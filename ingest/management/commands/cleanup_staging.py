"""Management command to reclaim staging storage.

Two things accumulate in the staging area and nothing else removes
them:

- ``discarded`` scans, whose rows stay so the queue can tell a rejected
  scan from one never taken;
- image files no row references, which is what deleting a ScanResult
  through the ORM leaves behind -- Django does not delete the file.

A scan awaiting OCR is left alone however long it has sat there. It is
unfinished work rather than rejected work: somebody photographed a book
and did not come back to it, and the difference between that and a scan
they discarded is the whole reason the two statuses exist. Reclaiming
the space is not worth deleting a photograph its owner never chose to
throw away.

Staged images live under ``MEDIA_ROOT/staging/``: ``ScanResult.image``
is written by ``staging_image_path``, which returns
``staging/YYYY/MM/DD/<random>.jpg``. Nothing else writes there.
``catalog.TitlePageImage`` keeps confirmed title pages under
``title-pages/``, outside the swept tree, so the sweep never sees them.

The command reports what it would delete and writes nothing unless
``--apply`` is passed, because none of these deletions can be undone.
"""

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ingest.models import ScanResult

# The one directory under MEDIA_ROOT that staged images land in.
STAGING_DIR = "staging"


def referenced_image_names():
    """Return the storage name of every image a ScanResult holds.

    Read once, before anything is deleted. An orphan is a file that no
    row referenced when the run started, so a file cannot become one
    part-way through a run by having its row deleted a moment earlier.
    """
    return {
        name
        for name in ScanResult.objects.values_list("image", flat=True)
        if name
    }


def staging_files():
    """Yield ``(path, storage name)`` for each file under ``staging/``.

    The storage name is the form ``ScanResult.image`` holds, so the two
    can be compared directly. Sorted for a stable report.
    """
    media_root = Path(settings.MEDIA_ROOT)
    staging = media_root / STAGING_DIR
    if not staging.is_dir():
        return
    for path in sorted(staging.rglob("*")):
        if path.is_file():
            yield path, path.relative_to(media_root).as_posix()


class Command(BaseCommand):
    help = (
        "Delete old discarded scans and orphaned staging images. "
        "Reports what it would delete; pass --apply to delete."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help=(
                "Retention period in days for discarded scans and "
                "orphaned images (default: 30)."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Delete. Without it nothing is removed.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        now = timezone.now()
        cutoff = now - timedelta(days=options["days"])

        if not apply_changes:
            self.stdout.write("REPORT ONLY — nothing will be deleted.\n")

        # Before any row goes. See referenced_image_names.
        referenced = referenced_image_names()

        discarded, discarded_files = self._delete_rows(
            "discarded",
            ScanResult.objects.filter(
                status="discarded", updated_at__lt=cutoff
            ),
            apply_changes,
        )
        orphans = self._delete_orphans(referenced, cutoff, apply_changes)

        total = discarded + orphans
        self.stdout.write("\n--- Summary ---")
        self.stdout.write(f"{'Discarded scans:':<27}{discarded}")
        self.stdout.write(
            f"{'Images held by those rows:':<27}{discarded_files}"
        )
        self.stdout.write(f"{'Orphaned images:':<27}{orphans}")

        if not apply_changes:
            if total:
                self.stdout.write("\nRe-run with --apply to delete.")
            return
        self.stdout.write(
            self.style.SUCCESS(f"\nCleanup complete: {total} item(s) removed.")
        )

    def _delete_rows(self, label, queryset, apply_changes):
        """Delete *queryset* and its files, returning ``(rows, files)``.

        The file goes first and explicitly, because deleting the row
        through the ORM leaves it on disk. A file whose delete fails is
        reported and left; the row still goes, and the next run sweeps
        the file as an orphan once nothing references it.
        """
        rows = 0
        files = 0

        for scan in queryset:
            name = scan.image.name
            self.stdout.write(
                f"  {label} scan {scan.pk} ({name or 'no image'})"
            )
            rows += 1
            if not apply_changes:
                files += bool(name)
                continue
            if name:
                try:
                    scan.image.delete(save=False)
                except OSError as exc:
                    self.stderr.write(f"    could not delete {name}: {exc}")
                else:
                    files += 1
            scan.delete()

        return rows, files

    def _delete_orphans(self, referenced, cutoff, apply_changes):
        """Delete staged files no row references, returning the count.

        Age is the file's mtime rather than a row's timestamp, because
        an orphan has no row to ask.
        """
        cutoff_stamp = cutoff.timestamp()
        removed = 0

        for path, name in staging_files():
            if name in referenced:
                continue
            try:
                if path.stat().st_mtime >= cutoff_stamp:
                    continue
            except OSError:
                # Vanished between the walk and the stat.
                continue
            self.stdout.write(f"  orphan {name}")
            if not apply_changes:
                removed += 1
                continue
            try:
                path.unlink()
            except FileNotFoundError:
                removed += 1
            except OSError as exc:
                self.stderr.write(f"    could not delete {name}: {exc}")
            else:
                removed += 1

        return removed
