"""
Services: the business logic of the app, kept out of the views.

A service is a plain Python function that:
  - takes plain inputs (a user, numbers, model objects) -- never a `request`
  - does the work (queries, rules, saving to the database)
  - returns plain results (model objects, lists, numbers) -- never a `Response`

The view's job then shrinks to:  read the request -> call the service -> build the response.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models.aggregates import Sum

from api.models import Budget, Expense, Income, User
from api.utils import month_start


@dataclass
class CopyBudgetsResult:
    """What copy_previous_month_budgets() returns: the budgets it created and the ones it skipped."""
    created: list = field(default_factory=list)   # new Budget objects
    skipped: list = field(default_factory=list)   # previous-month Budget objects not copied (category already had one)


@transaction.atomic   # all budgets are created, or none (if anything fails half-way)
def copy_previous_month_budgets(user: User, year: int, month: int) -> CopyBudgetsResult:
    """Copy the user's budgets from the month before (year, month) into (year, month).

    Categories that already have a budget in the target month are skipped, not overwritten.
    """
    # month_start handles the January -> previous December rollover
    previous = month_start(year, month - 1)

    previous_budgets = Budget.objects.filter(
        user=user, year=previous.year, month=previous.month
    ).select_related("category")

    # Categories that already have a budget in the target month
    existing_category_ids = set(
        Budget.objects.filter(user=user, year=year, month=month)
        .values_list("category_id", flat=True)
    )

    result = CopyBudgetsResult()
    for pb in previous_budgets:
        if pb.category_id in existing_category_ids:
            result.skipped.append(pb)
        else:
            result.created.append(Budget(
                category=pb.category,
                user=user,
                amount=pb.amount,
                year=year,
                month=month,
            ))

    Budget.objects.bulk_create(result.created)
    return result

@dataclass
class CashFlowResult:
    total_income: Decimal
    total_expenses: Decimal
    net_cash_flow: Decimal
    savings_rate: Decimal | None      # None when there is no income

def get_cash_flow(user: User, year: int, month: int) -> CashFlowResult:
    start = month_start(year, month)
    end = month_start(year, month + 1)
    expenses = Expense.objects.filter(user=user, is_deleted=False, date__gte=start, date__lt=end)
    incomes = Income.objects.filter(user=user, date__gte=start, date__lt=end)

    total_expenses = expenses.aggregate(total=Sum("amount", default=Decimal("0.00")))["total"]
    total_income = incomes.aggregate(total=Sum("amount", default=Decimal("0.00")))["total"]

    net_cash_flow = total_income - total_expenses
    # No income -> no savings rate (and no division by zero)
    savings_rate = net_cash_flow / total_income * 100 if total_income else None

    return CashFlowResult(total_income, total_expenses, net_cash_flow, savings_rate)