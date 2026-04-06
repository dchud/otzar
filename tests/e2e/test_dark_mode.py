"""End-to-end tests for dark mode toggle."""

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
