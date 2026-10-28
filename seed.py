"""
Populate the database with sample users, categories and expenses.

Usage (from the project root, with the venv activated):
    python seed.py            # add sample data
    python seed.py --reset    # delete existing users/categories/expenses first
"""
import os
import random
import sys
from datetime import timedelta
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from api.models import Category, Expense, User  # noqa: E402

USERS = [
    {"username": "alice", "email": "alice@example.com", "password": "Passw0rd!123"},
    {"username": "bob", "email": "bob@example.com", "password": "Passw0rd!123"},
]

# category name -> (description, [(title, min_amount, max_amount), ...])
CATEGORIES = {
    "Food": (
        "Groceries and restaurants",
        [("Groceries", 15, 120), ("Restaurant", 10, 80), ("Coffee", 2, 8)],
    ),
    "Transport": (
        "Fuel, taxi and public transport",
        [("Fuel", 20, 70), ("Taxi", 5, 40), ("Bus ticket", 1, 5)],
    ),
    "Utilities": (
        "Bills and subscriptions",
        [("Electricity bill", 30, 150), ("Internet", 20, 60), ("Phone plan", 10, 40)],
    ),
    "Entertainment": (
        "Movies, games and fun",
        [("Cinema", 8, 25), ("Video game", 15, 70), ("Concert", 30, 150)],
    ),
}

EXPENSES_PER_CATEGORY = 8


def random_amount(low, high):
    """Random Decimal with 2 decimal places, always > 0."""
    value = Decimal(str(round(random.uniform(low, high), 2)))
    return max(value, Decimal("0.01"))


@transaction.atomic
def seed(reset=False):
    if reset:
        Expense.objects.all().delete()
        Category.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        print("Existing data deleted.")

    now = timezone.now()

    for user_data in USERS:
        user, created = User.objects.get_or_create(
            username=user_data["username"],
            defaults={"email": user_data["email"]},
        )
        if created:
            user.set_password(user_data["password"])
            user.save()
            print(f"Created user: {user.username}")

        for cat_name, (cat_desc, templates) in CATEGORIES.items():
            category, _ = Category.objects.get_or_create(
                user=user,
                name=cat_name,
                defaults={"description": cat_desc},
            )

            expenses = []
            for _ in range(EXPENSES_PER_CATEGORY):
                title, low, high = random.choice(templates)
                expenses.append(
                    Expense(
                        title=title,
                        amount=random_amount(low, high),
                        category=category,
                        description=f"{title} - sample data",
                        user=user,
                        date=now - timedelta(days=random.randint(0, 90)),
                    )
                )
            Expense.objects.bulk_create(expenses)

    print(
        f"Done. Users: {User.objects.count()}, "
        f"Categories: {Category.objects.count()}, "
        f"Expenses: {Expense.objects.count()}"
    )


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)