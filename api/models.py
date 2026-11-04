import uuid
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
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

class Tag(models.Model):
    tag_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tags")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="tag_name_not_empty",
            ),
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_tag_name_per_user",
            ),
        ]

    def __str__(self):
        return self.name
    
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
    is_deleted = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, blank=True, related_name="expenses")

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


class Goal(models.Model):
    goal_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    target_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    target_date = models.DateField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="goals")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(target_amount__gt=0),
                name="goal_target_amount_gt_zero",
            ),
            models.CheckConstraint(
                condition=~models.Q(title=""),
                name="goal_title_not_empty",
            ),
            models.UniqueConstraint(
                fields=["user", "title", "target_date", "target_amount"],
                name="unique_goal",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.target_amount}) by {self.target_date}"

    @property
    def total_saved(self):
        # Sum is None when there are no contributions yet
        return self.contributions.aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00"))
        )["total"]

    @property
    def remaining_amount(self):
        return max(self.target_amount - self.total_saved, Decimal("0.00"))

    @property
    def progress_percentage(self):
        # capped at 100 when the user saves more than the target
        progress = min(self.total_saved / self.target_amount * 100, Decimal("100"))
        return round(progress, 2)

    @property
    def is_completed(self):
        return self.total_saved >= self.target_amount


class SavingContribution(models.Model):
    contribution_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # this line => contribution.goal and goal.contributions
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="contributions")
    
    amount = models.DecimalField(
            max_digits=20,
            decimal_places=2,
            validators=[MinValueValidator(Decimal("0.01"))],
            )
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="saving_contribution_amount_gt_zero",
            ),
        ]

    def __str__(self):
        return f"{self.amount} towards {self.goal.title} on {self.date}"
