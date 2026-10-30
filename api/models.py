import uuid
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    pass


class Category(models.Model):
    category_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="category_name_not_empty",
            ),
        ]

    def __str__(self):
        return self.name



class Budget(models.Model):
    budget_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(2000)])
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="budget_amount_gt_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(month__gte=1, month__lte=12),
                name="budget_month_range",
            ),
            models.UniqueConstraint(
                fields=["user", "category", "year", "month"],
                name="unique_budget_per_category_month",
            ),
        ]

class RecurrentExpense(models.Model):
    class FrequencyChoices(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
    recurrent_expense_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(
            max_digits=20,
            decimal_places=2,
            validators=[MinValueValidator(Decimal("0.01"))],
        )
    start_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    frequency = models.CharField(
        max_length=10,
        choices=FrequencyChoices.choices,
        default=FrequencyChoices.MONTHLY
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} - {self.frequency}"


class Expense(models.Model):
    expense_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    recurrent_expense = models.ForeignKey(
        RecurrentExpense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_expenses"
        )
#     on_delete=models.SET_NULL	If the recurring template is deleted, its generated expenses remain in the database.
# null=True	Allows the database to store NULL for normal expenses.
# blank=True	Makes the field optional during Django model validation and in automatically generated forms.
# related_name="generated_expenses"
# recurrent_expense.generated_expenses.all()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="expense_amount_gt_zero",
            ),
            models.CheckConstraint(
                condition=~models.Q(title=""),
                name="expense_title_not_empty",
            ),
            models.UniqueConstraint(
            fields=["recurrent_expense", "date"],
            name="unique_recurrent_expense_date"
        )
        ]

    def __str__(self):
        return f"{self.title} ({self.amount}) - {self.category.name}"


