"""Print how old the newest backups in the backup bucket are.

Two lines: the newest object under ``LITESTREAM_REPLICA_PATH``, which
is the last change Litestream uploaded, and the snapshot that
``snapshots/latest.json`` names. Litestream uploads only when the
database changes, so an old replica object on a day nobody catalogs is
not a fault; ``snapshot_db`` is the check that replication works. This
command reads and reports, and fails only when it cannot read the
bucket.
"""

from datetime import UTC, datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.timesince import timesince

from catalog import backups


def describe(moment: datetime, now: datetime) -> str:
    """``2026-09-24T12:00:00Z, 2 hours ago``, in UTC like the keys."""
    stamp = moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    age = timesince(moment, now).replace("\xa0", " ")
    return f"{stamp}, {age} ago"


class Command(BaseCommand):
    help = "Print the age of the newest replica object and snapshot."

    def handle(self, *args, **options):
        bucket = settings.AWS_S3_BACKUP_BUCKET
        if not bucket:
            raise CommandError("AWS_S3_BACKUP_BUCKET is not set")
        client = backups.s3_client()
        now = timezone.now()

        if settings.LITESTREAM_DISABLED:
            self.stdout.write(
                "replica: replication is off (LITESTREAM_DISABLED is set)"
            )
        else:
            prefix = settings.LITESTREAM_REPLICA_PATH + "/"
            where = f"replica s3://{bucket}/{prefix}"
            newest = backups.newest_object(client, bucket, prefix)
            if newest is None:
                self.stdout.write(f"{where}: no objects")
            else:
                when = describe(newest["LastModified"], now)
                self.stdout.write(
                    f"{where}: newest object {newest['Key']}, {when}"
                )

        manifest = backups.latest_manifest(client, bucket)
        if manifest is None:
            self.stdout.write(
                f"snapshot: no s3://{bucket}/{backups.LATEST_KEY}"
            )
        else:
            taken = datetime.fromisoformat(manifest["created_at"])
            self.stdout.write(
                f"snapshot s3://{bucket}/{manifest['key']}: "
                f"taken {describe(taken, now)}, "
                f"{manifest['record_count']} records"
            )
