from datetime import datetime

from django.utils import timezone


def month_start(year, month):
    """Aware datetime at midnight on the 1st; month may overflow past 1..12 (e.g. 13 -> next January)."""
    month_index = month - 1
    return timezone.make_aware(datetime(year + month_index // 12, month_index % 12 + 1, 1))
