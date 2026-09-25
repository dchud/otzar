"""Take the daily database snapshot and test-restore the replica.

Run once a day by the host's scheduler, and by the deploy before it
replaces the image. It does two things and reports on both:

1. Copies the database with SQLite's online backup API, gzips it and
   uploads it to the backup bucket with a manifest, as laid out in
   ``catalog.backups``.
2. Checks that the replica works: it writes one row, waits for
   Litestream to upload a new object under ``LITESTREAM_REPLICA_PATH``,
   then restores the replica to a scratch file and checks that the copy
   holds that row and passes SQLite's integrity check. Skipped unless
   ``LITESTREAM_MODE`` is ``replicate``.

Both run even when the first fails, so one failure does not hide the
state of the other. When ``BACKUP_PING_URL`` is set, the command
requests it after a run where both succeeded, and requests it with
``/fail`` appended, carrying the errors, after any failure. The service
behind the URL alerts when the success ping is late, which covers a
scheduler that stopped running the command as well as a failed run.
Any failure also exits non-zero.
"""

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog import backups

PING_TIMEOUT_SECONDS = 10


class Command(BaseCommand):
    help = (
        "Upload a dated database snapshot to the backup bucket and "
        "test-restore the Litestream replica."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--replica-timeout",
            type=float,
            default=60.0,
            help=(
                "Seconds to wait for Litestream to upload a new write "
                "(default 60)."
            ),
        )
        parser.add_argument(
            "--restore-timeout",
            type=float,
            default=300.0,
            help="Seconds to allow the test restore (default 300).",
        )

    def handle(self, *args, **options):
        bucket = settings.AWS_S3_BACKUP_BUCKET
        errors = []

        if not bucket:
            errors.append("AWS_S3_BACKUP_BUCKET is not set")
        else:
            client = backups.s3_client()
            # Both handlers catch everything: a failure of any kind has
            # to reach the ping, which is how a person hears of it.
            try:
                snapshot = backups.take_snapshot(client, bucket)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"snapshot failed: {exc}")
            else:
                m = snapshot.manifest
                self.stdout.write(
                    f"snapshot s3://{bucket}/{snapshot.key}: "
                    f"{m['record_count']} records, {m['bytes']} bytes, "
                    f"commit {m['commit'] or 'unknown'}"
                )

            if settings.LITESTREAM_MODE != "replicate":
                self.stdout.write(
                    "replication check skipped: LITESTREAM_MODE is "
                    f"{settings.LITESTREAM_MODE}"
                )
            else:
                path = settings.LITESTREAM_REPLICA_PATH
                try:
                    written_at = backups.check_replication(
                        client,
                        bucket,
                        path,
                        timeout=options["replica_timeout"],
                    )
                    self.stdout.write(
                        f"replication: s3://{bucket}/{path}/ received "
                        "a new write"
                    )
                    count = backups.verify_restore(
                        path,
                        written_at,
                        timeout=options["restore_timeout"],
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"replication check failed: {exc}")
                else:
                    self.stdout.write(
                        f"test restore: {count} records, integrity ok, "
                        "holds the new write"
                    )

        self._ping(errors)
        if errors:
            raise CommandError("; ".join(errors))

    def _ping(self, errors):
        url = settings.BACKUP_PING_URL
        if not url:
            return
        try:
            if errors:
                response = httpx.post(
                    url.rstrip("/") + "/fail",
                    content="\n".join(errors).encode(),
                    timeout=PING_TIMEOUT_SECONDS,
                )
            else:
                response = httpx.get(url, timeout=PING_TIMEOUT_SECONDS)
            # A mistyped check URL answers 404; that ping was not
            # counted, so it is a failure like an unreachable host.
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # The check behind the URL alerts on a missing success ping
            # by itself, so this is reported rather than retried.
            self.stderr.write(f"backup ping failed: {exc}")
            if not errors:
                raise CommandError(f"backup ping failed: {exc}") from exc
