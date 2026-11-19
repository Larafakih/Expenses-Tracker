from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import Expense


class Command(BaseCommand):
    help = "Permanently delete expenses that have been in the trash longer than --days."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Delete expenses trashed more than this many days ago (default: 30).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show how many expenses would be deleted.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 0:
            self.stderr.write("--days must be 0 or more.")
            return

        cutoff = timezone.now() - timedelta(days=days)
        expenses = Expense.objects.deleted().filter(deleted_at__lt=cutoff)

        if options["dry_run"]:
            self.stdout.write(f"{expenses.count()} expenses would be purged (trashed before {cutoff:%Y-%m-%d %H:%M}).")
            return

        # delete() returns (total rows incl. cascaded history/notes/receipts, {model: count})
        _, per_model = expenses.delete()
        count = per_model.get("api.Expense", 0)
        self.stdout.write(self.style.SUCCESS(f"Purged {count} expenses."))
