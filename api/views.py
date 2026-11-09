from calendar import monthrange
import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, render
from rest_framework import generics
from api.filters import ExpenseFilter, GoalFilter, IncomeFilter
from api.models import Category, ExpenseHistory, ExpenseNote, Goal, Income, IncomeSource, PaymentMethod, RecurrentExpense, SavingContribution, Tag, User, Expense, Budget
from api.serializers import (
    AddExpenseNoteSerializer,
    CashFlowSerializer,
    CategorySerializer,
    CreateUserSerializer,
    ExpenseHistorySerializer,
    ExpenseSerializer,
    ExpenseStatisticsSerializer,
    BudgetSerializer,
    GenerateExpensesSerializer,
    GoalSerializer,
    IncomeSerializer,
    IncomeSourceSerializer,
    IncomeStatisticsSerializer,
    MonthlyReportQuerySerializer,
    MonthlyReportSerializer,
    PaymentMethodSerializer,
    PaymentMethodStatisticsSerializer,
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
from django.db import transaction





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
        qs = Expense.objects.active()
        if not self.request.user.is_staff:
            qs = qs.for_user(self.request.user)
        return qs

    def perform_create(self, serializer):
        with transaction.atomic():
            expense = serializer.save(user=self.request.user)
            ExpenseHistory.objects.create(
                expense = expense,
                action = ExpenseHistory.HistoryChoices.CREATED,
                new_amount = expense.amount
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            old_amount = serializer.instance.amount   # captured before save
            expense = serializer.save()
            if old_amount != expense.amount:
                ExpenseHistory.objects.create(
                                        expense = expense,
                                        action = ExpenseHistory.HistoryChoices.UPDATED,
                                        new_amount = expense.amount,
                                        old_amount = old_amount
                                    )            
        
    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted'])
            ExpenseHistory.objects.create(
                                                expense = instance,
                                                action = ExpenseHistory.HistoryChoices.DELETED,
                                                old_amount = instance.amount
                                            )  
            
    @action(detail=True, methods=['post'], url_path='favorite')
    def set_as_favorite(self, request, pk):
        qs = Expense.objects.active()
        if not request.user.is_staff:
            qs = qs.for_user(self.request.user)
        expense = get_object_or_404(qs, pk=pk)
        expense.is_favorite = True
        expense.save(update_fields=['is_favorite'])
        serializer = self.get_serializer(expense)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='unfavorite')
    def unfavorite(self, request, pk):
        qs = Expense.objects.active()
        if not request.user.is_staff:
            qs = qs.for_user(self.request.user)
        expense = get_object_or_404(qs, pk=pk)
        expense.is_favorite = False
        expense.save(update_fields=['is_favorite'])
        serializer = self.get_serializer(expense)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='favorites')
    def list_favorites(self, request):
        favorite_expenses = Expense.objects.active().filter(is_favorite=True)
        if not request.user.is_staff:
            favorite_expenses = favorite_expenses.for_user(self.request.user)
        serializer = self.get_serializer(favorite_expenses, many=True)
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
        qs = Expense.objects.deleted()
        if not request.user.is_staff:
            qs = qs.for_user(self.request.user)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='restore')
    def restore_expense (self, request, pk):
        qs = Expense.objects.deleted()
        if not request.user.is_staff:
            qs = qs.for_user(self.request.user)
        expense = get_object_or_404(qs, pk=pk)
        expense.is_deleted = False
        expense.save(update_fields=['is_deleted'])
        serializer = self.get_serializer(expense)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='export')
    def export_expenses (self, request):
        # 1. Fetch and serialize data
        expenses = self.filter_queryset(Expense.objects.active().for_user(self.request.user))
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

    @action(detail=True, methods=['post'], url_path='notes')
    def add_note (self, request, pk):
        qs = Expense.objects.active()
        if not request.user.is_staff:
            qs = qs.for_user(self.request.user)
        expense = get_object_or_404(qs, pk=pk)
        input_serializer = AddExpenseNoteSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        note_content = input_serializer.validated_data["content"]

        note = ExpenseNote.objects.create(
            content=note_content,
            expense=expense
        )

        return Response(
            AddExpenseNoteSerializer(note).data,
            status=status.HTTP_201_CREATED
        )
    
    @add_note.mapping.get
    def list_expense_notes(self, request, pk=None):
        qs = Expense.objects.active()
        if not request.user.is_staff:
            qs = qs.for_user(self.request.user)
        expense = get_object_or_404(qs, pk=pk)
        notes = expense.notes.all()
        print(f"test")
        serializer = AddExpenseNoteSerializer(notes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)  

    @action(detail=True, methods=['get'], url_path='history')
    def list_expense_history(self, request, pk):
        qs = Expense.objects.all()
        if not request.user.is_staff:
            qs = qs.for_user(self.request.user)
        expense = get_object_or_404(qs, pk=pk)
        history = expense.history.all()
        serializer = ExpenseHistorySerializer(history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)  

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

class PaymentMethodViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentMethodSerializer
    queryset = PaymentMethod.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs= qs.filter(user= self.request.user)
        return qs
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(
        detail=False,
        methods=['get'],
        url_path='statistics',
        serializer_class=PaymentMethodStatisticsSerializer,
    )
    def payment_methods_statistics(self, request):
        expenses = Expense.objects.filter(is_deleted=False)
        if not request.user.is_staff:
            expenses = expenses.filter(user=request.user)

        # One row per payment method; expenses without one are grouped under null.
        by_pm = (
            expenses
            .values('payment_method_id', name=F('payment_method__name'))
            .annotate(
                total_spent=Sum('amount'),
                expense_count=Count('expense_id'),
            )
            .order_by('name')
        )
        serializer = self.get_serializer(by_pm, many=True)
        return Response(serializer.data)
            
    @action(detail=True, methods=['post'], url_path='set-default')
    def set_payment_method_as_default(self, request, pk=None):
        pm = self.get_object()  # already limited to the user's own methods by get_queryset()
        with transaction.atomic():
            PaymentMethod.objects.filter(
                user=pm.user, is_default=True
            ).exclude(pk=pm.pk).update(is_default=False)
            pm.is_default = True
            pm.save(update_fields=['is_default'])
        serializer = self.get_serializer(pm)
        return Response(serializer.data)

class ExpenseNoteDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddExpenseNoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ExpenseNote.objects.all()
    lookup_field = 'pk'  # Default lookup field
    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs= qs.filter(expense__user= self.request.user)
        return qs

class IncomeSourceViewSet(viewsets.ModelViewSet):
    serializer_class = IncomeSourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = IncomeSource.objects.all()
    def get_queryset(self):
            qs = super().get_queryset()
            if not self.request.user.is_staff:
                qs= qs.filter(user= self.request.user)
            return qs
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class IncomeViewSet(viewsets.ModelViewSet):
    serializer_class = IncomeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Income.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = IncomeFilter
    search_fields = ['title', 'description', 'source__name']
    ordering_fields = ['date', 'amount']

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='statistics', serializer_class=IncomeStatisticsSerializer)
    def get_income_statistics(self, request):
        params = MonthlyReportQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        month = params.validated_data["month"]
        year = params.validated_data["year"]

        start = month_start(year, month)
        end = month_start(year, month + 1)
        incomes = (
            self.filter_queryset(self.get_queryset())
            .order_by()  # clear default ordering so it doesn't affect GROUP BY
            .filter(date__gte=start, date__lt=end)
        )

        totals = incomes.aggregate(
            total_income=Sum('amount', default=Decimal('0.00')),
            income_count=Count('income_id'),
        )
        # Group by source id + name; incomes without a source form one row with source=None.
        by_source = (
            incomes
            .values('source__source_id', 'source__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        serializer = self.get_serializer({
            "month": month,
            "year": year,
            "total_income": totals["total_income"],
            "income_count": totals["income_count"],
            "by_source": [
                {"source": row["source__name"], "total": row["total"]}
                for row in by_source
            ],
        })
        return Response(serializer.data)



class CashFlowView(APIView):
    permission_classes = [permissions.IsAuthenticated]




class NetCashView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        params = MonthlyReportQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        month = params.validated_data["month"]
        year = params.validated_data["year"]


        start = month_start(year, month)
        end = month_start(year, month + 1)
        user_expenses = Expense.objects.filter(user=request.user, is_deleted=False)
        expenses = user_expenses.filter(date__gte=start, date__lt=end)
        income = Income.objects.filter(user=request.user, date__gte=start, date__lt=end)

        expenses_total = expenses.aggregate(
                    total_expense=Sum('amount'),
                )
        incomes_total = income.aggregate(
                            total_income=Sum('amount'),
                        )

        net_cash_flow = incomes_total['total_income'] - expenses_total['total_expense']
        savings_rate = net_cash_flow/incomes_total['total_income']  *100

        serializer = CashFlowSerializer({
            "month": month,
            "year": year,
            "total_income":incomes_total['total_income'],
            "total_expenses": expenses_total['total_expense'],
            "net_cash_flow": net_cash_flow,
            "savings_rate" : savings_rate
        })
        return Response(serializer.data)
             