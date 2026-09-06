"""End-to-end tests for the marks of ownership a copy carries.

A bookplate, a dedication and a stamp are entered on the record form,
read on the record page under Provenance, and reach search.
"""

import pytest
from playwright.sync_api import expect

from catalog.search import ensure_fts_table
from tests.e2e.conftest import login

MARKS = {
    "bookplate_text": "Ex libris David Solomon Sassoon",
    "dedication_text": (
        "To Rivka, on her wedding day,\nfrom her father, Warsaw 1932."
    ),
    "stamp_text": "Alliance Israelite Universelle, Paris",
}


def add_record_with_marks(page, live_server, title="Sefer ha-Kuzari"):
    """Enter a record through the manual entry form, with every mark."""
    page.goto(f"{live_server.url}/ingest/new/")
    page.fill("#id_title", title)
    for field, value in MARKS.items():
        page.fill(f"#id_{field}", value)
    page.click('button:text("Add record")')
    page.wait_for_url("**/catalog/**", timeout=10000)


@pytest.mark.django_db(transaction=True)
class TestOwnershipMarks:
    def test_marks_entered_in_the_form_show_on_the_record(
        self, page, live_server, staff_user
    ):
        ensure_fts_table()
        login(page, live_server)

        add_record_with_marks(page, live_server)

        expect(page.get_by_role("heading", name="Provenance")).to_be_visible()
        for label in ("Bookplate", "Dedication", "Stamp"):
            expect(page.get_by_text(label, exact=True)).to_be_visible()
        expect(page.get_by_text(MARKS["bookplate_text"])).to_be_visible()
        expect(page.get_by_text(MARKS["stamp_text"])).to_be_visible()
        expect(
            page.get_by_text("from her father, Warsaw 1932.")
        ).to_be_visible()

    @pytest.mark.parametrize(
        "term", ["Sassoon", "Rivka", "Universelle"], ids=list(MARKS)
    )
    def test_a_record_is_findable_by_a_phrase_from_one_mark(
        self, page, live_server, staff_user, term
    ):
        ensure_fts_table()
        login(page, live_server)
        add_record_with_marks(page, live_server)

        page.goto(f"{live_server.url}/search/?q={term}")

        expect(page.get_by_text("Sefer ha-Kuzari")).to_be_visible()

    def test_marks_can_be_added_when_editing_a_record(
        self, page, live_server, sample_record
    ):
        login(page, live_server)

        page.goto(f"{live_server.url}/ingest/edit/{sample_record.record_id}/")
        page.fill("#id_stamp_text", MARKS["stamp_text"])
        page.click('button:text("Save changes")')
        page.wait_for_url("**/catalog/**", timeout=10000)

        expect(page.get_by_text(MARKS["stamp_text"])).to_be_visible()

    def test_a_record_with_no_marks_omits_the_section(
        self, page, live_server, sample_record
    ):
        page.goto(
            f"{live_server.url}/catalog/{sample_record.record_id}/"
            f"{sample_record.slug}/"
        )

        expect(page.get_by_role("heading", name="Provenance")).to_have_count(0)
