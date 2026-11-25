"""Invalidate the cached expense list when data shown in it changes.

Signals don't fire for QuerySet.update() or bulk_create(), so those places
call invalidate_expense_list() themselves.
"""
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from api.cache import invalidate_expense_list
from api.models import Category, Expense, ExpenseNote, PaymentMethod, Tag


# Expense rows themselves, plus the related rows whose fields the serializer shows:
# category_name, payment_method_name and tags. Deleting a Tag removes its
# expense links without sending m2m_changed, so Tag is listed here too.
@receiver([post_save, post_delete], sender=Expense)
@receiver([post_save, post_delete], sender=Category)
@receiver([post_save, post_delete], sender=PaymentMethod)
@receiver([post_save, post_delete], sender=Tag)
def invalidate_on_owned_model_change(sender, instance, **kwargs):
    invalidate_expense_list(instance.user_id)


@receiver(m2m_changed, sender=Expense.tags.through)
def invalidate_on_expense_tags_change(sender, instance, **kwargs):
    # instance is an Expense (expense.tags.set(...)) or a Tag (tag.expenses.add(...)).
    invalidate_expense_list(instance.user_id)


# notes_count is part of the list response.
@receiver([post_save, post_delete], sender=ExpenseNote)
def invalidate_on_note_change(sender, instance, **kwargs):
    user_id = Expense.objects.filter(pk=instance.expense_id).values_list("user_id", flat=True).first()
    invalidate_expense_list(user_id)
