from django.db import models


class ExpenseQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)

    def for_user(self, user):
        return self.filter(user=user)