"""End-to-end tests for the review queue."""

from unittest.mock import patch

import pytest
from playwright.sync_api import expect

from catalog.models import Record
from catalog.search import ensure_fts_table
from ingest.models import ScanResult
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
    @patch("ingest.views.fetch_cover_url", return_value="")
    def test_confirm_inside_the_row_creates_the_record(
        self, _cover, page, live_server, staff_user, queued_scan
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
