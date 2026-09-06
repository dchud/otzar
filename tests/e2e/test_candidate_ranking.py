"""End-to-end tests: catalog candidates ordered by agreement with the page."""

import os
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from playwright.sync_api import expect

from catalog.models import Record
from catalog.search import ensure_fts_table
from ingest.models import ScanResult
from sources.cascade import CascadeResult
from sources.marc import extract_marc_records, parse_record
from tests import test_marc as marc_fixtures
from tests.e2e.conftest import login

FIXTURE_IMAGE = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "title_pages", "blank.jpg"
)

# What the OCR reads off the title page of the LC fixture's book. The
# date is the one field that disagrees with the record, so the row
# shows both kinds of verdict.
PAGE = {
    "title": "איש ההלכה",
    "subtitle": None,
    "author": "יוסף דב סולובייצ'יק",
    "publisher": "Sefer Press",
    "place": "Jerusalem",
    "date": "1990",
    "title_romanized": "Halakhic man",
    "author_romanized": "Joseph Dov Soloveitchik",
}


def _parsed(sru_xml: str) -> dict:
    _, records = extract_marc_records(sru_xml)
    return parse_record(records[0])


@pytest.mark.django_db(transaction=True)
class TestCandidateRanking:
    """NLI used to come first whatever the page said; now the match does."""

    def _pending_scan(self, staff_user):
        scan = ScanResult.objects.create(
            scan_type="ocr",
            status="pending",
            ocr_output=PAGE,
            scanned_by=staff_user,
        )
        with open(FIXTURE_IMAGE, "rb") as fh:
            scan.image.save("blank.jpg", ContentFile(fh.read()))
        return scan

    def _search(self, page, live_server, scan):
        page.goto(f"{live_server.url}/ingest/scan-title/")
        expect(page.locator(f"#title-page-card-{scan.pk}")).to_be_visible(
            timeout=10000
        )
        page.click('button:text("Continue editing")')
        expect(page.locator("text=Extracted metadata")).to_be_visible(
            timeout=10000
        )
        page.click('#search-controls button[type="submit"]')
        expect(page.locator("table")).to_be_visible(timeout=10000)

    def test_best_match_comes_first_across_catalogs(
        self, page, live_server, staff_user
    ):
        ensure_fts_table()
        scan = self._pending_scan(staff_user)
        login(page, live_server)

        with (
            patch("ingest.views.search_nli") as mock_nli,
            patch("ingest.views.search_lc") as mock_lc,
        ):
            mock_nli.return_value = CascadeResult(
                records=[_parsed(marc_fixtures.NLI_SRU_XML)]
            )
            mock_lc.return_value = CascadeResult(
                records=[_parsed(marc_fixtures.LC_SRU_XML)]
            )
            self._search(page, live_server, scan)

        expect(page.locator("text=Ordered by agreement")).to_be_visible()

        rows = page.locator("table tbody tr")
        expect(rows).to_have_count(2)
        expect(rows.nth(0)).to_contain_text("Halakhic man")
        expect(rows.nth(0)).to_contain_text("LC")
        expect(rows.nth(1)).to_contain_text("מאה שערים")
        expect(rows.nth(1)).to_contain_text("NLI")

        # Each row says why it sits where it does.
        first = rows.nth(0)
        expect(first.locator('[data-verdict="agreed"]')).to_have_text(
            ["title", "author", "publisher", "place"]
        )
        expect(first.locator('[data-verdict="disagreed"]')).to_have_text(
            ["date"]
        )
        second = rows.nth(1)
        expect(second.locator('[data-verdict="agreed"]')).to_have_count(0)

        # The list is evidence, not a decision: every row still offers
        # its own Use button and nothing has been chosen.
        expect(
            page.locator('table tbody tr button:text-is("Use")')
        ).to_have_count(2)

        # Using the first row confirms the record that was shown first,
        # so the stored order is the shown order.
        first.locator('button:text-is("Use")').click()
        page.wait_for_url("**/ingest/confirm/", timeout=5000)
        expect(page.locator("h1")).to_contain_text("Confirm record")
        expect(page.locator("text=Halakhic man")).to_be_visible()
        page.click('button:text("Add to catalog")')
        page.wait_for_url("**/catalog/**", timeout=5000)

        record = Record.objects.get(title__contains="Halakhic man")
        assert record.source_catalog == "LC"
        scan.refresh_from_db()
        assert scan.status == "confirmed"
        assert scan.selected_candidate_index == 0
        assert scan.created_record == record
        assert scan.candidate_records[0]["source_catalog"] == "LC"
