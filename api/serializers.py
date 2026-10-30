from dataclasses import field, fields
from pyexpat import model
from unicodedata import category
from rest_framework import serializers
from django.db import transaction
from api.models import Category, Expense, User, Budget
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
    class Meta:
        model = Expense    
        fields = ["expense_id", "title", "description", "date", "created_at", "user", "category", "category_name" , "amount"]   
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