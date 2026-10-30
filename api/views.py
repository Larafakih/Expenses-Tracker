from decimal import Decimal

from django.db.models import Count, Sum
from django.shortcuts import render
from rest_framework import generics
from api.filters import ExpenseFilter
from api.models import Category, User, Expense, Budget
from api.serializers import (
    CategorySerializer,
    CreateUserSerializer,
    ExpenseSerializer,
    ExpenseStatisticsSerializer,
    BudgetSerializer
)
from rest_framework import permissions
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
