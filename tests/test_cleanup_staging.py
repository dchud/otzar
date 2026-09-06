"""Tests for the ``cleanup_staging`` janitor.

Every test here runs a command that deletes files under
``MEDIA_ROOT``, which by default is ``DATA_DIR/media`` -- the
developer's real staging directory. So every test takes the
``media_root`` fixture, including the ones that only exercise rows, and
the command's tests live in this module alone rather than beside the
review-queue tests, where an invocation could be added without that
fixture.
"""

import os
import re
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from ingest.models import ScanResult

# A staged image path in the shape ``staging_image_path`` produces:
# a date tree under ``staging/`` with a random stem.
STAGED = "staging/2026/01/02/8f14e45fceea167a5a36dedd4bea2543.jpg"


@pytest.fixture
def media_root(settings, tmp_path):
    """Point MEDIA_ROOT at a throwaway directory for the whole test."""
    root = tmp_path / "media"
    root.mkdir()
    settings.MEDIA_ROOT = str(root)
    return root


def run(*args):
    """Run the command, returning everything it wrote to stdout."""
    out = StringIO()
    call_command("cleanup_staging", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


def counts(output):
    """Parse the summary block into ``{label: count}``."""
    parsed = {}
    for line in output.splitlines():
        match = re.match(r"^([A-Za-z][^:]*):\s+(\d+)$", line)
        if match:
            parsed[match.group(1)] = int(match.group(2))
    return parsed


def write_file(media_root, name, age_days=0):
    """Write a file under MEDIA_ROOT and backdate its mtime."""
    path = media_root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not really a jpeg")
    stamp = (timezone.now() - timedelta(days=age_days)).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def make_scan(image="", status="pending", age_days=0):
    """Create a ScanResult, backdating ``updated_at`` by *age_days*."""
    scan = ScanResult.objects.create(
        scan_type="ocr", status=status, image=image
    )
    if age_days:
        ScanResult.objects.filter(pk=scan.pk).update(
            updated_at=timezone.now() - timedelta(days=age_days)
        )
    return scan


@pytest.mark.django_db
class TestOrphanSweep:
    def test_orphan_older_than_retention_is_removed(self, media_root):
        path = write_file(media_root, STAGED, age_days=40)

        output = run("--days=30", "--apply")

        assert not path.exists()
        assert STAGED in output
        assert counts(output)["Orphaned images"] == 1

    def test_referenced_file_is_kept(self, media_root):
        path = write_file(media_root, STAGED, age_days=40)
        # A pending scan is never deleted by age, so the only thing
        # that could remove its file is the orphan sweep.
        make_scan(image=STAGED, status="pending", age_days=40)

        output = run("--days=30", "--apply")

        assert path.exists()
        assert counts(output)["Orphaned images"] == 0

    def test_recent_orphan_is_kept(self, media_root):
        path = write_file(media_root, STAGED, age_days=1)

        output = run("--days=30", "--apply")

        assert path.exists()
        assert counts(output)["Orphaned images"] == 0

    def test_files_outside_staging_are_untouched(self, media_root):
        """The sweep is confined to ``staging/``.

        ``catalog.TitlePageImage`` keeps confirmed title pages under
        ``title-pages/``, and no ScanResult references those, so a
        sweep of the whole of MEDIA_ROOT would delete them all.
        """
        path = write_file(
            media_root, "title-pages/2026/01/02/scan.jpg", age_days=400
        )

        run("--days=30", "--apply")

        assert path.exists()


@pytest.mark.django_db
class TestRowCleanup:
    def test_old_discarded_row_goes_with_its_file(self, media_root):
        path = write_file(media_root, STAGED, age_days=40)
        scan = make_scan(image=STAGED, status="discarded", age_days=40)

        output = run("--days=30", "--apply")

        assert not ScanResult.objects.filter(pk=scan.pk).exists()
        assert not path.exists()
        assert counts(output)["Discarded scans"] == 1

    def test_recent_discarded_row_is_kept(self, media_root):
        scan = make_scan(status="discarded")

        run("--days=30", "--apply")

        assert ScanResult.objects.filter(pk=scan.pk).exists()

    def test_pending_row_is_kept(self, media_root):
        scan = make_scan(status="pending", age_days=40)

        run("--days=30", "--apply")

        assert ScanResult.objects.filter(pk=scan.pk).exists()

    def test_stale_awaiting_ocr_row_goes_with_its_file(self, media_root):
        path = write_file(media_root, STAGED, age_days=8)
        scan = make_scan(image=STAGED, status="awaiting_ocr", age_days=8)

        output = run("--days=30", "--stale-ocr-days=7", "--apply")

        assert not ScanResult.objects.filter(pk=scan.pk).exists()
        assert not path.exists()
        assert counts(output)["Stale awaiting_ocr scans"] == 1

    def test_recent_awaiting_ocr_row_is_kept(self, media_root):
        path = write_file(media_root, STAGED, age_days=1)
        scan = make_scan(image=STAGED, status="awaiting_ocr", age_days=1)

        run("--days=30", "--stale-ocr-days=7", "--apply")

        assert ScanResult.objects.filter(pk=scan.pk).exists()
        assert path.exists()

    def test_missing_file_is_tolerated(self, media_root):
        """A row whose file is already gone still gets deleted.

        This is the state a failed file delete leaves behind, and
        MEDIA_ROOT/staging does not exist at all here.
        """
        scan = make_scan(image=STAGED, status="discarded", age_days=40)

        run("--days=30", "--apply")

        assert not ScanResult.objects.filter(pk=scan.pk).exists()

    def test_deleted_rows_file_is_not_counted_as_an_orphan(self, media_root):
        """A file goes because its row went, not because the row vanished.

        The row is old enough to delete and its file is old enough to
        sweep. An implementation that read the set of referenced files
        after deleting rows would find this file unreferenced and call
        it an orphan; reading that set first means the only thing that
        removes it is the row it belongs to.
        """
        path = write_file(media_root, STAGED, age_days=40)
        make_scan(image=STAGED, status="discarded", age_days=40)

        output = run("--days=30", "--apply")

        assert not path.exists()
        assert counts(output)["Orphaned images"] == 0
        assert counts(output)["Images held by those rows"] == 1


@pytest.mark.django_db
class TestDryRun:
    def test_report_is_the_default_and_changes_nothing(self, media_root):
        orphan = write_file(media_root, STAGED, age_days=40)
        kept = write_file(media_root, "staging/2026/09/01/keep.jpg")
        discarded = make_scan(status="discarded", age_days=40)
        stale = make_scan(
            image="staging/2026/09/01/keep.jpg",
            status="awaiting_ocr",
            age_days=8,
        )

        output = run("--days=30", "--stale-ocr-days=7")

        assert orphan.exists()
        assert kept.exists()
        assert ScanResult.objects.filter(pk=discarded.pk).exists()
        assert ScanResult.objects.filter(pk=stale.pk).exists()

        assert "REPORT ONLY" in output
        assert "--apply" in output
        summary = counts(output)
        assert summary["Discarded scans"] == 1
        assert summary["Stale awaiting_ocr scans"] == 1
        assert summary["Orphaned images"] == 1
