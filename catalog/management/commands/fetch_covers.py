"""Management command to fetch cover images for records missing them."""

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from catalog.models import ExternalIdentifier, Record
from sources.covers import fetch_cover_url_with_delay


class Command(BaseCommand):
    help = "Fetch cover images from Open Library for records that lack one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which records would be checked without making requests.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Records with no cover_url but at least one ExternalIdentifier.
        has_identifier = ExternalIdentifier.objects.filter(record=OuterRef("pk"))
        records = Record.objects.filter(cover_url="").filter(Exists(has_identifier))

        total = records.count()
        already_have = Record.objects.exclude(cover_url="").count()
        found = 0

        if dry_run:
            self.stdout.write(
                f"Dry run: {total} records to check, "
                f"{already_have} already have covers."
            )
            for record in records:
                ids = list(
                    record.external_identifiers.values_list("identifier_type", "value")
                )
                self.stdout.write(f"  {record.record_id}: {ids}")
            return

        for record in records:
            cover_url = fetch_cover_url_with_delay(record)
            if cover_url:
                record.cover_url = cover_url
                record.save(update_fields=["cover_url"])
                found += 1
                self.stdout.write(f"  Found cover for {record.record_id}")
            else:
                self.stdout.write(f"  No cover for {record.record_id}")

        self.stdout.write(
            f"\nDone: {found} covers found, {total} records checked, "
            f"{already_have} already had covers."
        )
