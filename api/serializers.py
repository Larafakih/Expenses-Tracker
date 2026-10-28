from dataclasses import field, fields
from pyexpat import model
from unicodedata import category
from rest_framework import serializers
from django.db import transaction
from api.models import Category, Expense, User


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

class CategoryExpenseSerializer(serializers.Serializer):
    category = serializers.CharField()
    total = serializers.DecimalField(max_digits=20, decimal_places=2)


class ExpenseStatisticsSerializer(serializers.Serializer):
    total_expenses = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    by_category = CategoryExpenseSerializer(many=True)
