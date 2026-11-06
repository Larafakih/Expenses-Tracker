from decimal import Decimal, InvalidOperation

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from api.models import Budget, Category, Expense, ExpenseHistory, Goal, PaymentMethod, RecurrentExpense, SavingContribution, Tag, User

# Register your models here.
# admin.site.register(ExpenseHistory)
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Extending Django's UserAdmin keeps the proper password-change form,
    # the "add user" form, and the permissions/groups fieldsets.
    list_display = [
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "date_joined",  # AbstractUser has no created_at field; date_joined is the equivalent
    ]

    # Filters suit fields with few distinct values (booleans, dates),
    # not free-text fields like email/username; those go in search_fields.
    list_filter = [
        "is_staff",
        "is_superuser",
        "is_active",
    ]

    search_fields = [
        "email",
        "username",
        "first_name",
        "last_name",
    ]

    ordering = ["-date_joined"]

    list_per_page = 20



@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "amount",
        "category",
        "user",
        "date",
        "is_deleted",
    ]

    list_filter = [
        "category",
        "is_deleted",
        "date",
    ]

    search_fields = [
        "title",
        "description",
    ]


    ordering = ["-date"]

    actions = ["move_to_trash"]

    @admin.action(description="Move selected expenses to trash")
    def move_to_trash(self, request, queryset):
        updated = queryset.update(is_deleted=True)

        self.message_user(
            request,
            f"{updated} expenses moved to trash."
        )

    list_per_page = 20

@admin.register(RecurrentExpense)
class RecurrentExpenseAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "user",
        "amount",
        "frequency",
        "is_active",
        "start_date",
    ]

    # Filters suit fields with few distinct values (choices, booleans, dates, FKs).
    list_filter = [
        "frequency",
        "is_active",
        "category",
        "user",
    ]

    # Search runs `<field>__icontains`, which needs text. For ForeignKeys,
    # follow the relation to a text field with "__" (plain "user" raises FieldError).
    search_fields = [
        "title",
        "user__username",
        "category__name",
    ]

    list_select_related = ["category", "user"]

    def get_search_results(self, request, queryset, search_term):
        # "amount" can't go in search_fields: search does a text LIKE match, and
        # SQLite stores 70.00 as 70, so "70.00" never matches (and "1" matches 10, 100...).
        # Instead, if the term is a number, also match it exactly against amount.
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        try:
            amount = Decimal(search_term.strip())
        except (InvalidOperation, ValueError):
            return queryset, may_have_duplicates
        queryset |= self.model.objects.filter(amount=amount)
        return queryset, may_have_duplicates


    ordering = ["-created_at"]

    list_per_page = 20

@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "target_amount",
        "target_date",
        "user__username",
        "created_at",
    ]

    list_filter = [
        "title",
        "user__username",
    ]

    search_fields = [
        "title",
        "user__username",
    ]

    ordering = ["-created_at"]

    list_per_page = 20

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = [
        "category",
        "user__username",
        "month",
        "year",
        "amount",
    ]

    list_filter = [
        "user__username",
    ]

    search_fields = [
        "user__username",
    ]

    def get_search_results(self, request, queryset, search_term):
        # "amount" can't go in search_fields: search does a text LIKE match, and
        # SQLite stores 70.00 as 70, so "70.00" never matches (and "1" matches 10, 100...).
        # Instead, if the term is a number, also match it exactly against amount.
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        try:
            amount = Decimal(search_term.strip())
        except (InvalidOperation, ValueError):
            return queryset, may_have_duplicates
        queryset |= self.model.objects.filter(amount=amount)
        return queryset, may_have_duplicates

    list_per_page = 20


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "user__username",
        "description",
        "created_at",
    ]

    list_filter = [
        "user__username",
        "name"
    ]

    search_fields = [
        "user__username",
        "name"
    ]


    list_per_page = 20

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "user__username",
        "is_default",
        "created_at",
    ]

    list_filter = [
        "user__username",
        "name"
    ]

    search_fields = [
        "user__username",
        "name"
    ]


    list_per_page = 20


@admin.register(SavingContribution)
class SavingContributionAdmin(admin.ModelAdmin):
    list_display = [
        "goal",
        "amount",
        "date",
    ]

    list_filter = [
        "goal__title",
        "date"
    ]

    search_fields = [
        "goal__title",
    ]

    def get_search_results(self, request, queryset, search_term):
        # "amount" can't go in search_fields: search does a text LIKE match, and
        # SQLite stores 70.00 as 70, so "70.00" never matches (and "1" matches 10, 100...).
        # Instead, if the term is a number, also match it exactly against amount.
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        try:
            amount = Decimal(search_term.strip())
        except (InvalidOperation, ValueError):
            return queryset, may_have_duplicates
        queryset |= self.model.objects.filter(amount=amount)
        return queryset, may_have_duplicates


    list_per_page = 20


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "user__username",
        "created_at",
    ]

    list_filter = [
        "user__username",
        "created_at"
    ]

    search_fields = [
        "user__username",
        "name"
    ]

    list_per_page = 20

@admin.register(ExpenseHistory)
class ExpenseHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "history_id",
        "expense",
        "action",
        "created_at",
        "old_amount",
        "new_amount"
    ]

    list_filter = [
        "history_id",
        "created_at"
    ]

    search_fields = [
        "expense__title",
        "history_id"
    ]

    list_per_page = 20
