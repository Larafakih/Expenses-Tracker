from django.contrib import admin
from api.models import Budget, Category, Expense, User, RecurrentExpense

# Register your models here.
admin.site.register(User)
admin.site.register(Category)
admin.site.register(Expense)
admin.site.register(Budget)
admin.site.register(RecurrentExpense)