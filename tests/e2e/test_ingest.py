"""End-to-end tests for ingest workflows."""

from unittest.mock import patch

import pytest
from playwright.sync_api import expect

from catalog.models import Record
from catalog.search import ensure_fts_table
from tests.e2e.conftest import login


# Simulated ISBN lookup result (what sources.cascade.isbn_lookup returns)
MOCK_ISBN_RESULT = {
    "nli_records": [
        {
            "title": "The social life of information /",
            "title_alternate": None,
            "author": "Brown, John Seely",
            "author_alternate": None,
            "publisher": "Harvard Business School Press,",
            "place": "Boston :",
            "date": "c2000.",
            "language": "eng",
            "isbn": "0875847625",
            "additional_authors": ["Duguid, Paul,"],
            "subjects": ["Information society", "Information technology"],
            "lccn": "99049068",
            "oclc": "42475952",
            "lc_classification": "HM851 .B76 2000",
            "dewey_classification": "303.48/33",
            "series_title": None,
            "series_volume": None,
            "source_marc": None,
        }
    ],
    "lc_records": [],
}


@pytest.mark.django_db(transaction=True)
class TestIngestLanding:
    def test_ingest_shows_three_methods(self, page, live_server, staff_user):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/")
        expect(page.locator("text=Scan barcode")).to_be_visible()
        expect(page.locator("text=Photograph title page")).to_be_visible()
        expect(page.locator("text=Enter manually")).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestISBNIngestFlow:
    def test_isbn_scan_page_loads(self, page, live_server, staff_user):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")
        expect(page.locator("h1")).to_contain_text("Scan ISBN")
        expect(page.locator('input[name="isbn"]')).to_be_visible()

    @patch("ingest.views.isbn_lookup")
    def test_full_isbn_flow(self, mock_lookup, page, live_server, staff_user):
        """Test the complete ISBN → candidates → confirm → record flow."""
        mock_lookup.return_value = MOCK_ISBN_RESULT
        ensure_fts_table()

        login(page, live_server)

        # Go to ISBN scan page
        page.goto(f"{live_server.url}/ingest/scan/")

        # Enter an ISBN
        page.fill('input[name="isbn"]', "0875847625")
        page.click('button:text("Look up")')

        # Wait for candidates to appear
        page.wait_for_selector("text=The social life of information", timeout=10000)

        # Click the candidate's "Use" button
        page.click('button:text-is("Use")')

        # Should be on confirm page
        page.wait_for_url("**/ingest/confirm/", timeout=5000)
        expect(page.locator("h1")).to_contain_text("Confirm record")
        expect(page.locator("text=The social life of information")).to_be_visible()
        expect(page.locator("text=Brown, John Seely")).to_be_visible()
        expect(page.locator("text=Duguid, Paul")).to_be_visible()
        expect(page.locator("text=Information society")).to_be_visible()
        expect(page.locator("text=0875847625")).to_be_visible()

        # Add a location and confirm
        page.fill('input[name="location_label"]', "Floor 2, Room A")
        page.click('button:text("Add to catalog")')

        # Should redirect to record detail
        page.wait_for_url("**/catalog/**", timeout=5000)
        expect(page.locator("h1")).to_contain_text("The social life of information")

        # Verify the record was created with all data
        record = Record.objects.get(title__contains="social life")
        assert record.authors.count() == 2
        assert record.subjects.count() == 2
        assert record.publishers.count() == 1
        assert record.locations.count() == 1
        assert record.locations.first().label == "Floor 2, Room A"
        assert record.external_identifiers.filter(identifier_type="ISBN").exists()
        assert record.external_identifiers.filter(identifier_type="LCCN").exists()


@pytest.mark.django_db(transaction=True)
class TestManualEntryFlow:
    def test_manual_entry_creates_record(self, page, live_server, staff_user):
        ensure_fts_table()
        login(page, live_server)

        page.goto(f"{live_server.url}/ingest/new/")
        expect(page.locator("h1")).to_contain_text("Add a new record")

        # Fill the form
        page.fill("#id_title", "Test Manual Entry Book")
        page.fill('input[name="author_name"]', "Test Author")
        page.fill("#id_date_of_publication", "2020")
        page.fill("#id_place_of_publication", "New York")
        page.fill('input[name="publisher_name"]', "Test Publisher")
        page.fill('input[name="location_label"]', "Shelf B-3")

        page.click('button:text("Add record")')

        # Should redirect to record detail
        page.wait_for_url("**/catalog/**", timeout=5000)
        expect(page.locator("h1")).to_contain_text("Test Manual Entry Book")

        # Verify record created
        record = Record.objects.get(title="Test Manual Entry Book")
        assert record.authors.first().name == "Test Author"
        assert record.locations.first().label == "Shelf B-3"

    def test_manual_entry_validation(self, page, live_server, staff_user):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/new/")

        # Submit without title — browser native validation prevents submit
        # so we should still be on the same page
        page.click('button:text("Add record")')
        expect(page).to_have_url(f"{live_server.url}/ingest/new/")


@pytest.mark.django_db(transaction=True)
class TestRecordManagement:
    def test_edit_record(self, page, live_server, staff_user, sample_record):
        login(page, live_server)
        page.goto(
            f"{live_server.url}/catalog/{sample_record.record_id}/{sample_record.slug}/"
        )

        # Click edit
        page.click("text=Edit")
        expect(page.locator("h1")).to_contain_text("Edit record")

        # Change title
        page.fill("#id_title", "Updated Title")
        page.click('button:text("Save changes")')

        # Should redirect to detail with new title
        page.wait_for_url("**/catalog/**", timeout=5000)
        expect(page.locator("h1")).to_contain_text("Updated Title")

        # Verify DB
        sample_record.refresh_from_db()
        assert sample_record.title == "Updated Title"

    def test_delete_record(self, page, live_server, staff_user, sample_record):
        login(page, live_server)
        record_id = sample_record.record_id

        page.goto(f"{live_server.url}/catalog/{record_id}/{sample_record.slug}/")

        # Handle the confirm dialog
        page.on("dialog", lambda dialog: dialog.accept())
        page.click("text=Delete")

        # Should redirect to home
        page.wait_for_url(f"{live_server.url}/", timeout=5000)

        # Verify record gone
        assert not Record.objects.filter(record_id=record_id).exists()
