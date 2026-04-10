"""End-to-end tests for dark mode toggle and contrast."""

import re

import pytest
from playwright.sync_api import expect


@pytest.mark.django_db(transaction=True)
class TestDarkMode:
    def test_toggle_adds_dark_class(self, page, live_server):
        page.goto(live_server.url)

        html = page.locator("html")

        # Click the toggle button
        page.click('button[aria-label="Toggle dark mode"]')

        # The html element should have the dark class
        expect(html).to_have_class(re.compile("dark"))

    def test_toggle_removes_dark_class(self, page, live_server):
        page.goto(live_server.url)

        html = page.locator("html")

        # Click twice: on then off
        page.click('button[aria-label="Toggle dark mode"]')
        expect(html).to_have_class(re.compile("dark"))

        page.click('button[aria-label="Toggle dark mode"]')
        # Should no longer have dark class
        expect(html).not_to_have_class(re.compile("dark"))

    def test_dark_mode_persists_across_navigation(
        self, page, live_server, sample_record
    ):
        page.goto(live_server.url)

        # Enable dark mode
        page.click('button[aria-label="Toggle dark mode"]')
        expect(page.locator("html")).to_have_class(re.compile("dark"))

        # Navigate to another page
        page.goto(f"{live_server.url}/browse/")

        # Dark mode should still be active
        expect(page.locator("html")).to_have_class(re.compile("dark"))

    def test_dark_mode_no_console_errors(self, page, live_server, sample_record):
        """Dark mode should render key pages without JavaScript errors."""
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto(live_server.url)
        page.click('button[aria-label="Toggle dark mode"]')
        expect(page.locator("html")).to_have_class(re.compile("dark"))

        # Visit several pages in dark mode
        for path in ["/", "/browse/", "/search/"]:
            page.goto(f"{live_server.url}{path}")
            # Page should render with dark background
            expect(page.locator("body")).to_have_class(re.compile("dark:bg-gray-900"))

        assert errors == [], f"Console errors in dark mode: {errors}"

    def test_dark_mode_contrast_classes(self, page, live_server, sample_record):
        """Verify dark mode text uses gray-300 (not gray-400) for contrast."""
        page.goto(live_server.url)
        page.click('button[aria-label="Toggle dark mode"]')
        expect(page.locator("html")).to_have_class(re.compile("dark"))

        # Footer text should use dark:text-gray-300 for sufficient contrast
        footer_div = page.locator("footer div")
        footer_classes = footer_div.get_attribute("class")
        assert "dark:text-gray-300" in footer_classes
        assert "dark:text-gray-400" not in footer_classes

    def test_dark_mode_record_detail_contrast(self, page, live_server, sample_record):
        """Record detail page should use gray-300 text in dark mode."""
        slug = sample_record.slug
        rid = sample_record.record_id
        page.goto(f"{live_server.url}/catalog/{rid}/{slug}/")
        page.click('button[aria-label="Toggle dark mode"]')
        expect(page.locator("html")).to_have_class(re.compile("dark"))

        # Section headers should use dark:text-gray-300
        headers = page.locator("h2.text-sm.font-semibold")
        count = headers.count()
        assert count > 0, "Expected section headers on record detail"
        for i in range(count):
            classes = headers.nth(i).get_attribute("class")
            assert "dark:text-gray-300" in classes
