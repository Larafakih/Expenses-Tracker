from django.urls import path
from api import views
from rest_framework.routers import DefaultRouter

urlpatterns = [
    path('users/', views.UserCreate.as_view())
    ]

router = DefaultRouter()
router.register('categories', views.CategoryViewSet) # registering prefix to the viewset
router.register('expenses', views.ExpenseViewSet) # registering prefix to the viewset

urlpatterns += router.urls