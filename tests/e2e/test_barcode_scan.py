"""End-to-end tests for the barcode scanning page and QR handoff flow."""

from unittest.mock import patch

import pytest
from django.core.signing import TimestampSigner
from playwright.sync_api import expect

from catalog.search import ensure_fts_table
from tests.e2e.conftest import login
from tests.e2e.test_ingest import MOCK_ISBN_RESULT


@pytest.mark.django_db(transaction=True)
class TestBarcodeScanPage:
    """Tests for the ISBN scan page with camera scanning UI."""

    def test_scan_page_has_camera_controls(self, page, live_server, staff_user):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")

        expect(page.locator("h1")).to_contain_text("Scan ISBN")
        expect(page.locator("#start-scan-btn")).to_be_visible()
        expect(page.locator("#stop-scan-btn")).to_be_hidden()
        expect(page.locator("#viewfinder")).to_be_hidden()
        # Manual input is always visible
        expect(page.locator("#isbn-input")).to_be_visible()

    def test_manual_isbn_still_works(self, page, live_server, staff_user):
        """Manual ISBN entry continues to work alongside camera scanning."""
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")

        expect(page.locator("#isbn-input")).to_be_visible()
        expect(page.locator('button:text("Look up")')).to_be_visible()

    @patch("ingest.views.isbn_lookup")
    def test_barcode_js_fills_and_submits(
        self, mock_lookup, page, live_server, staff_user
    ):
        """Simulate what the barcode JS does: fill the input and trigger submit."""
        mock_lookup.return_value = MOCK_ISBN_RESULT
        ensure_fts_table()

        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")

        # Simulate barcode detection by filling the ISBN and triggering the form
        # (we can't access a real camera in headless tests).
        page.fill("#isbn-input", "0875847625")
        page.click('button:text("Look up")')

        page.wait_for_selector("h3", timeout=10000)
        expect(
            page.get_by_role("heading", name="The social life of information")
        ).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestQRCodeHandoff:
    """Tests for the QR code generation and phone auth flow."""

    def test_qr_code_generates_png(self, page, live_server, staff_user):
        """QR code endpoint returns a PNG image."""
        login(page, live_server)
        response = page.request.get(f"{live_server.url}/ingest/qr/")
        assert response.status == 200
        assert response.headers["content-type"] == "image/png"

    def test_qr_code_requires_auth(self, page, live_server, db):
        """QR code endpoint redirects to login when not authenticated."""
        response = page.request.get(f"{live_server.url}/ingest/qr/", max_redirects=0)
        assert response.status == 302

    def test_phone_auth_logs_in_and_redirects(self, page, live_server, staff_user):
        """Phone auth endpoint validates token, logs user in, redirects to scan."""
        signer = TimestampSigner()
        token = signer.sign(str(staff_user.pk))

        page.goto(f"{live_server.url}/ingest/phone-auth/{token}/")
        page.wait_for_url("**/ingest/scan/", timeout=5000)
        expect(page.locator("h1")).to_contain_text("Scan ISBN")

    def test_phone_auth_expired_token(self, page, live_server, staff_user):
        """Expired token shows an error message."""
        signer = TimestampSigner()
        token = signer.sign(str(staff_user.pk))

        # Unsign with max_age=0 would expire — but we need to test the view.
        # Mangle the timestamp portion to simulate expiry.
        with patch(
            "ingest.views.TimestampSigner.unsign",
            side_effect=__import__(
                "django.core.signing", fromlist=["SignatureExpired"]
            ).SignatureExpired,
        ):
            response = page.request.get(f"{live_server.url}/ingest/phone-auth/{token}/")
            assert response.status == 403

    def test_phone_auth_bad_token(self, page, live_server, db):
        """Invalid token returns 400."""
        response = page.request.get(f"{live_server.url}/ingest/phone-auth/bad-token/")
        assert response.status == 400

    def test_scan_page_shows_qr_code(self, page, live_server, staff_user):
        """Scan page shows QR code for phone handoff."""
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")

        qr_img = page.locator('img[alt*="QR code"]')
        expect(qr_img).to_be_visible()

    @patch("ingest.views.isbn_lookup")
    def test_full_qr_to_scan_flow(self, mock_lookup, page, live_server, staff_user):
        """Complete flow: phone auth via token → scan page → ISBN lookup."""
        mock_lookup.return_value = MOCK_ISBN_RESULT
        ensure_fts_table()

        # Simulate phone scanning the QR code.
        signer = TimestampSigner()
        token = signer.sign(str(staff_user.pk))
        page.goto(f"{live_server.url}/ingest/phone-auth/{token}/")
        page.wait_for_url("**/ingest/scan/", timeout=5000)

        # Now on scan page — verify camera UI is present.
        expect(page.locator("#start-scan-btn")).to_be_visible()
        expect(page.locator("#isbn-input")).to_be_visible()

        # Simulate a barcode scan by filling ISBN and submitting.
        page.fill("#isbn-input", "0875847625")
        page.click('button:text("Look up")')

        page.wait_for_selector("h3", timeout=10000)
        expect(
            page.get_by_role("heading", name="The social life of information")
        ).to_be_visible()
