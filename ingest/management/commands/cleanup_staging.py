import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ingest.models import ScanResult


class Command(BaseCommand):
    help = "Delete discarded ScanResults and orphaned staging images."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Retention period in days (default: 30).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timezone.timedelta(days=days)

        # Delete old discarded ScanResults.
        discarded_qs = ScanResult.objects.filter(
            status="discarded",
            updated_at__lt=cutoff,
        )
        discarded_count = discarded_qs.count()
        discarded_qs.delete()
        self.stdout.write(f"Deleted {discarded_count} discarded scan result(s).")

        # Clean up orphaned staging images.
        staging_dir = os.path.join(settings.BASE_DIR, "tmp", "title_pages")
        orphaned_count = 0
        if os.path.isdir(staging_dir):
            for filename in os.listdir(staging_dir):
                filepath = os.path.join(staging_dir, filename)
                if not os.path.isfile(filepath):
                    continue
                mtime = os.path.getmtime(filepath)
                file_age = timezone.now().timestamp() - mtime
                if file_age > days * 86400:
                    os.remove(filepath)
                    orphaned_count += 1

        self.stdout.write(f"Deleted {orphaned_count} orphaned staging image(s).")
        self.stdout.write(
            self.style.SUCCESS(
                f"Cleanup complete: {discarded_count + orphaned_count} item(s) removed."
            )
        )
