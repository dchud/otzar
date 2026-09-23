"""End-to-end tests for authentication and authorization."""

import pytest
from django.core.signing import TimestampSigner
from playwright.sync_api import expect

from tests.e2e.conftest import login


@pytest.mark.django_db(transaction=True)
class TestAuth:
    def test_ingest_requires_login(self, page, live_server):
        page.goto(f"{live_server.url}/ingest/")
        # Should redirect to login
        expect(page).to_have_url(
            f"{live_server.url}/accounts/login/?next=/ingest/"
        )

    def test_login_works(self, page, live_server, staff_user):
        login(page, live_server)
        # Should be on home page
        expect(page.locator("text=testadmin")).to_be_visible()
        expect(page.locator("text=Log out")).to_be_visible()

    def test_admin_link_visible_for_staff(self, page, live_server, staff_user):
        login(page, live_server)
        expect(page.locator('a[href="/admin/"]')).to_be_visible()

    def test_ingest_accessible_after_login(
        self, page, live_server, staff_user
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/")
        expect(page.locator("h1")).to_contain_text("Review Queue")

    def test_logout(self, page, live_server, staff_user):
        login(page, live_server)
        page.click('button:text("Log out")')
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Log in")).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestLoginThrottle:
    def _try(self, page, live_server, username, password):
        page.goto(f"{live_server.url}/accounts/login/")
        page.get_by_label("Username").fill(username)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Log in").click()

    def test_repeated_failures_show_the_lockout_page(
        self, page, live_server, staff_user
    ):
        for _ in range(4):
            self._try(page, live_server, "testadmin", "wrong")
            expect(
                page.get_by_text("Invalid username or password.")
            ).to_be_visible()

        self._try(page, live_server, "testadmin", "wrong")

        expect(
            page.get_by_role("heading", name="Too many attempts")
        ).to_be_visible()
        expect(page.get_by_text("Try again in an hour.")).to_be_visible()

    def test_lockout_does_not_block_another_user(
        self, page, live_server, staff_user, django_user_model
    ):
        django_user_model.objects.create_user(
            username="second", password="second-pass-123"
        )
        for _ in range(5):
            self._try(page, live_server, "testadmin", "wrong")
        expect(
            page.get_by_role("heading", name="Too many attempts")
        ).to_be_visible()

        self._try(page, live_server, "second", "second-pass-123")

        expect(page).to_have_url(f"{live_server.url}/")
        expect(page.get_by_role("button", name="Log out")).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestPasswordChange:
    def test_cataloger_changes_their_own_password(
        self, page, live_server, django_user_model
    ):
        django_user_model.objects.create_user(
            username="cataloger", password="old-pass-4821"
        )
        login(page, live_server, "cataloger", "old-pass-4821")

        page.get_by_role("link", name="cataloger").click()
        page.get_by_label("Old password").fill("old-pass-4821")
        page.get_by_label("New password", exact=True).fill("new-pass-7395")
        page.get_by_label("New password confirmation").fill("new-pass-7395")
        page.get_by_role("button", name="Change password").click()
        expect(
            page.get_by_role("heading", name="Password changed")
        ).to_be_visible()

        page.get_by_role("button", name="Log out").click()
        login(page, live_server, "cataloger", "new-pass-7395")
        expect(page.get_by_role("button", name="Log out")).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestSitePasswordGate:
    @pytest.fixture(autouse=True)
    def gate(self, settings):
        settings.SITE_PASSWORD = "open-sesame"

    def _pass_gate(self, page):
        page.get_by_label("Site password").fill("open-sesame")
        page.get_by_role("button", name="Enter").click()

    def _log_in(self, page):
        page.get_by_label("Username").fill("testadmin")
        page.get_by_label("Password").fill("testpass123")
        page.get_by_role("button", name="Log in").click()
        expect(page.get_by_role("button", name="Log out")).to_be_visible()

    def test_gate_stays_open_across_logout(
        self, page, live_server, staff_user
    ):
        page.goto(f"{live_server.url}/accounts/login/?next=/ingest/")
        expect(
            page.get_by_text("This site requires a password.")
        ).to_be_visible()
        self._pass_gate(page)

        expect(page).to_have_url(
            f"{live_server.url}/accounts/login/?next=/ingest/"
        )
        self._log_in(page)
        expect(page).to_have_url(f"{live_server.url}/ingest/")

        page.get_by_role("button", name="Log out").click()
        expect(page.get_by_role("link", name="Log in")).to_be_visible()

        page.get_by_role("link", name="Log in").click()
        self._log_in(page)
        expect(
            page.get_by_text("This site requires a password.")
        ).to_have_count(0)

    def test_phone_opens_the_qr_url_past_the_gate(
        self, browser, live_server, staff_user
    ):
        desktop = browser.new_context().new_page()
        desktop.goto(f"{live_server.url}/accounts/login/")
        self._pass_gate(desktop)
        self._log_in(desktop)

        phone = browser.new_context().new_page()
        token = TimestampSigner().sign(f"{staff_user.pk}:title")
        phone.goto(f"{live_server.url}/ingest/phone-auth/{token}/")

        expect(phone).to_have_url(f"{live_server.url}/ingest/scan-title/")
        expect(
            phone.get_by_role("heading", name="Title page capture")
        ).to_be_visible()
