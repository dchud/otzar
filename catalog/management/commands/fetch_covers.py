"""Management command to fetch and store cover images for records that
lack one.

Also the backfill path for records that already have a
``cover_url``-style hotlink from before covers were stored locally --
run again, they have no ``RecordCover`` yet, so they are picked up the
same as any other record missing a cover.
"""

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from catalog.models import ExternalIdentifier, Record, RecordCover
from sources.covers import fetch_cover_with_delay


class Command(BaseCommand):
    help = "Fetch and store cover images from Open Library for records that lack one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which records would be checked without making requests.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Records with no stored cover but at least one ExternalIdentifier.
        has_identifier = ExternalIdentifier.objects.filter(
            record=OuterRef("pk")
        )
        records = Record.objects.filter(cover__isnull=True).filter(
            Exists(has_identifier)
        )

        total = records.count()
        already_have = Record.objects.filter(cover__isnull=False).count()
        found = 0

        if dry_run:
            self.stdout.write(
                f"Dry run: {total} records to check, "
                f"{already_have} already have covers."
            )
            for record in records:
                ids = list(
                    record.external_identifiers.values_list(
                        "identifier_type", "value"
                    )
                )
                self.stdout.write(f"  {record.record_id}: {ids}")
            return

        for record in records:
            result = fetch_cover_with_delay(record)
            if result:
                try:
                    RecordCover.store(record, result.url, result.content)
                except Exception as exc:  # noqa: BLE001
                    self.stdout.write(
                        f"  Failed to store cover for "
                        f"{record.record_id}: {exc}"
                    )
                    continue
                found += 1
                self.stdout.write(f"  Found cover for {record.record_id}")
            else:
                self.stdout.write(f"  No cover for {record.record_id}")

        self.stdout.write(
            f"\nDone: {found} covers found, {total} records checked, "
            f"{already_have} already had covers."
        )
