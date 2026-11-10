import uuid
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce, Length, Lower, Trim
from django.db.models.lookups import GreaterThan, LessThanOrEqual
from django.utils import timezone

from api.managers import ExpenseQuerySet


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

class PaymentMethod(models.Model):
    payment_method_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="paymentmethods")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="payment_method_name_not_empty",
            ),
            # A user cannot have two payment methods with the same name (case-insensitive).
            models.UniqueConstraint(
                Lower("name"),
                "user",
                name="unique_payment_method_name_per_user_ci",
                violation_error_message="You already have a payment method with this name.",
            ),
            # A user can have only one default payment method.
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default=True),
                name="one_default_payment_method_per_user",
                violation_error_message="You can only have one default payment method.",
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
    is_favorite = models.BooleanField(default=False)
    # One payment method per expense; one payment method -> many expenses.
    # Optional (null/blank) so existing expenses stay valid, and SET_NULL so
    # deleting a payment method keeps its expenses.
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    objects = ExpenseQuerySet.as_manager()

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

    def clean(self):
        super().clean()
        # Users cannot assign another user's payment method to an expense.
        if (
            self.payment_method_id
            and self.user_id
            and self.payment_method.user_id != self.user_id
        ):
            raise ValidationError(
                {"payment_method": "This payment method does not belong to you."}
            )

    def __str__(self):
        return f"{self.title} ({self.amount}) - {self.category.name}"

class ExpenseNote(models.Model):
    note_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="notes")
    content = models.TextField(max_length=1000, validators=[MaxLengthValidator(1000)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            # Required, and not empty or whitespace-only.
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("content")), 0),
                name="expense_note_content_not_blank",
            ),
            # At most 1,000 characters (TextField max_length is not enforced by the database).
            models.CheckConstraint(
                condition=LessThanOrEqual(Length("content"), 1000),
                name="expense_note_content_max_1000",
            ),
        ]

    def clean(self):
        super().clean()
        # The database Trim only strips spaces; this also rejects tabs and newlines.
        if not (self.content or "").strip():
            raise ValidationError({"content": "Note content cannot be empty."})

    def __str__(self):
        return self.content[:50]


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

class ExpenseHistory(models.Model):
    class HistoryChoices(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DELETED = "deleted", "Deleted"

    history_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(
        max_length=10,
        choices=HistoryChoices.choices,
        default=HistoryChoices.CREATED,
    )
    # Nullable: a "created" record has no old amount, a "deleted" record has no new amount.
    old_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        null=True,
        blank=True,
    )
    new_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "expense histories"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(old_amount__isnull=True) | models.Q(old_amount__gt=0),
                name="expense_history_old_amount_gt_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(new_amount__isnull=True) | models.Q(new_amount__gt=0),
                name="expense_history_new_amount_gt_zero",
            ),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.expense_id} at {self.created_at}"

class IncomeSource(models.Model):
    source_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="income_sources")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="income_source_name_not_empty",
            ),
            # A user cannot have two income sources with the same name (case-insensitive).
            models.UniqueConstraint(
                Lower("name"),
                "user",
                name="unique_income_source_name_per_user_ci",
                violation_error_message="You already have an income source with this name.",
            ),
        ]

    def __str__(self):
        return self.name


class Income(models.Model):
    income_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="incomes")
    title = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    # One source -> many incomes. SET_NULL requires null=True; deleting a source keeps its incomes.
    source = models.ForeignKey(
        IncomeSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incomes",
    )
    # When the money was received.
    date = models.DateTimeField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="income_amount_gt_zero",
            ),
            models.CheckConstraint(
                condition=~models.Q(title=""),
                name="income_title_not_empty",
            ),
        ]

    def clean(self):
        super().clean()
        # Users cannot assign another user's income source to their income.
        if self.source_id and self.user_id and self.source.user_id != self.user_id:
            raise ValidationError({"source": "This income source does not belong to you."})

    def __str__(self):
        return f"{self.title} ({self.amount}) on {self.date}"

MAX_RECEIPT_SIZE = 5 * 1024 * 1024  # 5 MB


def receipt_upload_to(instance, filename):
    # Random stored name (never the user's filename): receipts/<user_id>/<uuid>.<ext>
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return f"receipts/{instance.expense.user_id}/{uuid.uuid4()}.{ext}"


def receipt_thumbnail_upload_to(instance, filename):
    return f"receipts/{instance.expense.user_id}/thumbnails/{uuid.uuid4()}.jpg"


class ReceiptFileType(models.TextChoices):
    JPEG = "image/jpeg", "JPEG"
    PNG = "image/png", "PNG"
    PDF = "application/pdf", "PDF"


class Receipt(models.Model):
    FileChoices = ReceiptFileType  # so Receipt.FileChoices.PDF still works

    receipt_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="receipts")
    file = models.FileField(upload_to=receipt_upload_to)
    # The name the user uploaded, e.g. "carrefour_nov.jpg" (shown back to them, not used on disk).
    original_name = models.CharField(max_length=255)
    # Detected from the file content when uploading, so there is no default.
    content_type = models.CharField(max_length=50, choices=FileChoices.choices)
    size = models.PositiveIntegerField(help_text="File size in bytes.")
    # Only images get a thumbnail; PDFs leave it empty.
    thumbnail = models.ImageField(upload_to=receipt_thumbnail_upload_to, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(size__gt=0, size__lte=MAX_RECEIPT_SIZE),
                name="receipt_size_between_1_byte_and_5mb",
            ),
            models.CheckConstraint(
                condition=models.Q(content_type__in=ReceiptFileType.values),
                name="receipt_content_type_allowed",
            ),
            models.CheckConstraint(
                condition=~models.Q(original_name=""),
                name="receipt_original_name_not_empty",
            ),
        ]

    def __str__(self):
        return f"{self.original_name} ({self.expense_id})"