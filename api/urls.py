from django.urls import path
from api import views
from rest_framework.routers import DefaultRouter

urlpatterns = [
    path('users/', views.UserCreate.as_view()),
    path('reports/monthly/', views.MonthlyReportView.as_view()),
    path('contributions/<uuid:pk>/', views.ContributionDetailAPIView.as_view()),

    ]

router = DefaultRouter()
router.register('categories', views.CategoryViewSet) # registering prefix to the viewset
router.register('expenses', views.ExpenseViewSet)
router.register('budgets', views.BudgetViewSet)
router.register('recurrent-expenses', views.RecurrentExpenseViewSet)
router.register('tags', views.TagViewSet)
router.register('saving-goals', views.GoalViewset)
router.register('payment-methods', views.PaymentMethodViewSet)

urlpatterns += router.urls