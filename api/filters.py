import django_filters

from rest_framework import filters

from decimal import Decimal

from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce

from api.models import Expense, Goal

class UUIDInFilter(django_filters.BaseInFilter, django_filters.UUIDFilter):
    """Comma-separated list of UUIDs, e.g. ?tags=id1,id2"""


class ExpenseFilter(django_filters.FilterSet):
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    tags = UUIDInFilter(field_name="tags__tag_id", lookup_expr="in", distinct=True)

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

    class Meta:
        model = Goal
        fields = []

    def filter_completed(self, queryset, name, value):
        # same rule as Goal.is_completed: total saved >= target
        queryset = queryset.annotate(
            saved=Coalesce(
                Sum("contributions__amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            )
        )
        if value:
            return queryset.filter(saved__gte=F("target_amount"))
        return queryset.filter(saved__lt=F("target_amount"))
