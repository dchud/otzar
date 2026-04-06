"""End-to-end tests for public browsing workflows."""

import pytest
from playwright.sync_api import expect


@pytest.mark.django_db(transaction=True)
class TestHomePage:
    def test_home_loads(self, page, live_server):
        page.goto(live_server.url)
        expect(page.locator("h1")).to_contain_text("Catalog")

    def test_search_bar_present(self, page, live_server):
        page.goto(live_server.url)
        expect(page.locator('input[name="q"]')).to_be_visible()

    def test_browse_links_present(self, page, live_server):
        page.goto(live_server.url)
        expect(page.locator("text=Authors")).to_be_visible()
        expect(page.locator("text=Titles")).to_be_visible()
        expect(page.locator("text=Subjects")).to_be_visible()

    def test_recent_additions_shown(self, page, live_server, sample_record):
        page.goto(live_server.url)
        expect(page.locator("text=Recent additions")).to_be_visible()
        expect(page.locator("text=The social life of information")).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestBrowseViews:
    def test_browse_index(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/browse/")
        expect(page.locator("h1")).to_contain_text("Browse")

    def test_author_browse_shows_authors(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/browse/authors/")
        expect(page.get_by_role("link", name="Brown, John Seely")).to_be_visible()

    def test_author_browse_is_clickable(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/browse/authors/")
        page.click("text=Brown, John Seely")
        # Should navigate to author detail
        expect(page.locator("h1")).to_contain_text("Brown, John Seely")
        expect(page.locator("text=The social life of information")).to_be_visible()

    def test_subject_browse_shows_subjects(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/browse/subjects/")
        expect(page.locator("text=Information society")).to_be_visible()

    def test_subject_browse_is_clickable(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/browse/subjects/")
        page.click("text=Information society")
        expect(page.locator("h1")).to_contain_text("Information society")

    def test_title_browse_is_clickable(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/browse/titles/")
        page.click("text=The social life of information")
        # Should navigate to record detail
        expect(page.locator("h1")).to_contain_text("The social life of information")

    def test_publisher_browse_is_clickable(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/browse/publishers/")
        expect(page.locator("text=Harvard Business School Press")).to_be_visible()

    def test_location_browse_is_clickable(self, page, live_server, sample_record):
        page.goto(f"{live_server.url}/browse/locations/")
        expect(page.locator("text=Floor 1, Shelf A")).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestRecordDetail:
    def test_record_detail_shows_all_fields(self, page, live_server, sample_record):
        page.goto(
            f"{live_server.url}/catalog/{sample_record.record_id}/{sample_record.slug}/"
        )
        expect(page.locator("h1")).to_contain_text("The social life of information")
        # Authors — use first() since name may appear in both original and romanized
        expect(page.get_by_role("link", name="Brown, John Seely").first).to_be_visible()
        expect(page.get_by_role("link", name="Duguid, Paul").first).to_be_visible()
        # Subjects
        expect(page.locator("text=Information society")).to_be_visible()
        # Identifiers
        expect(page.locator("text=0875847625")).to_be_visible()

    def test_record_detail_redirect_without_slug(
        self, page, live_server, sample_record
    ):
        page.goto(f"{live_server.url}/catalog/{sample_record.record_id}/")
        # Should redirect to URL with slug
        expect(page).to_have_url(
            f"{live_server.url}/catalog/{sample_record.record_id}/{sample_record.slug}/"
        )

    def test_record_detail_404(self, page, live_server, sample_record):
        resp = page.goto(f"{live_server.url}/catalog/otzar-nonexistent/")
        assert resp.status == 404
