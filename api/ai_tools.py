from api.models import Expense



def list_expenses(user, category=None, date_from=None, date_to=None, limit=20):
    qs = Expense.objects.active().filter(user=user).select_related("category").order_by("-date")
    if category:
        qs = qs.filter(category__name__iexact=category)
    if date_from:
        qs = qs.filter(date__date__gte=date_from)
    if date_to:
        qs = qs.filter(date__date__lte=date_to)
    return [
        {"id": str(e.pk), "title": e.title, "amount": str(e.amount),
         "date": e.date.date().isoformat(), "category": e.category.name}
        # between 1 and 50: a negative slice would crash, a huge one is too much data for the AI
        for e in qs[:max(1, min(int(limit), 50))]
    ]


def get_expense(user, expense_id):
    # filter by user: the AI must never be able to read another user's expense
    expense = Expense.objects.active().filter(user=user, pk=expense_id).first()
    if expense is None:
        return {"error": "Expense not found"}
    return {"id": str(expense.pk), "title": expense.title, "amount": str(expense.amount),
            "date": expense.date.isoformat(), "category": expense.category.name,
            "description": expense.description}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_expenses",
            "description": "List the user's expenses, newest first. Use filters to narrow down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Category name, e.g. Food"},
                    "date_from": {"type": "string", "description": "Start date, YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "End date, YYYY-MM-DD"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expense",
            "description": "Get full details of one expense by its id.",
            "parameters": {
                "type": "object",
                "properties": {"expense_id": {"type": "string", "description": "The expense id"}},
                "required": ["expense_id"],
            },
        },
    },
]

TOOL_FUNCTIONS = {"list_expenses": list_expenses, "get_expense": get_expense}
