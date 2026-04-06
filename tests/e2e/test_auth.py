"""End-to-end tests for authentication and authorization."""

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import login


@pytest.mark.django_db(transaction=True)
class TestAuth:
    def test_ingest_requires_login(self, page, live_server):
        page.goto(f"{live_server.url}/ingest/")
        # Should redirect to login
        expect(page).to_have_url(f"{live_server.url}/accounts/login/?next=/ingest/")

    def test_login_works(self, page, live_server, staff_user):
        login(page, live_server)
        # Should be on home page
        expect(page.locator("text=testadmin")).to_be_visible()
        expect(page.locator("text=Log out")).to_be_visible()

    def test_admin_link_visible_for_staff(self, page, live_server, staff_user):
        login(page, live_server)
        expect(page.locator('a[href="/admin/"]')).to_be_visible()

    def test_ingest_accessible_after_login(self, page, live_server, staff_user):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/")
        expect(page.locator("h1")).to_contain_text("Add to catalog")

    def test_logout(self, page, live_server, staff_user):
        login(page, live_server)
        page.click('button:text("Log out")')
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Log in")).to_be_visible()
