"""End-to-end tests for provenance on a catalog record."""

import pytest
from playwright.sync_api import expect

from catalog.search import ensure_fts_table
from tests.e2e.conftest import login

PROVENANCE = (
    "Inscribed on the flyleaf by Solomon Schechter, Cambridge 1897; "
    "bookplate of the Sassoon family."
)


def add_record_with_provenance(page, live_server, title="Sefer ha-Kuzari"):
    """Enter a record through the manual entry form, with provenance."""
    page.goto(f"{live_server.url}/ingest/new/")
    page.fill("#id_title", title)
    page.fill("#id_provenance", PROVENANCE)
    page.click('button:text("Add record")')
    page.wait_for_url("**/catalog/**", timeout=10000)


@pytest.mark.django_db(transaction=True)
class TestProvenance:
    def test_provenance_entered_in_the_form_shows_on_the_record(
        self, page, live_server, staff_user
    ):
        ensure_fts_table()
        login(page, live_server)

        add_record_with_provenance(page, live_server)

        expect(page.get_by_role("heading", name="Provenance")).to_be_visible()
        expect(page.get_by_text(PROVENANCE)).to_be_visible()

    def test_record_is_findable_by_a_phrase_from_its_provenance(
        self, page, live_server, staff_user
    ):
        ensure_fts_table()
        login(page, live_server)
        add_record_with_provenance(page, live_server)

        page.goto(f"{live_server.url}/search/?q=Schechter")

        expect(page.get_by_text("Sefer ha-Kuzari")).to_be_visible()

    def test_provenance_can_be_added_when_editing_a_record(
        self, page, live_server, sample_record
    ):
        login(page, live_server)

        page.goto(f"{live_server.url}/ingest/edit/{sample_record.record_id}/")
        page.fill("#id_provenance", PROVENANCE)
        page.click('button:text("Save changes")')
        page.wait_for_url("**/catalog/**", timeout=10000)

        expect(page.get_by_text(PROVENANCE)).to_be_visible()

    def test_record_without_provenance_omits_the_section(
        self, page, live_server, sample_record
    ):
        page.goto(
            f"{live_server.url}/catalog/{sample_record.record_id}/"
            f"{sample_record.slug}/"
        )

        expect(page.get_by_role("heading", name="Provenance")).to_have_count(0)
