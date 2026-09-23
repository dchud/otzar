"""Download a dated snapshot from the backup bucket into place.

Used by ``deploy/rebuild.sh --snapshot``. The date is ``YYYY-MM-DD``
for a daily copy under ``snapshots/`` or ``YYYY-MM`` for the copy under
``monthly/``, taken on the 1st of that month (UTC). The database is
written to the configured database path unless ``--output`` names
another, and never over an existing file.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog import backups


class Command(BaseCommand):
    help = "Download a snapshot (YYYY-MM-DD, or YYYY-MM for a monthly one)."

    # The system checks open the database, and opening a SQLite path
    # that does not exist creates an empty file there -- the file this
    # command is about to write, which it then refuses to overwrite.
    requires_system_checks = ()

    def add_arguments(self, parser):
        parser.add_argument("date", help="YYYY-MM-DD or YYYY-MM")
        parser.add_argument(
            "--output",
            type=Path,
            help="Where to write the database (default: the database path).",
        )

    def handle(self, *args, **options):
        bucket = settings.AWS_S3_BACKUP_BUCKET
        if not bucket:
            raise CommandError("AWS_S3_BACKUP_BUCKET is not set")
        try:
            key = backups.parse_snapshot_date(options["date"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        output = options["output"] or backups.database_path()
        try:
            backups.fetch_snapshot(backups.s3_client(), bucket, key, output)
        except backups.BackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"restored s3://{bucket}/{key} to {output}")
