"""Management command to retroactively clean MARC punctuation from catalog data."""

from django.core.management.base import BaseCommand

from catalog.models import Author, Publisher, Record, Subject
from catalog.utils import strip_marc_punctuation


class Command(BaseCommand):
    help = "Clean trailing MARC punctuation from existing catalog records and related objects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write("DRY RUN — no changes will be saved.\n")

        record_changes = self._clean_records(dry_run)
        author_changes = self._clean_authors(dry_run)
        publisher_changes = self._clean_publishers(dry_run)
        subject_changes = self._clean_subjects(dry_run)

        self.stdout.write("\n--- Summary ---")
        self.stdout.write(f"Records changed:    {record_changes}")
        self.stdout.write(f"Authors changed:    {author_changes}")
        self.stdout.write(f"Publishers changed: {publisher_changes}")
        self.stdout.write(f"Subjects changed:   {subject_changes}")
        total = record_changes + author_changes + publisher_changes + subject_changes
        self.stdout.write(f"Total changes:      {total}")

        if dry_run and total > 0:
            self.stdout.write("\nRe-run without --dry-run to apply changes.")

    def _clean_records(self, dry_run):
        fields = [
            "title",
            "title_romanized",
            "subtitle",
            "place_of_publication",
            "date_of_publication_display",
        ]
        changed = 0
        for record in Record.objects.all():
            dirty = False
            for field in fields:
                old_val = getattr(record, field) or ""
                new_val = strip_marc_punctuation(old_val)
                if new_val != old_val:
                    self.stdout.write(
                        f"  Record {record.record_id} {field}: "
                        f"{old_val!r} -> {new_val!r}"
                    )
                    setattr(record, field, new_val)
                    dirty = True
            if dirty:
                changed += 1
                if not dry_run:
                    record.save()
        return changed

    def _clean_authors(self, dry_run):
        changed = 0
        for author in Author.objects.all():
            dirty = False
            for field in ("name", "name_romanized"):
                old_val = getattr(author, field) or ""
                new_val = strip_marc_punctuation(old_val)
                if new_val != old_val:
                    self.stdout.write(
                        f"  Author pk={author.pk} {field}: {old_val!r} -> {new_val!r}"
                    )
                    setattr(author, field, new_val)
                    dirty = True
            if dirty:
                changed += 1
                if not dry_run:
                    author.save()
        return changed

    def _clean_publishers(self, dry_run):
        changed = 0
        for publisher in Publisher.objects.all():
            dirty = False
            for field in ("name", "name_romanized"):
                old_val = getattr(publisher, field) or ""
                new_val = strip_marc_punctuation(old_val)
                if new_val != old_val:
                    self.stdout.write(
                        f"  Publisher pk={publisher.pk} {field}: "
                        f"{old_val!r} -> {new_val!r}"
                    )
                    setattr(publisher, field, new_val)
                    dirty = True
            if dirty:
                changed += 1
                if not dry_run:
                    publisher.save()
        return changed

    def _clean_subjects(self, dry_run):
        changed = 0
        for subject in Subject.objects.all():
            old_val = subject.heading or ""
            new_val = strip_marc_punctuation(old_val)
            if new_val != old_val:
                self.stdout.write(
                    f"  Subject pk={subject.pk} heading: {old_val!r} -> {new_val!r}"
                )
                subject.heading = new_val
                changed += 1
                if not dry_run:
                    subject.save()
        return changed
