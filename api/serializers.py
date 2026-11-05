from dataclasses import field, fields
from operator import concat
from pyexpat import model
from unicodedata import category
from rest_framework import serializers
from django.db import transaction
from api.models import Category, Expense, Goal, PaymentMethod, RecurrentExpense, SavingContribution, Tag, User, Budget
from decimal import Decimal
from django.db.models import Sum


class CreateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model= User
        fields = ["username","email", "password"]
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(**validated_data)
            return user

class CategorySerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    class Meta:
        model = Category
        fields = ["category_id","name", "created_at", "description", "user_email"]
    
class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True, default=None)
    class Meta:
        model = Expense
        fields = ["expense_id", "title", "description", "date", "created_at", "user", "category", "category_name" , "amount", "tags", "is_favorite", "payment_method", "payment_method_name"]
        extra_kwargs={
            'user': {"read_only": True},
            "is_favorite" : {"read_only": True}
        }

    def validate_category(self, category):
        request = self.context.get("request")
        if request and category.user != request.user:
            raise serializers.ValidationError(
                "This category does not belong to you."
            )
        return category

    def validate_tags(self, tags):
        request = self.context.get("request")
        if request and any(tag.user != request.user for tag in tags):
            raise serializers.ValidationError(
                "This tag does not belong to you."
            )
        return tags

    def validate_payment_method(self, payment_method):
        # None is allowed: an expense may have no payment method.
        request = self.context.get("request")
        if payment_method and request and payment_method.user != request.user:
            raise serializers.ValidationError(
                "This payment method does not belong to you."
            )
        return payment_method

    # def validate_title(self, title):
        # if len(title)==0 :
        #     raise serializers.ValidationError(
        #         "The title cannot be empty."
        #     )
        # return title
        # commented because: 
        # DRF builds the serializer field with allow_blank=False.
        #  A title of "" gets a "This field may not be blank." error before validate_title is called. 

class CategoryExpenseSerializer(serializers.Serializer):
    category = serializers.CharField()
    total = serializers.DecimalField(max_digits=20, decimal_places=2)


class ExpenseStatisticsSerializer(serializers.Serializer):
    total_expenses = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    by_category = CategoryExpenseSerializer(many=True)

class PaymentMethodStatisticsSerializer(serializers.Serializer):
    payment_method_id = serializers.UUIDField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    total_spent = serializers.DecimalField(max_digits=20, decimal_places=2)
    expense_count = serializers.IntegerField()

class BudgetSerializer(serializers.ModelSerializer):
    spent = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    percentage_used = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            "budget_id",
            "category",
            "user",
            "month",
            "year",
            "amount",
            "spent",
            "remaining",
            "percentage_used",
        ]
        read_only_fields = [
            "budget_id",
            "user",
            # SerializerMethodField is automatically read-only. You don't need to add these fields to read_only_fields
        ]

    def validate_category(self, category):
        request = self.context.get("request")

        if request and category.user != request.user:
            raise serializers.ValidationError(
                "This category does not belong to you."
            )

        return category

    def get_spent(self, obj):
        total = Expense.objects.filter(
            user=obj.user,
            category=obj.category,
            date__month=obj.month,
            date__year=obj.year,
        ).aggregate(total=Sum("amount"))

        return total["total"] or Decimal("0.00")

    def get_remaining(self, obj):
        spent = self.get_spent(obj)
        return obj.amount - spent

    def get_percentage_used(self, obj):
        spent = self.get_spent(obj)

        if obj.amount <= 0:
            return 0

        return round((spent / obj.amount) * 100, 2)


class RecurrentExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurrentExpense    
        fields = ["recurrent_expense_id", "title", "amount", "frequency", "start_date", "user", "category", "created_at"]   
        extra_kwargs={
            'user': {"read_only": True}
        }

    def validate_category(self, category):
        request = self.context.get("request")
        if request and category.user != request.user:
            raise serializers.ValidationError(
                "This category does not belong to you."
            )
        return category

class GenerateExpensesSerializer(serializers.Serializer):
    until_date = serializers.DateField()


class MonthlyReportQuerySerializer(serializers.Serializer):
    month = serializers.IntegerField(min_value=1, max_value=12)
    year = serializers.IntegerField(min_value=2000, max_value=9999)


class LargestExpenseSerializer(serializers.Serializer):
    title = serializers.CharField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)


class MonthlyReportSerializer(serializers.Serializer):
    month = serializers.IntegerField()
    year = serializers.IntegerField()
    total_spent = serializers.DecimalField(max_digits=20, decimal_places=2)
    expense_count = serializers.IntegerField()
    largest_expense = LargestExpenseSerializer(allow_null=True)
    previous_month_total = serializers.DecimalField(max_digits=20, decimal_places=2)
    # coerce_to_string=False renders a JSON number (25.0) instead of a string ("25.00")
    change_percentage = serializers.DecimalField(
        max_digits=20, decimal_places=2, coerce_to_string=False, allow_null=True
    )


class TagSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Tag
        fields = ["tag_id", "name", "user", "user_name", "created_at"]
        read_only_fields = ["tag_id", "user", "created_at"]

    def validate_name(self, value):
        user = self.context["request"].user
        qs = Tag.objects.filter(user=user, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"message": "You already have a tag with this name.", "code":"duplicate_tag_name"})
        return value

class SavingContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingContribution
        fields = ["contribution_id", "goal", "amount", "date", "created_at"]
        read_only_fields = [ "goal", "contribution_id", "created_at"]

class GoalSerializer(serializers.ModelSerializer):
    # "contributions" is the related_name on SavingContribution.goal
    contributions = SavingContributionSerializer(many=True, read_only=True)
    # computed on the Goal model (properties), so they are read-only here
    is_completed = serializers.BooleanField(read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    progress_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = Goal
        fields = ["goal_id", "title", "target_amount", "target_date", "user", "created_at", "contributions", "is_completed", "remaining_amount", "progress_percentage"]
        read_only_fields = [ "user", "created_at"]

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ["payment_method_id", "name", "user", "is_default", "created_at"]
        read_only_fields = [ "user", "created_at"]