"""End-to-end tests for ingest workflows."""

from unittest.mock import patch

import pytest
from playwright.sync_api import expect

from catalog.models import Record
from catalog.search import ensure_fts_table
from sources.sru import SRUResult
from tests.e2e.conftest import login
from tests.test_marc import DNB_SRU_XML, LC_SUBJECTS_SRU_XML

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


# A German candidate. MARC 008/35-37 says `ger`, not `deu`, and pycountry
# finds that only under `bibliographic`.
MOCK_GERMAN_ISBN_RESULT = {
    "nli_records": [
        {
            "title": "Der Zauberberg",
            "title_alternate": None,
            "author": "Mann, Thomas",
            "author_alternate": None,
            "publisher": "S. Fischer,",
            "place": "Berlin :",
            "date": "1924.",
            "language": "ger",
            "isbn": "9783100480323",
            "additional_authors": [],
            "subjects": ["German fiction"],
            "lccn": None,
            "oclc": None,
            "lc_classification": None,
            "dewey_classification": None,
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
        page.wait_for_selector(
            "text=The social life of information", timeout=10000
        )

        # Click the candidate's "Use" button
        page.click('button:text-is("Use")')

        # Should be on confirm page
        page.wait_for_url("**/ingest/confirm/", timeout=5000)
        expect(page.locator("h1")).to_contain_text("Confirm record")
        expect(
            page.locator("text=The social life of information")
        ).to_be_visible()
        expect(page.locator("text=Brown, John Seely")).to_be_visible()
        expect(page.locator("text=Duguid, Paul")).to_be_visible()
        expect(page.locator("text=Information society")).to_be_visible()
        expect(page.locator("text=0875847625")).to_be_visible()

        # Add a location and confirm
        page.fill('input[name="location_label"]', "Floor 2, Room A")
        page.click('button:text("Add to catalog")')

        # Should redirect to record detail
        page.wait_for_url("**/catalog/**", timeout=5000)
        expect(page.locator("h1")).to_contain_text(
            "The social life of information"
        )

        # Verify the record was created with all data
        record = Record.objects.get(title__contains="social life")
        assert record.authors.count() == 2
        assert record.subjects.count() == 2
        assert record.publishers.count() == 1
        assert record.locations.count() == 1
        assert record.locations.first().label == "Floor 2, Room A"
        assert record.external_identifiers.filter(
            identifier_type="ISBN"
        ).exists()
        assert record.external_identifiers.filter(
            identifier_type="LCCN"
        ).exists()

    @patch("ingest.views.isbn_lookup")
    def test_confirm_shows_language_name(
        self, mock_lookup, page, live_server, staff_user
    ):
        """The confirm page names the language rather than showing its code."""
        mock_lookup.return_value = MOCK_GERMAN_ISBN_RESULT
        ensure_fts_table()

        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")
        page.fill('input[name="isbn"]', "9783100480323")
        page.click('button:text("Look up")')

        page.wait_for_selector("text=Der Zauberberg", timeout=10000)
        page.click('button:text-is("Use")')
        page.wait_for_url("**/ingest/confirm/", timeout=5000)

        language = page.locator("h3", has_text="Language").locator(
            "xpath=following-sibling::p[1]"
        )
        expect(language).to_have_text("German")


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

    def test_edit_form_shows_language_name(
        self, page, live_server, staff_user, german_record
    ):
        """The language box on the entry form names the stored code."""
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/edit/{german_record.record_id}/")

        expect(page.locator("#language-search")).to_have_attribute(
            "placeholder", "ger \u2014 German"
        )

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

        page.goto(
            f"{live_server.url}/catalog/{record_id}/{sample_record.slug}/"
        )

        # Handle the confirm dialog
        page.on("dialog", lambda dialog: dialog.accept())
        page.click("text=Delete")

        # Should redirect to home
        page.wait_for_url(f"{live_server.url}/", timeout=5000)

        # Verify record gone
        assert not Record.objects.filter(record_id=record_id).exists()


@pytest.mark.django_db(transaction=True)
class TestMarcParsingOnConfirmPage:
    """What the parser makes of a MARC record is what the user reads.

    These drive the ISBN flow with the SRU response stubbed rather than
    the lookup result, so sources.marc does its real work in between.
    The records come from the parser's own tests: one copy of each
    record shape, exercised at both levels.
    """

    def _look_up(self, page, live_server, isbn):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")
        page.fill('input[name="isbn"]', isbn)
        page.click('button:text("Look up")')
        page.click('button:text-is("Use")')
        page.wait_for_url("**/ingest/confirm/", timeout=10000)

    @patch("sources.cascade.dnb_client.search")
    @patch("sources.cascade.lc_client.search")
    @patch("sources.cascade.nli_client.search")
    def test_no_non_sorting_delimiters_reach_the_page(
        self, mock_nli, mock_lc, mock_dnb, page, live_server, staff_user
    ):
        mock_nli.return_value = SRUResult(success=False, error="no match")
        mock_lc.return_value = SRUResult(success=False, error="no match")
        mock_dnb.return_value = SRUResult(success=True, data=DNB_SRU_XML)
        ensure_fts_table()

        self._look_up(page, live_server, "9783123456789")

        title = page.locator("h2.text-xl").first.inner_text()
        assert "The Complete Piano Etudes" in title
        assert not any(0x80 <= ord(char) <= 0x9F for char in title)

        series = page.locator("text=Klavierbibliothek").inner_text()
        assert not any(0x80 <= ord(char) <= 0x9F for char in series)

    @patch("ingest.views.fetch_cover_url")
    @patch("sources.cascade.dnb_client.search")
    @patch("sources.cascade.lc_client.search")
    @patch("sources.cascade.nli_client.search")
    def test_each_subject_listed_once_with_its_subdivisions(
        self,
        mock_nli,
        mock_lc,
        mock_dnb,
        mock_cover,
        page,
        live_server,
        staff_user,
    ):
        mock_nli.return_value = SRUResult(success=False, error="no match")
        mock_dnb.return_value = SRUResult(success=False, error="no match")
        mock_lc.return_value = SRUResult(
            success=True, data=LC_SUBJECTS_SRU_XML
        )
        mock_cover.return_value = ""
        ensure_fts_table()

        self._look_up(page, live_server, "9780123456789")

        assert page.locator("ul.text-sm li").all_inner_texts() == [
            "Jews -- Israel -- History.",
            "Jews -- Social life and customs.",
            "Judaism.",
            "Jews",
            "Passover -- Juvenile literature.",
        ]

        page.click('button:text("Add to catalog")')
        page.wait_for_url("**/catalog/**", timeout=10000)

        record = Record.objects.get(title__contains="Jewish life")
        assert sorted(record.subjects.values_list("heading", flat=True)) == [
            "Jews",
            "Jews -- Israel -- History",
            "Jews -- Social life and customs",
            "Judaism",
            "Passover -- Juvenile literature",
        ]
        expect(page.locator("text=Jews -- Israel -- History")).to_be_visible()
