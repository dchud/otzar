"""End-to-end tests for the barcode scanning page and QR handoff flow."""

from unittest.mock import patch

import pytest
from django.core.signing import TimestampSigner
from playwright.sync_api import expect

from catalog.search import ensure_fts_table
from ingest.models import ScanResult
from tests.e2e.conftest import login
from tests.e2e.test_ingest import MOCK_ISBN_RESULT


@pytest.mark.django_db(transaction=True)
class TestBarcodeScanPage:
    """Tests for the ISBN scan page with camera scanning UI (laptop mode)."""

    def test_scan_page_has_camera_controls(self, page, live_server, staff_user):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")

        expect(page.locator("h1")).to_contain_text("Scan ISBN")
        expect(page.locator("#start-scan-btn")).to_be_visible()
        expect(page.locator("#stop-scan-btn")).to_be_hidden()
        expect(page.locator("#viewfinder")).to_be_hidden()
        expect(page.locator("#isbn-input")).to_be_visible()

    def test_scan_page_has_poll_area(self, page, live_server, staff_user):
        """Laptop scan page polls for incoming phone scans."""
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")

        expect(page.locator("#scan-poll")).to_be_visible()
        expect(page.locator("text=Waiting for scans")).to_be_visible()

    def test_scan_page_shows_qr_code(self, page, live_server, staff_user):
        """Laptop scan page shows QR code for phone handoff."""
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")

        qr_img = page.locator('img[alt*="QR code"]')
        expect(qr_img).to_be_visible()

    @patch("ingest.views.isbn_lookup")
    def test_laptop_lookup_shows_candidates(
        self, mock_lookup, page, live_server, staff_user
    ):
        """Direct ISBN lookup on laptop still shows candidates inline."""
        mock_lookup.return_value = MOCK_ISBN_RESULT
        ensure_fts_table()

        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")

        page.fill("#isbn-input", "0875847625")
        page.click('button:text("Look up")')

        page.wait_for_selector("h3", timeout=10000)
        expect(
            page.get_by_role("heading", name="The social life of information")
        ).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestPhoneScannerMode:
    """Tests for phone scanner mode (accessed via QR token)."""

    def test_phone_mode_shows_phone_scanner_title(self, page, live_server, staff_user):
        """Phone auth sets phone_scanner flag, scan page shows phone UI."""
        signer = TimestampSigner()
        token = signer.sign(str(staff_user.pk))

        page.goto(f"{live_server.url}/ingest/phone-auth/{token}/")
        page.wait_for_url("**/ingest/scan/", timeout=5000)

        expect(page.locator("h1")).to_contain_text("Phone Scanner")
        # No QR code on phone
        expect(page.locator('img[alt*="QR code"]')).to_have_count(0)
        # No poll area on phone
        expect(page.locator("#scan-poll")).to_have_count(0)

    @patch("ingest.views.isbn_lookup")
    def test_phone_scan_sends_to_queue(
        self, mock_lookup, page, live_server, staff_user
    ):
        """Phone scan creates a ScanResult and shows confirmation."""
        mock_lookup.return_value = MOCK_ISBN_RESULT
        ensure_fts_table()

        signer = TimestampSigner()
        token = signer.sign(str(staff_user.pk))
        page.goto(f"{live_server.url}/ingest/phone-auth/{token}/")
        page.wait_for_url("**/ingest/scan/", timeout=5000)

        page.fill("#isbn-input", "0875847625")
        page.click('button:text("Look up")')

        # Phone gets confirmation, not full candidates
        page.wait_for_selector("#phone-scan-result", timeout=10000)
        expect(page.locator("text=Sent ISBN 0875847625 to review")).to_be_visible()
        expect(page.locator("text=Check your laptop")).to_be_visible()

        # ScanResult was created
        scan = ScanResult.objects.get(isbn="0875847625")
        assert scan.scanned_by == staff_user
        assert scan.status == "pending"
        assert len(scan.candidate_records) == 1

    @patch("ingest.views.isbn_lookup")
    def test_laptop_poll_picks_up_phone_scan(
        self, mock_lookup, page, live_server, staff_user
    ):
        """Laptop poll endpoint returns scans created by phone."""
        mock_lookup.return_value = MOCK_ISBN_RESULT
        ensure_fts_table()

        # Create a scan as if the phone did it.
        ScanResult.objects.create(
            scan_type="isbn",
            isbn="0875847625",
            candidate_records=[
                {**MOCK_ISBN_RESULT["nli_records"][0], "source_catalog": "NLI"}
            ],
            scanned_by=staff_user,
        )

        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")

        # Poll should show the pending scan
        page.wait_for_selector("#scan-poll", timeout=5000)
        # Wait for the poll to fetch and render
        page.wait_for_selector("text=ISBN: 0875847625", timeout=10000)
        expect(page.locator("text=ISBN: 0875847625")).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestQRCodeHandoff:
    """Tests for the QR code generation and phone auth endpoints."""

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
        expect(page.locator("h1")).to_contain_text("Phone Scanner")

    def test_phone_auth_expired_token(self, page, live_server, staff_user):
        """Expired token shows an error message."""
        signer = TimestampSigner()
        token = signer.sign(str(staff_user.pk))

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

    def test_scan_poll_endpoint(self, page, live_server, staff_user):
        """Poll endpoint returns pending scans for the current user."""
        login(page, live_server)

        # No scans yet
        response = page.request.get(f"{live_server.url}/ingest/scan/poll/")
        assert response.status == 200
        assert "Waiting for scans" in response.text()

        # Create a pending scan
        ScanResult.objects.create(
            scan_type="isbn",
            isbn="1234567890",
            candidate_records=[],
            scanned_by=staff_user,
        )

        response = page.request.get(f"{live_server.url}/ingest/scan/poll/")
        assert response.status == 200
        assert "1234567890" in response.text()
