import django_filters

from rest_framework import filters

from api.models import Expense

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
