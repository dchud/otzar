"""End-to-end tests for the review queue."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from playwright.sync_api import expect

from catalog.models import Record
from catalog.search import ensure_fts_table
from ingest.models import ScanResult
from ingest.views import LONG_PENDING_DAYS
from tests.e2e.conftest import login

CANDIDATE = {
    "title": "Biblia Hebraica Stuttgartensia",
    "title_alternate": "Torah, Neviim u-Khetuvim",
    "author": "Elliger, Karl",
    "additional_authors": ["Rudolph, Wilhelm"],
    "date": "1994-2003",
    "publisher": "Deutsche Bibelgesellschaft",
    "place": "Stuttgart",
    "language": "ger",
    "series_title": "Biblia Hebraica",
    "series_volume": "4",
    "subjects": ["Bible. Old Testament -- Criticism"],
    "lccn": "75950123",
    "source_catalog": "NLI",
}


@pytest.fixture
def queued_scan(db, staff_user):
    ensure_fts_table()
    return ScanResult.objects.create(
        scan_type="isbn",
        isbn="9783438052285",
        candidate_records=[CANDIDATE],
        scanned_by=staff_user,
    )


@pytest.fixture
def empty_scan(db, staff_user):
    return ScanResult.objects.create(
        scan_type="isbn",
        isbn="9780000000000",
        candidate_records=[],
        scanned_by=staff_user,
    )


@pytest.fixture
def old_scan(db, staff_user):
    """A scan well past LONG_PENDING_DAYS -- old enough that whoever
    took it has plainly moved on."""
    scan = ScanResult.objects.create(
        scan_type="isbn",
        isbn="9780000000099",
        candidate_records=[CANDIDATE],
        scanned_by=staff_user,
    )
    ScanResult.objects.filter(pk=scan.pk).update(
        created_at=timezone.now() - timedelta(days=LONG_PENDING_DAYS + 5)
    )
    scan.refresh_from_db()
    return scan


@pytest.mark.django_db(transaction=True)
class TestQueueRows:
    def test_row_shows_the_match_without_expanding(
        self, page, live_server, staff_user, queued_scan
    ):
        """The columns that decide a match read straight off the row."""
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        row = page.locator(f"#scan-{queued_scan.pk}-row-0")
        expect(row).to_contain_text("Biblia Hebraica Stuttgartensia")
        expect(row).to_contain_text("Elliger, Karl")
        expect(row).to_contain_text("1994-2003")
        expect(row).to_contain_text("Deutsche Bibelgesellschaft")
        expect(row).to_contain_text("NLI")

    def test_clicking_a_row_expands_it_in_place(
        self, page, live_server, staff_user, queued_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        detail = page.locator(f"#scan-{queued_scan.pk}-candidate-0")
        expect(detail).to_be_hidden()

        page.click(f"#scan-{queued_scan.pk}-row-0")

        expect(detail).to_be_visible()
        expect(detail).to_contain_text("Bible. Old Testament")
        expect(detail).to_contain_text("Rudolph, Wilhelm")
        expect(detail).to_contain_text("German")

    def test_clicking_again_collapses_the_row(
        self, page, live_server, staff_user, queued_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        detail = page.locator(f"#scan-{queued_scan.pk}-candidate-0")
        page.click(f"#scan-{queued_scan.pk}-row-0")
        expect(detail).to_be_visible()

        page.click(f"#scan-{queued_scan.pk}-row-0")
        expect(detail).to_be_hidden()


@pytest.mark.django_db(transaction=True)
class TestInlineConfirm:
    def test_confirm_inside_the_row_creates_the_record(
        self, page, live_server, staff_user, queued_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        page.click(f"#scan-{queued_scan.pk}-row-0")
        detail = page.locator(f"#scan-{queued_scan.pk}-candidate-0")
        detail.get_by_role("button", name="Confirm").click()

        page.wait_for_url("**/ingest/queue/", timeout=10000)
        expect(page.locator("text=No pending scans")).to_be_visible()

        record = Record.objects.get(title="Biblia Hebraica Stuttgartensia")
        assert record.subjects.count() == 1
        assert record.authors.count() == 2
        assert "1994" in record.get_date_display()

        queued_scan.refresh_from_db()
        assert queued_scan.status == "confirmed"
        assert queued_scan.created_record == record


@pytest.mark.django_db(transaction=True)
class TestSeeFullRecord:
    def test_see_full_record_reaches_the_review_page(
        self, page, live_server, staff_user, queued_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        page.click(f"#scan-{queued_scan.pk}-row-0")
        detail = page.locator(f"#scan-{queued_scan.pk}-candidate-0")
        detail.get_by_role("button", name="See full record").click()

        page.wait_for_url("**/ingest/confirm/", timeout=10000)
        expect(page.locator("h1")).to_contain_text("Confirm record")
        expect(
            page.locator("text=Biblia Hebraica Stuttgartensia")
        ).to_be_visible()
        expect(page.locator("text=Rudolph, Wilhelm")).to_be_visible()
        expect(page.locator("text=Bible. Old Testament")).to_be_visible()

    def test_candidate_never_travels_through_the_row(
        self, page, live_server, staff_user, queued_scan
    ):
        """Every candidate on this page already lives on the scan
        being rendered, so "See full record" names its pick by index
        rather than carrying a copy of the record with it."""
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")
        page.click(f"#scan-{queued_scan.pk}-row-0")

        assert "candidate_data" not in page.content()


@pytest.mark.django_db(transaction=True)
class TestZeroCandidateScan:
    def test_says_so_without_expanding_anything(
        self, page, live_server, staff_user, empty_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        card = page.locator(f"#scan-{empty_scan.pk}")
        expect(card).to_contain_text("No matching records found")
        expect(card.get_by_role("button", name="Search again")).to_be_visible()
        expect(card.get_by_role("button", name="Discard")).to_be_visible()

    @patch("ingest.views.isbn_lookup")
    def test_search_again_fills_the_row_with_what_it_finds(
        self, mock_lookup, page, live_server, staff_user, empty_scan
    ):
        mock_lookup.return_value = {
            "nli_records": [dict(CANDIDATE)],
            "lc_records": [],
        }

        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        card = page.locator(f"#scan-{empty_scan.pk}")
        card.get_by_role("button", name="Search again").click()

        expect(card).to_contain_text("Biblia Hebraica Stuttgartensia")
        expect(card).not_to_contain_text("No matching records found")

        empty_scan.refresh_from_db()
        assert len(empty_scan.candidate_records) == 1


@pytest.mark.django_db(transaction=True)
class TestQueueVisibilityAcrossUsers:
    """Several people scan while one reviews; that only works if every
    logged-in cataloger sees the whole queue, not just their own scans.
    """

    def test_a_different_cataloger_sees_and_can_discard_the_scan(
        self, page, live_server, staff_user, queued_scan
    ):
        User.objects.create_user(username="cataloger2", password="testpass123")
        login(page, live_server, username="cataloger2", password="testpass123")
        page.goto(f"{live_server.url}/ingest/queue/")

        row = page.locator(f"#scan-{queued_scan.pk}-row-0")
        expect(row).to_be_visible()

        page.get_by_role("button", name="Discard").click()
        page.wait_for_url("**/ingest/queue/", timeout=10000)
        expect(page.get_by_text("No pending scans")).to_be_visible()

        queued_scan.refresh_from_db()
        assert queued_scan.status == "discarded"


@pytest.mark.django_db(transaction=True)
class TestLongPendingScans:
    """A scan nobody finishes stays in the queue forever by design --
    the badge and filter are what tell "kept forever" apart from "kept
    and forgotten."
    """

    def test_the_queue_distinguishes_recent_from_old(
        self, page, live_server, staff_user, queued_scan, old_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        recent_card = page.locator(f"#scan-{queued_scan.pk}")
        old_card = page.locator(f"#scan-{old_scan.pk}")
        expect(recent_card.get_by_text("Long pending")).to_have_count(0)
        expect(old_card.get_by_text("Long pending")).to_be_visible()

    def test_a_recent_only_queue_offers_no_filter(
        self, page, live_server, staff_user, queued_scan
    ):
        """Not a default filter: with nothing old to find, the queue
        does not offer to narrow itself."""
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        expect(page.get_by_role("link", name="long-pending")).to_have_count(0)

    def test_filtering_shows_only_the_old_ones(
        self, page, live_server, staff_user, queued_scan, old_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        page.get_by_role("link", name="long-pending").click()
        page.wait_for_url("**/ingest/queue/?age=old", timeout=10000)

        expect(page.locator(f"#scan-{old_scan.pk}")).to_be_visible()
        expect(page.locator(f"#scan-{queued_scan.pk}")).to_have_count(0)

        # Old scans stay visible without asking -- this is a filter a
        # cataloger reaches for, not one applied on their behalf.
        page.get_by_role("link", name="Show all pending scans").click()
        expect(page.locator(f"#scan-{queued_scan.pk}")).to_be_visible()
        expect(page.locator(f"#scan-{old_scan.pk}")).to_be_visible()

    def test_discarding_from_the_filtered_view_removes_the_scan(
        self, page, live_server, staff_user, old_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/?age=old")

        card = page.locator(f"#scan-{old_scan.pk}")
        card.get_by_role("button", name="Discard").click()

        page.wait_for_url("**/ingest/queue/?age=old", timeout=10000)
        expect(page.locator(f"#scan-{old_scan.pk}")).to_have_count(0)

        old_scan.refresh_from_db()
        assert old_scan.status == "discarded"


@pytest.mark.django_db(transaction=True)
class TestQueueControlsStayInViewport:
    """The badge and the filter link are exactly the kind of addition
    that pushes the narrowest phones still in use into sideways
    scrolling; see TestNothingScrollsSideways in test_site_chrome.py
    for the same check on the pages it covers.

    The candidate table itself is allowed to overflow its own
    ``overflow-x-auto`` wrapper -- that is the documented exception for
    wide content -- so this checks the page, not every element on it.

    Logged in as a plain cataloger rather than ``staff_user``: the
    header's Admin link is a separate, pre-existing overflow at 320px
    that has nothing to do with the queue, and mixing it in here would
    make this test fail for a reason this change did not cause.
    """

    @pytest.mark.parametrize("width", [320, 360, 375, 414])
    def test_the_queue_stays_inside_the_viewport(
        self, page, live_server, queued_scan, old_scan, width
    ):
        User.objects.create_user(username="cataloger", password="testpass123")
        login(page, live_server, username="cataloger", password="testpass123")
        page.set_viewport_size({"width": width, "height": 800})
        page.goto(f"{live_server.url}/ingest/queue/")

        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth"
            " - document.documentElement.clientWidth"
        )
        assert overflow <= 0, (
            f"{width}px: page scrolls sideways by {overflow}px"
        )
