"""End-to-end tests for reusing an existing author on the confirm page.

One person reaches the catalog under two headings -- romanized from the
Library of Congress, Hebrew from the National Library of Israel -- and
confirming both editions used to leave two Author rows for that person.
The confirm page offers the rows it already has so the cataloguer can
say which one this is.
"""

from unittest.mock import patch

import pytest
from playwright.sync_api import expect

from catalog.models import Author, Record
from catalog.search import ensure_fts_table
from tests.e2e.conftest import login

LC_AUTHOR = "Shneur Zalman, of Lyady"
NLI_AUTHOR = "שניאור זלמן מלאדי"


def isbn_result(author, author_alternate, title="Likute amarim (Tanya) /"):
    """One NLI candidate carrying the author headings under test."""
    return {
        "nli_records": [
            {
                "title": title,
                "title_alternate": None,
                "author": author,
                "author_alternate": author_alternate,
                "publisher": "Kehot,",
                "place": "Brooklyn :",
                "date": "1984.",
                "language": "heb",
                "isbn": "9780826604118",
                "additional_authors": [],
                "subjects": ["Hasidism"],
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


def reach_confirm_page(page, live_server):
    """Drive the ISBN route as far as the confirm page."""
    login(page, live_server)
    page.goto(f"{live_server.url}/ingest/scan/")
    page.fill('input[name="isbn"]', "9780826604118")
    page.click('button:text("Look up")')
    page.wait_for_selector("text=Likute amarim", timeout=10000)
    page.click('button:text-is("Use")')
    page.wait_for_url("**/ingest/confirm/", timeout=5000)


@pytest.mark.django_db(transaction=True)
class TestAuthorMatchOnConfirm:
    @patch("ingest.views.isbn_lookup")
    def test_no_match_leaves_the_confirm_page_alone(
        self, mock_lookup, page, live_server, staff_user
    ):
        """Nothing to offer means nothing on the page."""
        mock_lookup.return_value = isbn_result(
            f"{LC_AUTHOR}, 1745-1812.", NLI_AUTHOR
        )
        ensure_fts_table()
        Author.objects.create(name="Elliger, Karl")

        reach_confirm_page(page, live_server)

        expect(page.locator('input[name="author_choice"]')).to_have_count(0)

        page.click('button:text("Add to catalog")')
        page.wait_for_url("**/catalog/**", timeout=5000)

        record = Record.objects.get(title__startswith="Likute")
        assert record.authors.count() == 1
        assert record.authors.first().name == f"{LC_AUTHOR}, 1745-1812"

    @patch("ingest.views.isbn_lookup")
    def test_choosing_an_offered_author_files_the_book_under_it(
        self, mock_lookup, page, live_server, staff_user
    ):
        """A variant hit is offered, and picking it reuses the row.

        The existing row came from a Library of Congress record, which
        filed the linked Hebrew heading as a variant name. This edition
        arrives from the National Library of Israel under that Hebrew
        heading alone, so nothing matches by name.
        """
        mock_lookup.return_value = isbn_result(f"{NLI_AUTHOR}.", None)
        ensure_fts_table()
        existing = Author.objects.create(
            name=LC_AUTHOR, variant_names=[NLI_AUTHOR]
        )

        reach_confirm_page(page, live_server)

        choices = page.locator('input[name="author_choice"]')
        expect(choices).to_have_count(2)
        expect(page.locator(f"text={LC_AUTHOR}")).to_be_visible()

        # Nothing is chosen for the cataloguer on a variant-only hit.
        offered = page.locator(
            f'input[name="author_choice"][value="{existing.pk}"]'
        )
        expect(offered).not_to_be_checked()
        expect(
            page.locator('input[name="author_choice"][value="new"]')
        ).to_be_checked()

        offered.check()
        page.click('button:text("Add to catalog")')
        page.wait_for_url("**/catalog/**", timeout=5000)

        record = Record.objects.get(title__startswith="Likute")
        assert list(record.authors.all()) == [existing]
        assert Author.objects.count() == 1

    @patch("ingest.views.isbn_lookup")
    def test_declining_the_offer_creates_a_separate_author(
        self, mock_lookup, page, live_server, staff_user
    ):
        """Two people can share a name form; the cataloguer decides."""
        mock_lookup.return_value = isbn_result(f"{NLI_AUTHOR}.", None)
        ensure_fts_table()
        Author.objects.create(name=LC_AUTHOR, variant_names=[NLI_AUTHOR])

        reach_confirm_page(page, live_server)

        page.locator('input[name="author_choice"][value="new"]').check()
        page.click('button:text("Add to catalog")')
        page.wait_for_url("**/catalog/**", timeout=5000)

        record = Record.objects.get(title__startswith="Likute")
        assert record.authors.first().name == NLI_AUTHOR
        assert Author.objects.count() == 2

    @patch("ingest.views.isbn_lookup")
    def test_a_single_strong_match_is_chosen_in_advance(
        self, mock_lookup, page, live_server, staff_user
    ):
        """A confirm stays one click when the match is unambiguous."""
        mock_lookup.return_value = isbn_result(
            f"{LC_AUTHOR}, 1745-1812.", NLI_AUTHOR
        )
        ensure_fts_table()
        existing = Author.objects.create(name=NLI_AUTHOR)

        reach_confirm_page(page, live_server)

        expect(
            page.locator(f'input[name="author_choice"][value="{existing.pk}"]')
        ).to_be_checked()

        page.click('button:text("Add to catalog")')
        page.wait_for_url("**/catalog/**", timeout=5000)

        record = Record.objects.get(title__startswith="Likute")
        assert list(record.authors.all()) == [existing]
        assert Author.objects.count() == 1
