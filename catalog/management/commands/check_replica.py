"""Decide whether the app may start against the backup bucket.

Run by ``entrypoint.sh`` at every start, after it writes the Litestream
configuration and before it restores. Exits non-zero to stop a start
that would serve or replicate the wrong data:

- ``LITESTREAM_REPLICA_PATH`` names a path older than the newest one in
  the bucket. A rebuild moves replication to a new path and records it
  only in the instance's ``.env``; an instance rebuilt after losing the
  machine starts with a fresh ``.env`` that names the first path.
- There is no database on disk and nothing to restore it from, while
  the bucket holds a replica somewhere. Only the very first start of a
  deployment finds ``litestream/`` empty.
- The database on disk is behind its replica, as after starting from
  an older copy of the disk. Litestream would replicate it over the
  newer state.

With a database on disk, a question it cannot answer (the bucket or
Litestream unreachable, no position recorded) is reported and the start
goes ahead: the database is there, and refusing would turn a passing
fault into an outage. Without one, the same failures stop the start,
since the restore that follows could not work either.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog import backups


class Command(BaseCommand):
    help = (
        "Check LITESTREAM_REPLICA_PATH and the database on disk against "
        "the replicas in the backup bucket before the app starts."
    )
    # The system checks open the database, and opening it creates an
    # empty file where a missing one should be restored; the restore
    # then finds a file and skips.
    requires_system_checks = ()

    def add_arguments(self, parser):
        parser.add_argument(
            "--config",
            default="/etc/litestream.yml",
            help="The Litestream configuration entrypoint.sh wrote.",
        )

    def handle(self, *args, **options):
        bucket = settings.AWS_S3_BACKUP_BUCKET
        if settings.LITESTREAM_MODE == "off" or not bucket:
            self.say("Litestream is off; nothing to check")
            return

        configured = settings.LITESTREAM_REPLICA_PATH
        if backups.replica_path_age(configured) is None:
            raise CommandError(
                f"LITESTREAM_REPLICA_PATH is {configured}, which is not a "
                f"replica path: expected {backups.FIRST_REPLICA_PATH} or "
                f"{backups.FIRST_REPLICA_PATH}-<UTC stamp>, as rebuild "
                "writes"
            )
        database = backups.database_path()
        on_disk = database.exists()
        root = f"s3://{bucket}/{backups.REPLICA_ROOT}"

        try:
            paths = backups.replica_paths(backups.s3_client(), bucket)
        except Exception as exc:  # any failure to list is the same answer
            if not on_disk:
                raise CommandError(
                    f"no database on disk, and {root} cannot be listed: {exc}"
                ) from exc
            self.say(
                f"warning: {root} cannot be listed ({exc}); starting on "
                "the database on disk unchecked",
                error=True,
            )
            return

        newest = backups.newest_replica_path(paths)
        if newest and backups.replica_path_age(
            configured
        ) < backups.replica_path_age(newest):
            raise CommandError(
                f"LITESTREAM_REPLICA_PATH is {configured}, but the newest "
                f"replica is {root}{newest.removeprefix(backups.REPLICA_ROOT)}"
                ". A rebuild moved replication there. Set "
                f"LITESTREAM_REPLICA_PATH={newest} in .env and start again."
            )

        if not on_disk:
            if configured in paths:
                self.say(f"restoring the database from {configured}")
            elif not paths:
                self.say(f"{root} is empty; starting a new, empty database")
            else:
                raise CommandError(
                    f"no database on disk and nothing under {configured} "
                    f"to restore it from, while {root} holds "
                    f"{', '.join(sorted(paths))}. Starting would serve an "
                    "empty catalog."
                )
            return

        if settings.LITESTREAM_MODE == "restore-only":
            self.say(
                "database on disk; restore-only, so nothing is replicated"
            )
            return
        if configured not in paths:
            # A rebuild's new path, or a bucket without a replica yet.
            self.say(f"replicating the database on disk into {configured}")
            return
        self.check_position(database, Path(options["config"]), configured)

    def check_position(self, database, config, configured):
        local = backups.local_txid(database)
        try:
            remote = backups.replica_txid(database, config)
        except backups.BackupError as exc:
            self.say(
                f"warning: {exc}; starting on the database on disk unchecked",
                error=True,
            )
            return
        if local is None or remote is None:
            self.say(
                "warning: no replication position recorded "
                f"({'on disk' if local is None else 'in the replica'}); "
                "starting on the database on disk unchecked",
                error=True,
            )
            return
        if local < remote:
            raise CommandError(
                f"the database on disk is behind its replica at "
                f"{configured} (transaction {local:#x} against {remote:#x}),"
                " as after starting from an older copy of the disk. "
                "Replicating it would overwrite the newer state. Run "
                "just rebuild --latest."
            )
        self.say(
            f"database on disk at transaction {local:#x}, replica at "
            f"{remote:#x}; replicating into {configured}"
        )

    def say(self, message, error=False):
        stream = self.stderr if error else self.stdout
        stream.write(f"check_replica: {message}")
