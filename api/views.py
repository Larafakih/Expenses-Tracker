from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from django.shortcuts import render
from rest_framework import generics
from api.filters import ExpenseFilter
from api.models import Category, RecurrentExpense, User, Expense, Budget
from api.serializers import (
    CategorySerializer,
    CreateUserSerializer,
    ExpenseSerializer,
    ExpenseStatisticsSerializer,
    BudgetSerializer,
    GenerateExpensesSerializer,
    RecurrentExpenseSerializer
)
from rest_framework import permissions, serializers, status
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response



# Create your views here.
class UserCreate(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = CreateUserSerializer
    permission_classes = [permissions.AllowAny]

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        # qs = Category.objects.select_related("user")
        if not self.request.user.is_staff:
            qs= qs.filter(user= self.request.user)
        return qs


    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    queryset = Expense.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ExpenseFilter
    search_fields = ['title']
    ordering_fields = ['amount', 'date']

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs= qs.filter(user= self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        expenses = self.filter_queryset(self.get_queryset()).order_by()

        totals = expenses.aggregate(
            total_expenses=Count('expense_id'),
            total_amount=Sum('amount'),
        )
        by_category = (
            expenses
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('category__name')
        )

        serializer = ExpenseStatisticsSerializer({
            'total_expenses': totals['total_expenses'],
            'total_amount': totals['total_amount'] or Decimal('0.00'),
            'by_category': [
                {'category': row['category__name'], 'total': row['total']}
                for row in by_category
            ],
        })
        return Response(serializer.data)


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    queryset = Budget.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        # qs = Category.objects.select_related("user")
        if not self.request.user.is_staff:
            qs= qs.filter(user= self.request.user)
        return qs


    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class RecurrentExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = RecurrentExpenseSerializer
    queryset = RecurrentExpense.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
            qs = super().get_queryset()
            # qs = Category.objects.select_related("user")
            if not self.request.user.is_staff:
                qs= qs.filter(user= self.request.user)
            return qs
    def perform_create(self, serializer):
            serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        input_serializer = GenerateExpensesSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        until_date = input_serializer.validated_data["until_date"]

        templates = RecurrentExpense.objects.filter(user=request.user, is_active=True)
        to_create = []
        for template in templates:
            existing = set(
                template.generated_expenses.values_list("date", flat=True)
            )
            for day in scheduled_dates(template, until_date):
                when = timezone.make_aware(datetime.combine(day, time.min))
                if when not in existing:
                    to_create.append(Expense(
                        user=template.user,
                        category=template.category,
                        title=template.title,
                        amount=template.amount,
                        date=when,
                        recurrent_expense=template,
                    ))

        Expense.objects.bulk_create(to_create)
        return Response({"created": len(to_create)}, status=status.HTTP_201_CREATED)




def scheduled_dates(template, until_date):
    """Yield every date from template.start_date through until_date, inclusive."""
    start = template.start_date
    n = 0
    while True:
        if template.frequency == RecurrentExpense.FrequencyChoices.DAILY:
            day = start + timedelta(days=n)
        elif template.frequency == RecurrentExpense.FrequencyChoices.WEEKLY:
            day = start + timedelta(weeks=n)
        else:
            # computed from start each time so Jan 31 -> Feb 28 -> Mar 31, not Mar 28
            month_index = start.month - 1 + n
            year = start.year + month_index // 12
            month = month_index % 12 + 1
            day = date(year, month, min(start.day, monthrange(year, month)[1]))
        if day > until_date:
            return
        yield day
        n += 1




