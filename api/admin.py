from django.contrib import admin
from api.models import Budget, Category, Expense, Goal, RecurrentExpense, SavingContribution, Tag, User

# Register your models here.
admin.site.register(User)
admin.site.register(Category)
admin.site.register(Expense)
admin.site.register(Budget)
admin.site.register(Tag)
admin.site.register(RecurrentExpense)
admin.site.register(Goal)
admin.site.register(SavingContribution)