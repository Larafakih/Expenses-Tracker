from datetime import timedelta

from django.utils import timezone
import django_filters

from rest_framework import filters

from decimal import Decimal

from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce

from api.models import Expense, Goal, Income

class UUIDInFilter(django_filters.BaseInFilter, django_filters.UUIDFilter):
    """Comma-separated list of UUIDs, e.g. ?tags=id1,id2"""


class ExpenseFilter(django_filters.FilterSet):
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    tags = UUIDInFilter(field_name="tags__tag_id", lookup_expr="in", distinct=True)
    is_favorite = django_filters.BooleanFilter(field_name="is_favorite")
    payment_method = django_filters.UUIDFilter(field_name="payment_method__payment_method_id", lookup_expr="exact", )
    payment_method__isnull = django_filters.BooleanFilter(field_name="payment_method", lookup_expr="isnull")

    class Meta:
        model = Expense
        fields = {
            "category": ["exact"],
            # 'date': ["gte", "lte"],
            # "amount": ["gte", "lte"], # this make it possible with amount__gte and amount__lte
                }


class GoalFilter(django_filters.FilterSet):
    # ?completed=true / ?completed=false
    completed = django_filters.BooleanFilter(method="filter_completed")
    upcoming = django_filters.BooleanFilter(
        method="filter_upcoming"
    )

    class Meta:
        model = Goal
        fields = []

    def filter_completed(self, queryset, name, value):
        queryset = queryset.annotate(
            saved=Sum("contributions__amount", default=0)
        )

        if value:
            return queryset.filter(saved__gte=F("target_amount"))

        return queryset.filter(saved__lt=F("target_amount"))

    def filter_upcoming(self, queryset, name, value):
        if value:
            today = timezone.localdate()
            end_date = today + timedelta(days=30)

            return queryset.filter(
                target_date__range=(today, end_date)
            )

        return queryset

class IncomeFilter(django_filters.FilterSet):
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    start_date = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    source = django_filters.UUIDFilter(field_name="source__source_id", lookup_expr="exact", )

    class Meta:
        model = Income
        fields = []
