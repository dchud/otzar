"""End-to-end tests for catalog search."""

import pytest
from playwright.sync_api import expect


@pytest.mark.django_db(transaction=True)
class TestCatalogSearch:
    def test_search_page_loads(self, page, live_server):
        page.goto(f"{live_server.url}/search/")
        expect(page.locator('input[name="q"]')).to_be_visible()

    def test_search_from_home(self, page, live_server, sample_record):
        page.goto(live_server.url)
        page.fill('input[name="q"]', "social life")
        page.click('button[type="submit"]')
        expect(page.locator("text=The social life of information")).to_be_visible()

    def test_search_by_author(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/search/?q=Brown")
        expect(page.locator("text=The social life of information")).to_be_visible()

    def test_search_by_isbn(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/search/?q=0875847625")
        expect(page.locator("text=The social life of information")).to_be_visible()

    def test_search_no_results(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/search/?q=xyznonexistent")
        expect(page.locator("text=No results")).to_be_visible()

    def test_search_with_punctuation(self, page, live_server, sample_record):
        """Commas and other punctuation should not cause errors."""
        page.goto(f"{live_server.url}/search/?q=Harvard+Business+School+Press,")
        # Should not error — may or may not find results depending on indexing
        expect(page.locator("h1")).to_contain_text("Search")

    def test_search_result_links_to_record(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/search/?q=social+life")
        page.click("text=The social life of information")
        expect(page.locator("h1")).to_contain_text("The social life of information")
