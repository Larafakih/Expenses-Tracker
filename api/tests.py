from datetime import date, datetime

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Budget, Category, ExpenseHistory, Income, IncomeSource, Expense, Goal, ExpenseNote, PaymentMethod, RecurrentExpense, SavingContribution, Tag, User
from api.views import month_start, scheduled_dates
from api.services import copy_previous_month_budgets
from datetime import timedelta
from django.core.management import call_command
from decimal import Decimal



class ExpenseSoftDeleteTests(APITestCase):
    def setUp(self):
        # Runs before EVERY test method, on a fresh empty test database.
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.category = Category.objects.create(name="Food", user=self.user)
        self.expense = Expense.objects.create(
            title="Lunch",
            amount="12.50",
            category=self.category,
            user=self.user,
            date=timezone.now(),
        )
        # Skip the login flow: make every request act as this user.
        self.client.force_authenticate(user=self.user)
        # force_authenticate tells the fake client to act as that user.

    def test_delete_marks_expense_as_deleted_instead_of_removing_it(self):
        # Act: call the API like a real client would.
        response = self.client.delete(f"/expenses/{self.expense.expense_id}/")

        # Assert 1: the API says "deleted, nothing to return".
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Assert 2: the row still exists, but flagged. Re-read it from the DB.
        self.expense.refresh_from_db()
        self.assertTrue(self.expense.is_deleted)

    def test_deleted_expense_is_hidden_from_the_list(self):
        self.client.delete(f"/expenses/{self.expense.expense_id}/")

        response = self.client.get("/expenses/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

class MonthStartTests(APITestCase):
    def setUp(self):
        self.date1 = month_start(2026,4)
        self.date2 = month_start(2026,14)
        self.date3 = month_start(2026,0)

    def test_month_start_functionnality(self):
        self.assertEqual(self.date1.year, 2026)
        self.assertEqual(self.date1.month, 4)
        self.assertEqual(self.date2.year, 2027)
        self.assertEqual(self.date2.month, 2)
        self.assertEqual(self.date3.year, 2025)
        self.assertEqual(self.date3.month, 12)

class UserExpensesPrivacy(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="lara1", password="pass12345")
        self.category1 = Category.objects.create(name="Food", user=self.user1)
        self.expense1 = Expense.objects.create(
            title="Lunch",
            amount="12.50",
            category=self.category1,
            user=self.user1,
            date=timezone.now(),
        )

        self.user2 = User.objects.create_user(username="lara2", password="pass12345")
        self.category2 = Category.objects.create(name="Entertainment", user=self.user2)
        self.expense2 = Expense.objects.create(
            title="Cinema",
            amount="12.50",
            category=self.category2,
            user=self.user2,
            date=timezone.now(),
        )

        # Skip the login flow: make every request act as this user.
        self.client.force_authenticate(user=self.user1)
        # force_authenticate tells the fake client to act as that user.

    def test_user_can_see_only_his_expenses(self):
        response = self.client.get("/expenses/")
        expenses = response.data["results"]

        # Guard: an empty list would make the loop below pass without checking anything.
        self.assertEqual(len(response.data["results"]), 1)
        for exp in expenses:
            self.assertEqual(exp["user"], self.user1.id)

class Scheduled_datesFunctionality(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.category = Category.objects.create(name="Food", user=self.user)
        self.template_daily = RecurrentExpense.objects.create(category=self.category, user=self.user, title= "template daily", amount=50, start_date=date(2026, 1, 1), frequency="daily" )
        # self.daily = scheduled_dates(template=sel)
        self.template_monthly = RecurrentExpense.objects.create(category=self.category, user=self.user, title= "template monthly", amount=50, start_date=date(2026, 1, 1), frequency="monthly" )
        self.template_weekly = RecurrentExpense.objects.create(category=self.category, user=self.user, title= "template weekly", amount=50, start_date=date(2026, 1, 1), frequency="weekly" )

    
    def test_scheduled_dates_function_functionality(self):
        # list(...) collects the values the generator yields one by one.
        daily = list(scheduled_dates(self.template_daily, until_date=date(2026, 1, 3)))
        weekly = list(scheduled_dates(self.template_weekly, until_date=date(2026, 1, 22)))
        monthly = list(scheduled_dates(self.template_monthly, until_date=date(2026, 5, 1)))
        self.assertEqual(daily, [date(2026,1,1), date(2026,1,2), date(2026,1,3)])
        self.assertEqual(weekly, [date(2026,1,1), date(2026,1,8), date(2026,1,15), date(2026,1,22)])
        self.assertEqual(monthly, [date(2026,1,1), date(2026,2,1), date(2026,3,1), date(2026,4,1), date(2026,5,1)])

class GenerateRecurrentExpenses(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.category = Category.objects.create(name="Food", user=self.user)
        self.template_monthly = RecurrentExpense.objects.create(category=self.category, user=self.user, title= "template monthly", amount=50, start_date=date(2026, 1, 1), frequency="monthly" )
        # Skip the login flow: make every request act as this user.
        self.client.force_authenticate(user=self.user)
        # force_authenticate tells the fake client to act as that user.
    def test_genrate_recurrent_expenses(self):
        response1 = self.client.post(f"/recurrent-expenses/generate/",data={
            "until_date": date(2026, 5, 1)
        })
        response2 = self.client.post(f"/recurrent-expenses/generate/")

        response3 =self.client.get(f"/expenses/")

        # First call: Jan, Feb, Mar, Apr, May = 5 new expenses.
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Second call, same data: nothing new, because the dates already exist.
        # this won't work because it will still retuen 201 even if the expenses are not created again
        # self.assertNotEqual(response1.status_code, status.HTTP_201_CREATED)

        # And the database holds exactly 5, not 10.
        response3 = self.client.get("/expenses/")
        self.assertEqual(len(response3.data["results"]), 5)

class TagOwnershipValidationTest(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="lara1", password="pass12345")
        self.tag1 = Tag.objects.create(user= self.user1, name="tag user1")
        self.category1 = Category.objects.create(name="Food", user=self.user1)

        self.user2 = User.objects.create_user(username="lara2", password="pass12345")
        self.tag2 = Tag.objects.create(user= self.user2, name="tag user2")
        self.category2 = Category.objects.create(name="Food", user=self.user2)

    def test_assign_tag_to_expense_happy_flow(self):
        self.client.force_authenticate(user=self.user1)  

        creation_response = self.client.post(f"/expenses/", data={
                                "title":"Lunch",
                                "amount":"12.50",
                                "user" :self.user1.id,
                                "category":self.category1.category_id,
                                "date":timezone.now(),
                                "tags" : [self.tag1.tag_id]
                                            })
        
        self.assertEqual(creation_response.status_code, status.HTTP_201_CREATED)

    def test_tag_ownership_validation_test(self):
        self.client.force_authenticate(user=self.user2)  
        creation_response = self.client.post(f"/expenses/", data={
                                        "title":"Lunch",
                                        "amount":"12.50",
                                        "user" :self.user2.id,
                                        "category":self.category2.category_id,
                                        "date":timezone.now(),
                                        "tags" : [self.tag1.tag_id]
                                                    })
        
        self.assertEqual(creation_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tags", creation_response.data)
        self.assertEqual(Expense.objects.count(), 0)

class ContributionsTest(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="lara1", password="pass12345")

    def test_validation_on_negative_contribution_amount(self):
        self.client.force_authenticate(user=self.user1)  
        created_goal = self.client.post(f"/saving-goals/", data = {
                        "title": "Camera",
                        "target_amount": 500,
                        "target_date": "2027-06-30"
                                      })
        created_contribution = self.client.post(f"/saving-goals/{created_goal.data["goal_id"]}/contributions/",
                            data={
                                    "amount": -20,
                                    "date": "2026-11-04"
                                })
        self.assertEqual(created_contribution.status_code, status.HTTP_400_BAD_REQUEST)

        contributions_list = self.client.get(f"/saving-goals/{created_goal.data["goal_id"]}/contributions/")

        self.assertEqual(len(contributions_list.data), 0)

    def test_contributions_are_separate_per_goal(self):
        self.client.force_authenticate(user=self.user1)
        created_goal1 = self.client.post(f"/saving-goals/", data = {
                                "title": "Camera",
                                "target_amount": 500,
                                "target_date": "2027-06-30"
                                              }) 
        created_contribution1 = self.client.post(f"/saving-goals/{created_goal1.data["goal_id"]}/contributions/",
                                    data={
                                            "amount": 20,
                                            "date": "2026-11-04"
                                        })       
        created_goal2 = self.client.post(f"/saving-goals/", data = {
                                        "title": "Hair Curler",
                                        "target_amount": 100,
                                        "target_date": "2027-06-30"
                                                      }) 
        created_contribution2 = self.client.post(f"/saving-goals/{created_goal2.data["goal_id"]}/contributions/",
                                            data={
                                                    "amount": 20,
                                                    "date": "2026-11-04"
                                                })  
        contributions_list = self.client.get(f"/saving-goals/{created_goal1.data["goal_id"]}/contributions/")
        self.assertEqual(len(contributions_list.data), 1)

class LogoutTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        login = self.client.post(
            "/api/token/",
            {"username": "lara", "password": "pass12345"},
            format="json",
        )
        self.access = login.data["access"]
        self.refresh = login.data["refresh"]

    def test_logout_blacklists_refresh_token(self):
        response = self.client.post(
            "/api/token/logout/",
            {"refresh": self.refresh},
            format="json",
            headers={"Authorization": f"Bearer {self.access}"},
        )
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)

        # The refresh token must not work any more.
        response = self.client.post("/api/token/refresh/", {"refresh": self.refresh}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_without_access_token_is_rejected(self):
        response = self.client.post("/api/token/logout/", {"refresh": self.refresh}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

class ChangePasswordTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        # login = self.client.post(
        #     "/api/token/",
        #     {"username": "lara", "password": "pass12345"},
        #     format="json",
        # )
        # self.access = login.data["access"]
        # self.refresh = login.data["refresh"]
        self.client.force_authenticate(user=self.user)


    def test_new_password_works(self):
        change_pass_response = self.client.post(
                "/users/me/change-password/",
                {"old_password": "pass12345", "new_password": "pass123456", "confirm_password": "pass123456"},
                format="json",
            )
        self.assertEqual(change_pass_response.status_code, status.HTTP_204_NO_CONTENT)

        login_new_pass = self.client.post(
                    "/api/token/",
                    {"username": "lara", "password": "pass123456"},
                    format="json",
                )
        self.assertEqual(login_new_pass.status_code, status.HTTP_200_OK)

        login_old_pass = self.client.post(
                            "/api/token/",
                            {"username": "lara", "password": "pass12345"},
                            format="json",
                        )
        # Wrong credentials on login -> 401 (authentication failed), not 400.
        self.assertEqual(login_old_pass.status_code, status.HTTP_401_UNAUTHORIZED)

        
class HardExpenseDeleteTest(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="lara1", password="pass12345")
        self.category1 = Category.objects.create(name="Food", user=self.user1)
        self.soft_deleted_expense1 = Expense.objects.create(
            title="Lunch",
            amount="12.50",
            category=self.category1,
            user=self.user1,
            date=timezone.now(),
            is_deleted=True,
            deleted_at="2026-11-19T12:43:46.368536Z"
        )
        self.expense1 = Expense.objects.create(
                    title="Lunch",
                    amount="12.50",
                    category=self.category1,
                    user=self.user1,
                    date=timezone.now(),
                )


    def test_hard_delete_solft_Deleted_expense(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(
            f"/expenses/{self.soft_deleted_expense1.expense_id}/trash/",
            format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        get_deleted_expense_response = self.client.get(
            f"/expenses/{self.soft_deleted_expense1.expense_id}/",
            format="json",
            )
        self.assertEqual(get_deleted_expense_response.status_code, status.HTTP_404_NOT_FOUND)
        # The GET above is 404 even before a hard delete (trashed expenses are hidden),
        # so check the database to prove the row is really gone.
        self.assertFalse(Expense.objects.filter(pk=self.soft_deleted_expense1.pk).exists())

        delete_active_expense_response = self.client.delete(f"/expenses/{self.expense1.expense_id}/trash/",
            format="json",
            )
        self.assertEqual(delete_active_expense_response.status_code, status.HTTP_404_NOT_FOUND)
        get_deleted_active_expense_response = self.client.get(
                f"/expenses/{self.expense1.expense_id}/",
                format="json",
                )
        self.assertEqual(get_deleted_active_expense_response.status_code, status.HTTP_200_OK)
        self.assertEqual(get_deleted_active_expense_response.data["expense_id"], str(self.expense1.expense_id))

class DeletedAtTrackingTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.category = Category.objects.create(name="Food", user=self.user)
        self.expense = Expense.objects.create(
            title="Lunch", amount="12.50", category=self.category,
            user=self.user, date=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)

    def test_delete_sets_and_restore_clears_deleted_at(self):
        self.assertIsNone(self.expense.deleted_at)

        # 1. soft delete (DELETE /expenses/<id>/, not /trash/) -> assert 204
        response = self.client.delete(
                    f"/expenses/{self.expense.expense_id}/",
                    format="json",
                    )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # 2. refresh_from_db() updates self.expense in place (it returns None)
        self.expense.refresh_from_db()
        self.assertIsNotNone(self.expense.deleted_at)
        self.assertTrue(self.expense.is_deleted)
        # 3. restore      -> assert 200
        response = self.client.post(
                            f"/expenses/{self.expense.expense_id}/restore/",
                            format="json",
                            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 4. refresh again -> assert is_deleted / deleted_at
        self.expense.refresh_from_db()
        self.assertIsNone(self.expense.deleted_at)
        self.assertFalse(self.expense.is_deleted)

class PurgeTrashCommandTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.category = Category.objects.create(name="Food", user=self.user)
        now = timezone.now()
        self.old_trashed = Expense.objects.create(
            title="Old", amount="10.00", category=self.category, user=self.user,
            date=now, is_deleted=True, deleted_at=now - timedelta(days=31),
        )
        # self.recent_trashed = ...  (5 days ago)
        self.recent_trashed = Expense.objects.create(
                    title="recent trashed", amount="10.00", category=self.category, user=self.user,
                    date=now, is_deleted=True, deleted_at=now - timedelta(days=5),
                )
        # self.active = ...          (not deleted)
        self.active = Expense.objects.create(
                            title="active", amount="10.00", category=self.category, user=self.user,
                            date=now)

    def test_purge_deletes_only_old_trashed_expenses(self):
        call_command("purge_trash", days=30)
        # assert old_trashed is gone:    Expense.objects.filter(pk=...).exists()
        self.assertFalse(Expense.objects.filter(pk=self.old_trashed.expense_id).exists())
        # assert the other two still exist
        self.assertTrue(Expense.objects.filter(pk=self.recent_trashed.expense_id).exists())
        self.assertTrue(Expense.objects.filter(pk=self.active.expense_id).exists())

    def test_purge_dry_run_do_not_delete(self):
        call_command("purge_trash", days=30, dry_run=True)
        self.assertTrue(Expense.objects.filter(pk=self.old_trashed.expense_id).exists())
        self.assertTrue(Expense.objects.filter(pk=self.recent_trashed.expense_id).exists())
        self.assertTrue(Expense.objects.filter(pk=self.active.expense_id).exists())


class CopyPreviousBudgetsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.food = Category.objects.create(name="Food", user=self.user)
        self.rent = Category.objects.create(name="Rent", user=self.user)
        Budget.objects.create(user=self.user, category=self.food, year=2026, month=12, amount="200.00")
        Budget.objects.create(user=self.user, category=self.rent, year=2026, month=1, amount="900.00")
        # Rent budget: January 2026 (wrong year, must not be copied)
        self.client.force_authenticate(user=self.user)

    def test_january_copies_from_previous_december(self):
        response = self.client.post(
            "/budgets/copy-previous/", {"year": 2027, "month": 1}, format="json"
        )
        # assert 201
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["created"]), 1)
        self.assertEqual(response.data["created"][0]['category'], 'Food')

        jan_budgets = Budget.objects.filter(user=self.user, year=2027, month=1)
        self.assertEqual(jan_budgets.count(), 1)
        self.assertEqual(jan_budgets.first().category, self.food)
        self.assertEqual(jan_budgets.first().amount , Decimal("200.00"))

class DuplicateExpenseTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.category = Category.objects.create(name="Food", user=self.user)
        self.existing = Expense.objects.create(
            title="Coffee", amount="4.50", category=self.category,
            user=self.user, date="2026-11-02T08:00:00Z",
        )
        self.client.force_authenticate(user=self.user)
        self.body = {
            "title": "Coffee",
            "amount": "4.50",
            "category": str(self.category.category_id),
            "date": "2026-11-02T16:00:00Z",
        }

    def test_same_day_duplicate_returns_409(self):
        response = self.client.post("/expenses/", self.body, format="json")
        possible_duplicates = response.data['possible_duplicates']
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(len(possible_duplicates), 1)
        self.assertEqual(possible_duplicates[0]["expense_id"] , str(self.existing.expense_id))
        self.assertEqual(Expense.objects.filter(user=self.user).count(), 1)

    def test_force_true_creates_duplicate(self):
        response = self.client.post("/expenses/?force=true", self.body, format="json")
        # assert 201
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # assert user now has 2 expenses
        self.assertEqual(Expense.objects.filter(user=self.user).count(), 2)


class BudgetStatusTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.food = Category.objects.create(name="Food", user=self.user)
        self.rent = Category.objects.create(name="Rent", user=self.user)
        Budget.objects.create(user=self.user, category=self.food, year=2026, month=11, amount="200.00")
        Budget.objects.create(user=self.user, category=self.rent, year=2026, month=11, amount="500.00")

        def add(category, amount, date, **extra):
            Expense.objects.create(title="x", amount=amount, category=category,
                                   user=self.user, date=date, **extra)

        add(self.food, "50.00", "2026-11-03T10:00:00Z")
        add(self.food, "30.00", "2026-11-10T10:00:00Z")
        add(self.food, "100.00", "2026-11-12T10:00:00Z", is_deleted=True)   # trashed
        add(self.food, "70.00", "2026-10-15T10:00:00Z")                     # other month
        # Rent: 600.00 in November
        add(self.rent, "600.00", "2026-11-10T10:00:00Z")
        self.client.force_authenticate(user=self.user)

    def test_budget_status_totals(self):
        response = self.client.get("/budgets/status/?year=2026&month=11")
        # assert 200
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        food, rent = response.data["budgets"]

        self.assertEqual(food["spent"],80.00) 
        self.assertEqual(food["percent_used"],40.00) 
        self.assertFalse(food["is_over_budget"]) 

        self.assertEqual(rent["remaining"], Decimal("0.00"))
        self.assertTrue(rent["is_over_budget"]) 



class SetDefaultPaymentMethodTest(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="lara", password="pass12345")
        self.user_b = User.objects.create_user(username="sam", password="pass12345")
        self.cash = PaymentMethod.objects.create(name="Cash", user=self.user_a, is_default=True)
        self.visa = PaymentMethod.objects.create(name="Visa", user=self.user_a)
        self.b_card = PaymentMethod.objects.create(name="Mastercard", user=self.user_b, is_default=True)
        self.client.force_authenticate(user=self.user_a)

    def test_set_default_unsets_previous_default(self):
        response = self.client.post(f"/payment-methods/{self.visa.payment_method_id}/set-default/")
        # assert 200 and response.data["is_default"] is True
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_default"])
        # refresh visa, cash, b_card
        self.visa.refresh_from_db()
        self.cash.refresh_from_db()
        self.b_card.refresh_from_db()
        # assert visa True, cash False, b_card still True
        self.assertTrue(self.visa.is_default)
        self.assertFalse(self.cash.is_default)
        self.assertTrue(self.b_card.is_default)
        # assert only one default for user_a
        self.assertEqual(PaymentMethod.objects.filter(user=self.user_a, is_default=True).count(), 1)

    def test_cannot_set_another_users_method_as_default(self):
        # post to b_card's set-default -> assert 404
        response = self.client.post(f"/payment-methods/{self.b_card.payment_method_id}/set-default/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # refresh b_card -> still True
        self.b_card.refresh_from_db()
        self.assertTrue(self.b_card.is_default)


class GoalProgressTest(TestCase):          # plain TestCase: no API client needed
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.goal = Goal.objects.create(
            title="Laptop", target_amount=Decimal("1000.00"),
            target_date=date(2027, 6, 1), user=self.user,
        )
        # self.client.force_authenticate(user=self.user_a)

    def contribute(self, amount):
        SavingContribution.objects.create(goal=self.goal, amount=Decimal(amount), date=date(2026, 11, 1))

    def test_no_contributions(self):
        # assert the four properties
        self.assertEqual(self.goal.total_saved, Decimal("0.00"))
        self.assertEqual(self.goal.remaining_amount , Decimal("1000.00"))
        self.assertEqual(self.goal.progress_percentage , Decimal("0.00"))
        self.assertFalse(self.goal.is_completed)
        

    def test_partially_saved(self):
        self.contribute("250.00")
        self.contribute("150.00")
        # assert the four properties
        self.assertEqual(self.goal.total_saved, Decimal("400.00"))
        self.assertEqual(self.goal.remaining_amount , Decimal("600.00"))
        self.assertEqual(self.goal.progress_percentage , Decimal("40.00"))
        self.assertFalse(self.goal.is_completed)

    def test_over_saved_is_capped(self):
        # contribute 800 + 500, assert remaining 0, progress 100, completed True
        self.contribute("800.00")
        self.contribute("500.00")
        self.assertEqual(self.goal.total_saved, Decimal("1300.00"))
        self.assertEqual(self.goal.remaining_amount , Decimal("0.00"))
        self.assertEqual(self.goal.progress_percentage , Decimal("100.00"))
        self.assertTrue(self.goal.is_completed)


class ExpenseNotesTest(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="lara", password="pass12345")
        self.user_b = User.objects.create_user(username="sam", password="pass12345")
        cat_a = Category.objects.create(name="Food", user=self.user_a)
        cat_b = Category.objects.create(name="Misc", user=self.user_b)
        now = timezone.now()
        self.lunch = Expense.objects.create(title="Lunch", amount="12.50", category=cat_a, user=self.user_a, date=now)
        self.trashed = Expense.objects.create(title="Dinner", amount="10.00", category=cat_a, user=self.user_a, date=now, is_deleted=True)
        self.b_expense = Expense.objects.create(title="Lunch", amount="12.50", category=cat_b, user=self.user_b, date=now)
        self.client.force_authenticate(user=self.user_a)

    def notes_url(self, expense):
        return f"/expenses/{expense.expense_id}/notes/"

    def test_add_and_list_note(self): 
        # add notes test
        response = self.client.post(f"/expenses/{self.lunch.expense_id}/notes/", data={
            "content": "Paid with cash"
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["content"], "Paid with cash")
        # get notes test
        response_get_notes = self.client.get(f"/expenses/{self.lunch.expense_id}/notes/")
        self.assertEqual(response_get_notes.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_get_notes.data), 1)
        # notes count test
        response_expense = self.client.get(f"/expenses/{self.lunch.expense_id}/")
        self.assertEqual(response_expense.status_code, status.HTTP_200_OK)
        self.assertEqual(response_expense.data["notes_count"], 1)

    def test_blank_content_rejected(self):
        # add empty notes test
        response_empty = self.client.post(f"/expenses/{self.lunch.expense_id}/notes/", data={
            "content": ""
        })
        self.assertEqual(response_empty.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ExpenseNote.objects.count(), 0)

        # add space as notes content 
        response_space = self.client.post(f"/expenses/{self.lunch.expense_id}/notes/", data={
                    "content": " "
                })
        self.assertEqual(response_space.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ExpenseNote.objects.count(), 0)
    def test_content_length_limit(self):
        #  add notes with 1000 characters
        response_1000 = self.client.post(f"/expenses/{self.lunch.expense_id}/notes/", data={
                     "content": "a"*1000
                 })
        self.assertEqual(response_1000.status_code, status.HTTP_201_CREATED)
        #  add notes with 1001 characters
        response_1001 = self.client.post(f"/expenses/{self.lunch.expense_id}/notes/", data={
                             "content": "a"*1001
                         })
        self.assertEqual(response_1001.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("content", response_1001.data)
    def test_cannot_add_note_to_others_or_trashed_expense(self): 
        # Adding a note to user B's expense returns 404.
        response_user_b = self.client.post(f"/expenses/{self.b_expense.expense_id}/notes/", data={
            "content": "test"
        })
        self.assertEqual(response_user_b.status_code, status.HTTP_404_NOT_FOUND)

        # Adding a note to a trashed expense of your own also returns 404, because add_note only looks at active expenses.
        response_trashed = self.client.post(f"/expenses/{self.trashed.expense_id}/notes/", data={
                    "content": "test"
                })
        self.assertEqual(response_trashed.status_code, status.HTTP_404_NOT_FOUND)
        
class CopyExpenseActionTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.category = Category.objects.create(name="Transport", user=self.user)
        self.work = Tag.objects.create(name="work", user=self.user)
        self.travel = Tag.objects.create(name="travel", user=self.user)
        self.visa = PaymentMethod.objects.create(name="Visa", user=self.user)
        self.taxi = Expense.objects.create(
            title="Taxi", amount=Decimal("25.00"), category=self.category,
            description="Airport", user=self.user, payment_method=self.visa,
            is_favorite=True, date="2026-10-01T09:00:00Z",
        )
        self.taxi.tags.set([self.work, self.travel])
        self.client.force_authenticate(user=self.user)

    def duplicate_url(self, expense):
        return f"/expenses/{expense.expense_id}/duplicate/"

    def test_copies_fields_and_tags_but_not_favorite(self):
        response = self.client.post(self.duplicate_url(self.taxi), format="json")
        # assert 201 and new id != original id
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response.data['expense_id'], str(self.taxi.expense_id))
        # assert copied fields, set(new.tags.all()), is_favorite False
        new = Expense.objects.get(pk=response.data["expense_id"])
        self.assertEqual(new.amount, self.taxi.amount)
        self.assertEqual(new.category, self.taxi.category)
        self.assertEqual(new.title, self.taxi.title)
        self.assertEqual(new.description, self.taxi.description)
        self.assertEqual(new.payment_method, self.taxi.payment_method)
        self.assertEqual(set(new.tags.all()),{self.work, self.travel} )
        self.assertFalse(new.is_favorite)
        # assert ExpenseHistory for new expense with action "created"
        self.assertEqual(ExpenseHistory.objects.get(expense=new.expense_id).action, "created")
        self.assertEqual(ExpenseHistory.objects.all().count(), 1)
        self.assertEqual(Expense.objects.all().count(),2)

        # the original is untouched
        self.taxi.refresh_from_db()
        self.assertTrue(self.taxi.is_favorite)
        self.assertEqual(self.taxi.date, datetime.fromisoformat("2026-10-01T09:00:00Z"))

    
class UpcomingPaymentsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.health = Category.objects.create(name="Health", user=self.user)
        self.fun = Category.objects.create(name="Fun", user=self.user)
        self.today = timezone.localdate()

        self.gym = RecurrentExpense.objects.create(
            title="Gym", amount=Decimal("15.00"), category=self.health, user=self.user,
            frequency="weekly", start_date=self.today,
        )
        # Netflix: monthly, start today + 10, amount 12.99
        self.netflix = RecurrentExpense.objects.create(
            title="Netflix", amount=Decimal("12.99"), category=self.fun, user=self.user,
            frequency="monthly", start_date=self.today + timedelta(days=10),
        )
        # Old plan: monthly, start today + 5, is_active=False
        self.old_plan = RecurrentExpense.objects.create(
            title="Old Plan", amount=Decimal("30.00"), category=self.fun, user=self.user,
            frequency="monthly", start_date=self.today + timedelta(days=5), is_active=False,
        )
        # user B + their own template (must never appear in user A's results)
        self.user_b = User.objects.create_user(username="sam", password="pass12345")
        self.b_category = Category.objects.create(name="Bills", user=self.user_b)
        self.b_template = RecurrentExpense.objects.create(
            title="Sam Rent", amount=Decimal("700.00"), category=self.b_category, user=self.user_b,
            frequency="weekly", start_date=self.today,
        )
        self.client.force_authenticate(user=self.user)

    def test_weekly_and_monthly_within_14_days(self):
        response = self.client.get("/recurrent-expenses/upcoming/?days=14")
        # assert 200
        self.assertEqual(response.status_code, status.HTTP_200_OK )
        titles = [p["title"] for p in response.data["payments"]]
        self.assertEqual(titles.count("Gym"), 3)
        self.assertEqual(titles.count("Netflix"), 1)
        
        # assert "Old plan" not in titles
        self.assertNotIn("Old plan", titles)

class FavoriteExpenseTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        category = Category.objects.create(name="Food", user=self.user)
        now = timezone.now()
        self.lunch = Expense.objects.create(title="Lunch", amount=Decimal("12.50"),
                                            category=category, user=self.user, date=now)
        self.taxi = Expense.objects.create(title="Taxi", amount=Decimal("8.00"),
                                           category=category, user=self.user, date=now)
        self.client.force_authenticate(user=self.user)

    def test_favorite_and_unfavorite(self):
        response = self.client.post(f"/expenses/{self.lunch.expense_id}/favorite/")
        # assert 200 and response.data["is_favorite"] is True
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_favorite"])
        # refresh_from_db, assert True
        self.lunch.refresh_from_db()
        self.assertTrue(self.lunch.is_favorite)
        # unfavorite -> assert 200, False, refresh, False
        response_unfavorite = self.client.post(f"/expenses/{self.lunch.expense_id}/unfavorite/")
        self.assertEqual(response_unfavorite.status_code, status.HTTP_200_OK)
        self.assertFalse(response_unfavorite.data["is_favorite"])
        self.lunch.refresh_from_db()
        self.assertFalse(self.lunch.is_favorite)

    def test_favorites_list_shows_only_favorites(self):
        self.client.post(f"/expenses/{self.lunch.expense_id}/favorite/")
        response = self.client.get("/expenses/favorites/")
        # assert 200, len == 1, title == "Lunch"
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], "Lunch")

class CategoryTotalsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.food = Category.objects.create(name="Food", user=self.user)
        now = timezone.now()
        Expense.objects.create(title="Lunch", amount=Decimal("12.50"),
                               category=self.food, user=self.user, date=now)
        # Dinner: 30.00, active
        Expense.objects.create(title="Dinner", amount=Decimal("30.00"),
                                       category=self.food, user=self.user, date=now)
        # Old: 100.00, is_deleted=True
        Expense.objects.create(title="v", amount=Decimal("100.00"),
                                               category=self.food, user=self.user, date=now, is_deleted=True)
        self.client.force_authenticate(user=self.user)

    def test_totals_ignore_trashed_expenses(self):
        response = self.client.get(f"/categories/{self.food.category_id}/")
        # assert 200
        self.assertEqual(response.status_code,status.HTTP_200_OK)
        # assert expense_count == 2
        self.assertEqual(response.data['expense_count'], 2)
        # assert total_spent == "42.50"
        self.assertEqual(response.data['total_spent'], '42.50')

    def test_empty_category_shows_zero(self):
        travel = Category.objects.create(name="Travel", user=self.user)
        # GET it, assert expense_count == 0 and total_spent == "0.00"
        response = self.client.get(f"/categories/{travel.category_id}/")
        # assert expense_count == 0
        self.assertEqual(response.data['expense_count'], 0)
        # assert total_spent == "00.00"
        self.assertEqual(response.data['total_spent'], '0.00')

class DeleteCategoryTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.food = Category.objects.create(name="Food", user=self.user)
        self.groceries = Category.objects.create(name="Groceries", user=self.user)
        self.travel = Category.objects.create(name="Travel", user=self.user)
        now = timezone.now()
        self.lunch = Expense.objects.create(title="Lunch", amount=Decimal("12.50"),
                                            category=self.food, user=self.user, date=now)
        self.old = Expense.objects.create(title="Old", amount=Decimal("60.00"), category=self.food,
                                          user=self.user, date=now, is_deleted=True)
        # user B + their category self.b_misc
        self.user_b = User.objects.create_user(username="Sam", password="pass12345")
        self.user_b_category = Category.objects.create(name="User B Categ", user=self.user_b)
        self.client.force_authenticate(user=self.user)

    def delete_url(self, category, move_to=None):
        url = f"/categories/{category.category_id}/"
        return f"{url}?move_to={move_to}" if move_to else url

    def test_move_to_moves_expenses_then_deletes(self):
        response = self.client.delete(self.delete_url(self.food, self.groceries.category_id))
        # assert 204
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # assert Food no longer exists
        self.assertEqual(Category.objects.filter(pk=self.food.category_id).count(), 0)
        # refresh lunch and old -> category == self.groceries
        self.lunch.refresh_from_db()
        self.old.refresh_from_db()
        self.assertEqual(self.old.category.category_id, self.groceries.category_id)
        self.assertEqual(self.lunch.category.category_id, self.groceries.category_id)


class BulkExpenseCreateTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.food = Category.objects.create(name="Food", user=self.user)
        self.client.force_authenticate(user=self.user)

    def item(self, title="Lunch", amount="12.50"):
        return {"title": title, "amount": amount,
                "category": str(self.food.category_id), "date": "2026-11-20T12:00:00Z"}

    def bulk(self, items):
        return self.client.post("/expenses/bulk/", items, format="json")

    def test_one_invalid_item_saves_nothing(self):
        response = self.bulk([self.item("Lunch"), self.item("Bad", "-5.00"), self.item("Coffee")])
        # assert 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # assert user has 0 expenses
        self.assertEqual(Expense.objects.all().count(), 0)

    def test_bulk_creates_all(self):
        response = self.bulk([self.item("Lunch"), self.item("Taxi", "8.00"), self.item("Coffee", "3.00")])
        # assert 201
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # assert user has 3 expenses
        self.assertEqual(Expense.objects.all().count(), 3)
        self.assertEqual(len(response.data), 3)

    def test_empty_list_rejected(self):
        response = self.bulk([])
        # assert 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # assert user has 0 expenses
        self.assertEqual(Expense.objects.all().count(), 0)

    def test_more_than_100_rejected(self):
        response = self.bulk(self.item() for _ in range(101))
        # assert 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # assert user has 0 expenses
        self.assertEqual(Expense.objects.all().count(), 0)

    def test_100(self):
        response = self.bulk(self.item() for _ in range(100))
        # assert 201
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # assert user has 100 expenses
        self.assertEqual(Expense.objects.all().count(), 100)
        self.assertEqual(len(response.data), 100)

class ExpenseUpdateHistoryTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.food = Category.objects.create(name="Food", user=self.user)
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/expenses/", {
            "title": "Lunch", "amount": "12.50",
            "category": str(self.food.category_id), "date": "2026-11-20T12:00:00Z",
        }, format="json")
        self.expense = Expense.objects.get(pk=response.data["expense_id"])

    def patch(self, data):
        return self.client.patch(f"/expenses/{self.expense.expense_id}/", data, format="json")

    def history(self):
        return ExpenseHistory.objects.filter(expense=self.expense)

    def test_amount_change_is_recorded(self):
        response = self.patch({"amount": "20.00"})
        # assert 200
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.history().count(), 2)
        updated = self.history().get(action="updated")
        self.assertEqual(updated.old_amount, Decimal("12.50"))
        self.assertEqual(updated.new_amount, Decimal("20.00"))

    def test_title_change_is_not_recorded(self):
        response = self.patch({"title": "Big lunch"})
        # assert 200
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.history().count(), 1)
        created = self.history().get(action="created")
        self.assertIsNotNone(created)

    def test_same_amount_is_not_recorded(self):
        response = self.patch({"amount": "12.50"})
        # assert 200
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.history().count(), 1)
        created = self.history().get(action="created")
        self.assertIsNotNone(created)

    def test_history_endpoint_lists_newest_first(self):
        response1 = self.patch({"amount": "20.00"})
        response2 = self.patch({"amount": "25.00"})
        response = self.client.get(f"/expenses/{self.expense.expense_id}/history/", format="json")
        self.assertEqual(len(response.data), 3)
        self.assertEqual(response.data[0]['new_amount'], '25.00')
        self.assertEqual(response.data[1]['new_amount'], '20.00')
        self.assertEqual(response.data[2]['action'], 'created')


class IncomeSourceTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.user_b = User.objects.create_user(username="sam", password="pass12345")
        self.salary = IncomeSource.objects.create(name="Salary", user=self.user)
        self.b_freelance = IncomeSource.objects.create(name="Freelance", user=self.user_b)
        self.client.force_authenticate(user=self.user)

    def test_duplicate_source_name_returns_400(self):
        response = self.client.post("/income-sources/", {"name": "salary"}, format="json")
        # assert 400 and "name" in response.data   <- fails (500) until the serializer is fixed
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_same_name_allowed_for_different_users(self):
        response = self.client.post("/income-sources/", {"name": "Freelancing"}, format="json")
        self.client.force_authenticate(user=self.user_b)
        response_b = self.client.post("/income-sources/", {"name": "Freelancing"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_b.status_code, status.HTTP_201_CREATED)

    def test_cannot_use_another_users_source(self):
        response = self.client.post("/incomes/", {
            "title": "income1",
            "description": "description blabla",
            "source": str(self.b_freelance.source_id),   # send the ID, not the object
            "amount": "500.00",
            "date": "2026-11-25T12:00:00Z",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("source", response.data)
        # nothing was saved
        self.assertFalse(Income.objects.filter(user=self.user).exists())

    def test_deleting_source_keeps_incomes(self):
        response_create_income = self.client.post("/incomes/", {
                    "title": "income1",
                    "description": "description blabla",
                    "source": str(self.salary.source_id),   # send the ID, not the object
                    "amount": "500.00",
                    "date": "2026-11-25T12:00:00Z",
                }, format="json")
        self.assertEqual(response_create_income.status_code, status.HTTP_201_CREATED)

        income_id = response_create_income.data["income_id"]
        income = Income.objects.get(pk=income_id)
        response_delete_source = self.client.delete(f"/income-sources/{self.salary.source_id}/", format="json")
        self.assertEqual(response_delete_source.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(IncomeSource.objects.filter(pk=self.salary.pk).exists())
        income.refresh_from_db()
        self.assertTrue(Income.objects.filter(pk=income_id).exists())
        self.assertIsNone(income.source)

class GoalFiltersTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        today = timezone.localdate()   # dates relative to today, so the test keeps working next month

        self.laptop = Goal.objects.create(title='Laptop', target_amount=Decimal("1200.00"),
                                          target_date=today + timedelta(days=10), user=self.user)
        self.trip = Goal.objects.create(title='Trip', target_amount=Decimal("2000.00"),
                                        target_date=today + timedelta(days=90), user=self.user)
        self.phone = Goal.objects.create(title='Phone', target_amount=Decimal("800.00"),
                                         target_date=today + timedelta(days=10), user=self.user)
        self.old_goal = Goal.objects.create(title='Old Goal', target_amount=Decimal("2000.00"),
                                            target_date=today - timedelta(days=5), user=self.user)

        self.saving_laptop = SavingContribution.objects.create(goal=self.laptop, amount=Decimal("1200.00"), date=today)
        self.saving_trip = SavingContribution.objects.create(goal=self.trip, amount=Decimal("500.00"), date=today)
        # Phone: no contributions at all (a 0 contribution is not allowed by the model)
        self.saving_old_goal = SavingContribution.objects.create(goal=self.old_goal, amount=Decimal("100.00"), date=today)

        self.client.force_authenticate(user=self.user)

    def test_completed_filter(self):
        response = self.client.get("/saving-goals/?completed=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check the WHOLE result, not just the first item: exactly Laptop, nothing else
        self.assertEqual({g["title"] for g in response.data}, {"Laptop"})

        response = self.client.get("/saving-goals/?completed=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Phone has no contributions and must still be listed as not completed
        self.assertEqual({g["title"] for g in response.data}, {"Trip", "Phone", "Old Goal"})

    def test_upcoming_filter(self):
        response = self.client.get("/saving-goals/?upcoming=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check the WHOLE result, not just the first item: exactly Laptop, nothing else
        self.assertEqual({g["title"] for g in response.data}, {"Laptop", "Phone"})

        response = self.client.get("/saving-goals/?upcoming=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({g["title"] for g in response.data}, {"Trip", "Old Goal"})

    def test_filters_combined(self):
        response = self.client.get("/saving-goals/?completed=false&upcoming=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({g["title"] for g in response.data}, { "Phone"})

    def test_no_filter_returns_all_my_goals(self):
        response = self.client.get("/saving-goals/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Phone has no contributions and must still be listed as not completed
        self.assertEqual({g["title"] for g in response.data}, {"Laptop", "Trip", "Phone", "Old Goal"})

class IncomeFiltersTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.client.force_authenticate(user=self.user)
        self.job = IncomeSource.objects.create(name="Job", user=self.user)
        self.freelance = IncomeSource.objects.create(name="Freelance", user=self.user)
        # Income.date is a DateTimeField, so use timezone.now() (a datetime), not localdate() (a date).
        # Dates are in the past: income is money you already received.
        now = timezone.now()
        self.salary = Income.objects.create(amount=Decimal("2000"), date=now - timedelta(days=40), user=self.user, source=self.job, title="Salary", description="Salary Description")
        self.bonus = Income.objects.create(amount=Decimal("500"), date=now - timedelta(days=10), user=self.user, source=self.job, title="Bonus", description="Bonus Description")
        self.website = Income.objects.create(amount=Decimal("300"), date=now - timedelta(days=5), user=self.user, source=self.freelance, title="Website", description="Website Description")
        self.gift = Income.objects.create(amount=Decimal("50"), date=now, user=self.user, title="Gift", description="Gift Description")  # no source

    def test_amount_range(self):
        response = self.client.get("/incomes/?amount_min=100&amount_max=600")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({income["title"] for income in response.data}, {"Bonus", "Website"})

    def test_amount_min_is_inclusive(self):
        response = self.client.get("/incomes/?amount_min=500")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({income["title"] for income in response.data}, {"Salary", "Bonus"})

    def test_date_range(self):
        # Build the dates from today (same as setUp), never hard-code them:
        # "2026-11-14" only matches Bonus on the day you wrote the test.
        today = timezone.localdate()
        start = (today - timedelta(days=10)).isoformat()   # Bonus's day
        end = (today - timedelta(days=5)).isoformat()      # Website's day
        response = self.client.get(f"/incomes/?start_date={start}&end_date={end}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({income["title"] for income in response.data}, {"Bonus", "Website"})

    def test_filter_by_source(self):
        response = self.client.get(f"/incomes/?source={self.job.source_id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({income["title"] for income in response.data}, {"Salary", "Bonus"})

    def test_combined_filters(self):
        response = self.client.get(f"/incomes/?source={self.job.source_id}&amount_max=1000")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({income["title"] for income in response.data}, {"Bonus"})

    def test_same_income_different_users(self):
        user2 = User.objects.create_user(username="lara2", password="pass12345")
        job2 = IncomeSource.objects.create(name="Job2", user=user2)
        # Salary2 matches the filter below (2000 >= 1000), so only ownership can hide it.
        Income.objects.create(amount=Decimal("2000"), date=timezone.now() - timedelta(days=40), user=user2, source=job2, title="Salary2", description="Salary2 Description")

        response = self.client.get("/incomes/?amount_min=1000")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Compare titles (strings), not the UUID against a list of dicts.
        self.assertEqual({income["title"] for income in response.data}, {"Salary"})

class PaymentMethodsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.client.force_authenticate(user=self.user)
        # Prepare data with the ORM, not the API: setUp should not depend on POST working.
        self.visa = PaymentMethod.objects.create(name="Visa", user=self.user, is_default=True)

    def test_duplicate_name_rejected(self):
        response1 = self.client.post(f"/payment-methods/", data={"name" : "Visa",
                                "is_default" : False})
        response2 = self.client.post(f"/payment-methods/", data={"name" : "Visa",
                                        "is_default" : False})
        self.assertEqual(response1.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_name_allowed_for_other_user(self):
        user2 = User.objects.create_user(username="lara2", password="pass12345")
        response1 = self.client.post("/payment-methods/", data={"name": "Mastercard", "is_default": False})
        self.client.force_authenticate(user=user2)
        response2 = self.client.post("/payment-methods/", data={"name": "Mastercard", "is_default": False})
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

    def test_rename_to_existing_name_rejected(self):
        cash = PaymentMethod.objects.create(name="Cash", user=self.user)
        # PATCH needs the object's id in the URL. "VISA" (other case) also tests case-insensitivity.
        response = self.client.patch(f"/payment-methods/{cash.payment_method_id}/", data={"name": "VISA"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        cash.refresh_from_db()                  # reload from the DB: the name must not have changed
        self.assertEqual(cash.name, "Cash")

    def test_second_default_rejected(self):
        response = self.client.post("/payment-methods/", data={"name": "Cash", "is_default": True})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check the database directly: reload Visa and confirm it is still the default.
        self.visa.refresh_from_db()
        self.assertTrue(self.visa.is_default)
        self.assertEqual(PaymentMethod.objects.filter(user=self.user, is_default=True).count(), 1)
        self.assertFalse(PaymentMethod.objects.filter(user=self.user, name="Cash").exists())

class CopyBudgetsServiceTest(TestCase):
    """Tests the service directly: no URL, no client, no request, no JSON. Just a function call."""
    def setUp(self):
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.food = Category.objects.create(name="Food", user=self.user)
        self.rent = Category.objects.create(name="Rent", user=self.user)
        Budget.objects.create(user=self.user, category=self.food, year=2026, month=10, amount=Decimal("200.00"))
        Budget.objects.create(user=self.user, category=self.rent, year=2026, month=10, amount=Decimal("900.00"))
        # Rent already has a November budget -> must be skipped, not overwritten
        Budget.objects.create(user=self.user, category=self.rent, year=2026, month=11, amount=Decimal("950.00"))

    def test_copies_missing_and_skips_existing(self):
        result = copy_previous_month_budgets(user=self.user, year=2026, month=11)

        # The result holds real Budget objects, so we can check their fields directly
        self.assertEqual([b.category for b in result.created], [self.food])
        self.assertEqual([b.category for b in result.skipped], [self.rent])

        # And the database was really updated
        self.assertTrue(Budget.objects.filter(user=self.user, category=self.food, year=2026, month=11, amount=Decimal("200.00")).exists())
        rent_nov = Budget.objects.get(user=self.user, category=self.rent, year=2026, month=11)
        self.assertEqual(rent_nov.amount, Decimal("950.00"))   # not overwritten with 900


# The test settings use DummyCache; these tests need a real cache, so they use
# an in-process one (never Redis).
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class ExpenseListCacheTest(APITestCase):
    def setUp(self):
        cache.clear()   # LocMemCache lives for the whole test run
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.other = User.objects.create_user(username="sam", password="pass12345")
        self.category = Category.objects.create(name="Food", user=self.user)
        self.expense = Expense.objects.create(
            title="Lunch", amount="12.50", category=self.category, user=self.user, date=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)

    def write(self, method, url, data=None):
        # Invalidation runs on transaction commit. TestCase never commits, so
        # captureOnCommitCallbacks(execute=True) runs those callbacks for us.
        with self.captureOnCommitCallbacks(execute=True):
            return getattr(self.client, method)(url, data, format="json")

    def test_second_request_is_served_from_cache(self):
        self.client.get("/expenses/")
        # A cache hit doesn't touch the database at all.
        with self.assertNumQueries(0):
            response = self.client.get("/expenses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_different_query_params_are_cached_separately(self):
        self.client.get("/expenses/")
        response = self.client.get("/expenses/", {"search": "nothing-matches"})
        self.assertEqual(response.data["count"], 0)

    def test_users_do_not_share_cached_lists(self):
        self.client.get("/expenses/")
        self.client.force_authenticate(user=self.other)
        response = self.client.get("/expenses/")
        self.assertEqual(response.data["count"], 0)

    def test_create_update_delete_invalidate_the_cache(self):
        self.client.get("/expenses/")

        self.write("post", "/expenses/", {
            "title": "Dinner", "amount": "20.00", "category": str(self.category.pk), "date": timezone.now().isoformat(),
        })
        self.assertEqual(self.client.get("/expenses/").data["count"], 2)

        self.write("patch", f"/expenses/{self.expense.pk}/", {"amount": "99.00"})
        lunch = next(e for e in self.client.get("/expenses/").data["results"] if e["title"] == "Lunch")
        self.assertEqual(lunch["amount"], "99.00")

        self.write("delete", f"/expenses/{self.expense.pk}/")
        self.assertEqual(self.client.get("/expenses/").data["count"], 1)

    def test_renaming_category_invalidates_the_cache(self):
        self.client.get("/expenses/")
        self.write("patch", f"/categories/{self.category.pk}/", {"name": "Groceries"})
        result = self.client.get("/expenses/").data["results"][0]
        self.assertEqual(result["category_name"], "Groceries")

    def test_adding_note_invalidates_the_cache(self):
        self.client.get("/expenses/")
        self.write("post", f"/expenses/{self.expense.pk}/notes/", {"content": "paid cash"})
        self.assertEqual(self.client.get("/expenses/").data["results"][0]["notes_count"], 1)

    def test_generating_recurrent_expenses_invalidates_the_cache(self):
        # generate uses bulk_create, which doesn't send signals.
        RecurrentExpense.objects.create(
            category=self.category, user=self.user, title="Rent", amount=50,
            start_date=date(2026, 1, 1), frequency="monthly",
        )
        self.client.get("/expenses/")
        self.write("post", "/recurrent-expenses/generate/", {"until_date": "2026-03-01"})
        self.assertEqual(self.client.get("/expenses/").data["count"], 4)   # Lunch + Jan, Feb, Mar

# Same as ExpenseListCacheTest: the test settings use DummyCache (stores nothing),
# so swap in an in-process cache that really keeps values.
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class TestHeaderExpensesListAfterCaching(APITestCase):
    def setUp(self):
        cache.clear()   # LocMemCache lives for the whole test run: drop other tests' entries
        self.user = User.objects.create_user(username="lara", password="pass12345")
        self.client.force_authenticate(user=self.user)

    def test_hit_miss_header(self):
        response = self.client.get("/expenses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["X-Cache"], "MISS")

        response = self.client.get("/expenses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["X-Cache"], "HIT")

        # Invalidation runs on transaction commit, which never happens inside a
        # TestCase. captureOnCommitCallbacks(execute=True) runs those callbacks.
        with self.captureOnCommitCallbacks(execute=True):
            category = Category.objects.create(name="Food", user=self.user)
            Expense.objects.create(
                title="Lunch",
                amount="12.50",
                category=category,
                user=self.user,
                date=timezone.now(),
            )

        response = self.client.get("/expenses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["X-Cache"], "MISS")
