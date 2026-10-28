from django.contrib import admin
from api.models import Category, Expense, User

# Register your models here.
admin.site.register(User)
admin.site.register(Category)
admin.site.register(Expense)