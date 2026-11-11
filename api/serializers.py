import io

from PIL import Image, ImageOps
from rest_framework import serializers
from django.core.files.base import ContentFile
from django.db import transaction
from api.models import MAX_RECEIPT_SIZE, Category, Expense, ExpenseHistory, ExpenseNote, Goal, Income, IncomeSource, PaymentMethod, Receipt, ReceiptFileType, RecurrentExpense, SavingContribution, Tag, User, Budget
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

class UserProfileSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "date_joined", "password"]
        read_only_fields = ["id", "date_joined"]

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

class CategorySerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    total_spent = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    expense_count = serializers.IntegerField( read_only=True)
    class Meta:
        model = Category
        fields = ["category_id","name", "created_at", "description", "user_email", "total_spent", "expense_count"]
    
class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True, default=None)
    notes_count = serializers.SerializerMethodField()
    class Meta:
        model = Expense
        fields = ["expense_id", "title", "description", "date", "created_at", "user", "category",
                   "category_name" , "amount", "tags", "is_favorite", "payment_method", "payment_method_name",
                   "notes_count"]
        extra_kwargs={
            'user': {"read_only": True},
            "is_favorite" : {"read_only": True},
        }

    def get_notes_count(self, obj):
        # obj.notes is a related manager, not a list: count() runs SELECT COUNT(*).
        return obj.notes.count()

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

class AddExpenseNoteSerializer(serializers.ModelSerializer):
    note_id = serializers.UUIDField(read_only=True)
    content = serializers.CharField(max_length=1000)
    class Meta:
        model = ExpenseNote
        fields = ["note_id", "content"]

class ExpenseHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseHistory
        fields = ["history_id", "expense","action", "old_amount", "new_amount", "created_at" ]
        read_only_fields =["history_id", "expense", "created_at"]

class IncomeSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeSource
        fields = ["source_id", "user", "name", "created_at"]
        read_only_fields = ["source_id", "user", "created_at"]

class IncomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Income
        fields = ["income_id", "user", "title", "amount", "source", "date", "description", "created_at"]
        read_only_fields = ["income_id", "user", "created_at"]

    def validate_source(self, source):
        # Users cannot assign another user's income source to their income.
        request = self.context.get("request")
        if source and request and source.user != request.user:
            raise serializers.ValidationError("This income source does not belong to you.")
        return source

class IncomeBySourceSerializer(serializers.Serializer):
    source = serializers.CharField(allow_null=True)  # null = incomes with no source
    total = serializers.DecimalField(max_digits=20, decimal_places=2)


class IncomeStatisticsSerializer(serializers.Serializer):
    month = serializers.IntegerField()
    year = serializers.IntegerField()
    total_income = serializers.DecimalField(max_digits=20, decimal_places=2)
    income_count = serializers.IntegerField()
    by_source = IncomeBySourceSerializer(many=True)

class CashFlowSerializer(serializers.Serializer):
    month = serializers.IntegerField()
    year = serializers.IntegerField()
    total_income = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=20, decimal_places=2)
    net_cash_flow = serializers.DecimalField(max_digits=20, decimal_places=2)
    savings_rate = serializers.DecimalField(max_digits=20, decimal_places=1)

MAX_RECEIPTS_PER_EXPENSE = 5
THUMBNAIL_SIZE = (300, 300)

# The first bytes of each allowed file type ("magic numbers").
FILE_SIGNATURES = {
    b"\xff\xd8\xff": ReceiptFileType.JPEG,
    b"\x89PNG\r\n\x1a\n": ReceiptFileType.PNG,
    b"%PDF-": ReceiptFileType.PDF,
}


def detect_content_type(file):
    """Return the ReceiptFileType based on the file's content (not its name), or None."""
    file.seek(0)
    header = file.read(8)
    file.seek(0)
    for signature, content_type in FILE_SIGNATURES.items():
        if header.startswith(signature):
            return content_type
    return None


def make_thumbnail(file):
    """A JPEG at most 300x300, keeping the aspect ratio and the photo's orientation."""
    file.seek(0)
    with Image.open(file) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail(THUMBNAIL_SIZE)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
    file.seek(0)
    return ContentFile(buffer.getvalue())


class ReceiptSerializer(serializers.ModelSerializer):
    # Upload only: the response describes the receipt instead of returning the raw file.
    file = serializers.FileField(write_only=True)
    has_thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Receipt
        fields = [
            "receipt_id",
            "expense",
            "file",
            "original_name",
            "content_type",
            "size",
            "has_thumbnail",
            "uploaded_at",
        ]
        # Everything except "file" is set by the server, never by the client.
        read_only_fields = [
            "receipt_id",
            "expense",
            "original_name",
            "content_type",
            "size",
            "uploaded_at",
        ]

    def get_has_thumbnail(self, obj):
        return bool(obj.thumbnail)

    def validate_file(self, file):
        if file.size == 0:
            raise serializers.ValidationError("The file is empty.")
        if file.size > MAX_RECEIPT_SIZE:
            raise serializers.ValidationError("The file must be 5 MB or smaller.")

        content_type = detect_content_type(file)
        if content_type is None:
            raise serializers.ValidationError("Only JPEG, PNG and PDF files are allowed.")

        if content_type != ReceiptFileType.PDF:
            # The header looks like an image; make sure the whole file really is one.
            try:
                with Image.open(file) as image:
                    image.verify()
            except Exception:
                raise serializers.ValidationError("The image file is corrupted or invalid.")
            finally:
                file.seek(0)

        file.detected_content_type = content_type
        return file

    def validate(self, attrs):
        # The view passes the expense in the context after checking it belongs to the user.
        expense = self.context["expense"]
        if expense.is_deleted:
            raise serializers.ValidationError("You cannot add receipts to a deleted expense.")
        if expense.receipts.count() >= MAX_RECEIPTS_PER_EXPENSE:
            raise serializers.ValidationError(
                f"An expense can have at most {MAX_RECEIPTS_PER_EXPENSE} receipts."
            )
        return attrs

    def create(self, validated_data):
        file = validated_data["file"]
        receipt = Receipt(
            expense=self.context["expense"],
            file=file,
            original_name=file.name[:255],
            content_type=file.detected_content_type,
            size=file.size,
        )
        if receipt.content_type != ReceiptFileType.PDF:
            # save=False: the receipt itself is saved once, below.
            receipt.thumbnail.save("thumbnail.jpg", make_thumbnail(file), save=False)
        receipt.save()
        return receipt