from calendar import monthrange
import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, render
from rest_framework import generics
from api.filters import ExpenseFilter, GoalFilter
from api.models import Category, Goal, RecurrentExpense, SavingContribution, Tag, User, Expense, Budget
from api.serializers import (
    CategorySerializer,
    CreateUserSerializer,
    ExpenseSerializer,
    ExpenseStatisticsSerializer,
    BudgetSerializer,
    GenerateExpensesSerializer,
    GoalSerializer,
    MonthlyReportQuerySerializer,
    MonthlyReportSerializer,
    RecurrentExpenseSerializer,
    SavingContributionSerializer,
    TagSerializer,
)
from rest_framework import permissions, serializers, status
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView



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
        qs = super().get_queryset().filter(is_deleted=False)
        if not self.request.user.is_staff:
            qs= qs.filter(user= self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])

    @action(detail=True, methods=['post'], url_path='favorite')
    def set_as_favorite(self, request, pk):
        qs = Expense.objects
        if not request.user.is_staff:
            qs = qs.filter(user=request.user, is_deleted= False)
        expense = get_object_or_404(qs, pk=pk)
        expense.is_favorite = True
        expense.save(update_fields=['is_favorite'])
        serializer = self.get_serializer(expense)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='unfavorite')
    def unfavorite(self, request, pk):
        qs = Expense.objects
        if not request.user.is_staff:
            qs = qs.filter(user=request.user, is_deleted= False)
        expense = get_object_or_404(qs, pk=pk)
        expense.is_favorite = False
        expense.save(update_fields=['is_favorite'])
        serializer = self.get_serializer(expense)
        return Response(serializer.data)

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

    @action(detail=False, methods=['get'], url_path='trash')
    def get_soft_deleted_expenses(self, request):
        expenses = Expense.objects.filter(is_deleted=True)
        if not request.user.is_staff:
            expenses = expenses.filter(user=request.user)
        serializer = self.get_serializer(expenses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='restore')
    def restore_expense (self, request, pk):
        qs = Expense.objects.filter(is_deleted=True)
        if not request.user.is_staff:
            qs = qs.filter(user=request.user)
        expense = get_object_or_404(qs, pk=pk)
        expense.is_deleted = False
        expense.save(update_fields=['is_deleted'])
        serializer = self.get_serializer(expense)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='export')
    def export_expenses (self, request):
        # 1. Fetch and serialize data
        expenses = self.filter_queryset(Expense.objects.filter(user=request.user, is_deleted=False))
        serializer = ExpenseSerializer(expenses, many=True)

        # 2. Create the HttpResponse object with CSV headers
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="exported_data.csv"'

        writer = csv.writer(response)
        
        # 3. Write header row based on serializer fields
        fields = ["title", "description", "date","user", "created_at",  "category_name" , "amount"]
        writer.writerow([field.replace('_', ' ').title() for field in fields])
        
        # 4. Write data rows
        for row in serializer.data:
            writer.writerow([row.get(field) for field in fields])
            
        return response




class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    queryset = Budget.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
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


class MonthlyReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        params = MonthlyReportQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        month = params.validated_data["month"]
        year = params.validated_data["year"]


        start = month_start(year, month)
        end = month_start(year, month + 1)
        previous_start = month_start(year, month - 1)

        user_expenses = Expense.objects.filter(user=request.user, is_deleted=False)
        expenses = user_expenses.filter(date__gte=start, date__lt=end)

        totals = expenses.aggregate(
            expense_count=Count('expense_id'),
            total_spent=Sum('amount'),
        )
        total_spent = totals['total_spent'] or Decimal('0.00')
        previous_total = (
            user_expenses
            .filter(date__gte=previous_start, date__lt=start)
            .aggregate(total=Sum('amount'))['total']
            or Decimal('0.00')
        )

        serializer = MonthlyReportSerializer({
            'month': month,
            'year': year,
            'total_spent': total_spent,
            'expense_count': totals['expense_count'],
            'largest_expense': expenses.order_by('-amount').first(),
            'previous_month_total': previous_total,
            'change_percentage': percentage(total_spent - previous_total, previous_total),
        })
        return Response(serializer.data)


def month_start(year, month):
    """Aware datetime at midnight on the 1st; month may overflow past 1..12 (e.g. 13 -> next January)."""
    month_index = month - 1
    return timezone.make_aware(datetime(year + month_index // 12, month_index % 12 + 1, 1))


def percentage(part, whole):
    if not whole:
        return None
    return round(part / whole * 100, 2)




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


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs= qs.filter(user= self.request.user)
        return qs
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class GoalViewset(viewsets.ModelViewSet):
    serializer_class = GoalSerializer
    queryset = Goal.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = GoalFilter

    def get_queryset(self):
            qs = super().get_queryset()
            if not self.request.user.is_staff:
                qs= qs.filter(user= self.request.user)
            return qs
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ("create_contribution", "list_contributions"):
            return SavingContributionSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=['post'], url_path='contributions')
    def create_contribution(self, request, pk=None):
        goal = self.get_object()  # 404 if it isn't the user's goal
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(goal=goal)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @create_contribution.mapping.get
    def list_contributions(self, request, pk=None):
        goal = self.get_object()  # 404 if it isn't the user's goal
        contributions = goal.contributions.all()
        serializer = self.get_serializer(contributions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
        


class ContributionDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SavingContributionSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SavingContribution.objects.all()
    lookup_field = 'pk'  # Default lookup field
    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs= qs.filter(goal__user= self.request.user)
        return qs