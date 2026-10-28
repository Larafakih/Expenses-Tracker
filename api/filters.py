import django_filters

from rest_framework import filters

from api.models import Expense

class ExpenseFilter(django_filters.FilterSet):
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    class Meta:
        model = Expense
        fields = {
            "category": ["exact"],
            # 'date': ["gte", "lte"],
            # "amount": ["gte", "lte"], # this make it possible with amount__gte and amount__lte
                }
