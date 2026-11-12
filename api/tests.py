from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Category, Expense, RecurrentExpense, Tag, User
from api.views import month_start, scheduled_dates


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

        

      



 