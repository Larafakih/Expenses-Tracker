import json
import os
from decimal import Decimal

import requests
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from api.ai_tools import TOOL_FUNCTIONS, TOOLS
from api.models import Budget, Category, Expense, Income
from api.utils import month_start


SYSTEM_PROMPT = (
    "You are a helpful assistant inside a personal expense tracker app.\n"
    "\n"
    "Rules:\n"
    "- Answer ONLY using the DATA below. Never invent numbers.\n"
    "- If the DATA doesn't contain the answer, say: \"I don't have that information.\"\n"
    "- Keep answers short: 1 to 3 sentences.\n"
    "- Write amounts with 2 decimals, exactly as in the DATA.\n"
    "- \"This month\" is not finished yet; don't compare it to last month as if it were a full month.\n"
    "- If the user asks about something unrelated to their finances, politely say you can only help with their expenses.\n"
    "- Never give investment, tax or legal advice.\n"
    "- Answer in the same language the user writes in.\n"
    "\n"
    "DATA:\n{summary}"
)

EXPENSE_PARSER_PROMPT = (
    "Extract ONE expense from the user's text.\n"
    "Today is {today}. The user's categories are: {categories}.\n"
    "Rules:\n"
    "- Answer ONLY with JSON, no other text.\n"
    '- Format: {{"title": str, "amount": number, "date": "YYYY-MM-DD", "category": str}}\n'
    "- category MUST be one of the user's categories, written exactly.\n"
    '- If the text has no amount, answer {{"error": "no amount"}}.'
)



GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"


def groq_headers():
    return {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}


def ask_ai(system_prompt, user_message):
    response = requests.post(
        GROQ_URL,
        headers=groq_headers(),
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=20,
    )
    response.raise_for_status()   # turns 4xx/5xx into an exception
    return response.json()["choices"][0]["message"]["content"]


def spending_by_category(user, start, end):
    """{category_id: (category name, total)} for the user's active expenses in [start, end)."""
    rows = (
        Expense.objects.active()
        .filter(user=user, date__gte=start, date__lt=end)
        # values() + annotate() = GROUP BY category -> one dict per category.
        # Group by id (not only name): two categories could share a name.
        .values("category_id", "category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    return {row["category_id"]: (row["category__name"], row["total"]) for row in rows}


def income_total(user, start, end):
    return Income.objects.filter(
        user=user, date__gte=start, date__lt=end
    ).aggregate(total=Sum("amount", default=Decimal("0")))["total"]


def format_spending(spending):
    if not spending:
        return "none"
    return ", ".join(f"{name} {total:.2f}" for name, total in spending.values())


def build_summary(user):
    """Plain-text summary of the user's finances, computed by Django (not by the AI)."""
    today = timezone.localdate()
    this_month_start = month_start(today.year, today.month)
    next_month_start = month_start(today.year, today.month + 1)
    last_month_start = month_start(today.year, today.month - 1)

    this_month = spending_by_category(user, this_month_start, next_month_start)
    last_month = spending_by_category(user, last_month_start, this_month_start)
    this_total = sum((total for _, total in this_month.values()), Decimal("0"))
    last_total = sum((total for _, total in last_month.values()), Decimal("0"))

    income_this = income_total(user, this_month_start, next_month_start)
    income_last = income_total(user, last_month_start, this_month_start)

    budget_lines = []
    budgets = Budget.objects.filter(
        user=user, year=today.year, month=today.month
    ).select_related("category")
    for budget in budgets:
        _, spent = this_month.get(budget.category_id, (None, Decimal("0")))
        budget_lines.append(
            f"{budget.category.name}: budget {budget.amount:.2f}, "
            f"spent {spent:.2f}, remaining {budget.amount - spent:.2f}"
        )

    this_label = this_month_start.strftime("%B %Y")
    last_label = last_month_start.strftime("%B %Y")
    lines = [
        f"Today: {today.isoformat()}",
        # "so far": this month isn't over, so the AI shouldn't treat it as a full month.
        f"This month ({this_label}, so far) spending by category: {format_spending(this_month)}",
        f"This month total spending so far: {this_total:.2f}",
        f"Last month ({last_label}) spending by category: {format_spending(last_month)}",
        f"Last month total spending: {last_total:.2f}",
        # Precomputed so the AI only has to read it, not calculate it.
        f"Change in total spending vs last month: {this_total - last_total:+.2f}",
        f"Income this month so far: {income_this:.2f}",
        f"Income last month: {income_last:.2f}",
        f"Budgets this month: {'; '.join(budget_lines) or 'none'}",
    ]
    return "\n".join(lines)

def parse_expense_text(user, text):
    categories = list(Category.objects.filter(user=user).values_list("name", flat=True))
    # localdate(): only the date ("2026-11-17"), in the project's timezone.
    # ", ".join(): "Food, Transport" instead of the Python list "['Food', 'Transport']".
    prompt = EXPENSE_PARSER_PROMPT.format(
        today=timezone.localdate().isoformat(),
        categories=", ".join(categories),
    )
    answer = ask_ai(prompt, text)
    return json.loads(answer)

def chat(messages, tools=None):
    """Send a whole conversation; return the AI's full message (text OR tool_calls)."""
    body = {"model": MODEL, "messages": messages}
    if tools:
        body["tools"] = tools
    response = requests.post(GROQ_URL, headers=groq_headers(), json=body, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]


def run_tool(user, call):
    """Run one tool the AI asked for. Always returns something JSON-able, never raises."""
    name = call["function"]["name"]
    func = TOOL_FUNCTIONS.get(name)          # only OUR listed functions can run
    if func is None:
        return {"error": f"Unknown tool {name}"}
    try:
        args = json.loads(call["function"]["arguments"] or "{}")
        # user comes from our code, never from the AI
        return func(user, **args)
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        # Sent back to the AI, which usually fixes its call in the next round.
        return {"error": str(exc)}


def ask_with_tools(user, question, max_rounds=5):
    messages = [
        {"role": "system", "content": f"You help the user with their expenses. Today is {timezone.localdate()}. "
                                      f"Use the tools to get data. Never invent numbers. {SYSTEM_PROMPT}"},
        {"role": "user", "content": question},
    ]
    for _ in range(max_rounds):
        msg = chat(messages, tools=TOOLS)
        if not msg.get("tool_calls"):
            return msg.get("content") or "Sorry, I couldn't answer that."   # final text answer
        # Keep the AI's tool request in the history. Copy only the standard fields:
        # Groq also returns extra ones (like "reasoning") that it may refuse if sent back.
        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": msg["tool_calls"],
        })
        for call in msg["tool_calls"]:
            result = run_tool(user, call)
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],         # links the result to the request
                "content": json.dumps(result),
            })
    return "Sorry, I couldn't answer that."
