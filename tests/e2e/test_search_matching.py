"""End-to-end tests for how a search word matches: prefixes and Hebrew
particles."""

from urllib.parse import urlencode

import pytest
from playwright.sync_api import expect

from catalog.models import Author, Record
from catalog.search import ensure_fts_table, index_record


@pytest.fixture
def matching_records(db):
    """Records that tell a prefix hit, a whole-word hit and a particle
    apart, with unrelated filler so the ranking has something to weigh."""
    ensure_fts_table()

    guide = Record.objects.create(title="Guide for the Perplexed")
    guide.authors.add(
        Author.objects.create(name="רמב״ם", name_romanized="Rambam")
    )
    kuzari = Record.objects.create(title="ספר הכוזרי")
    exact = Record.objects.create(title="Torah commentary")
    longer = Record.objects.create(title="Torahs, Torahs and more Torahs")
    fillers = [
        Record.objects.create(title=f"Unrelated filler {i}") for i in range(6)
    ]

    for record in (guide, kuzari, exact, longer, *fillers):
        index_record(record)
    return {"guide": guide, "kuzari": kuzari, "exact": exact}


def search_url(live_server, query):
    return f"{live_server.url}/search/?{urlencode({'q': query})}"


@pytest.mark.django_db(transaction=True)
class TestSearchMatching:
    def test_a_partial_word_reaches_the_record(
        self, page, live_server, matching_records
    ):
        page.goto(search_url(live_server, "Ramb"))
        expect(page.locator("text=Guide for the Perplexed")).to_be_visible()

    def test_a_hebrew_base_word_reaches_the_prefixed_form(
        self, page, live_server, matching_records
    ):
        page.goto(live_server.url)
        page.fill('input[name="q"]', "כוזרי")
        page.click('button[type="submit"]')
        expect(page.locator("text=ספר הכוזרי")).to_be_visible()

    def test_the_whole_word_is_listed_first(
        self, page, live_server, matching_records
    ):
        page.goto(search_url(live_server, "Torah"))
        expect(page.locator("text=2 results")).to_be_visible()
        expect(page.locator("ul li h2").first).to_have_text("Torah commentary")
