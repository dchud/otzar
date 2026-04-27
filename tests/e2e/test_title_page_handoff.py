"""End-to-end tests for the title-page phone-to-desktop handoff."""

import os
from unittest.mock import patch

import pytest
from django.core.signing import TimestampSigner
from playwright.sync_api import expect

from ingest.models import ScanResult
from tests.e2e.conftest import login

FIXTURE_IMAGE = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "title_pages", "blank.jpg"
)

SAMPLE_OCR_RESPONSE = {
    "title": "משנה תורה",
    "subtitle": None,
    "author": "רמבם",
    "publisher": None,
    "place": "וילנא",
    "date": "1862",
    "title_romanized": "Mishneh Torah",
    "author_romanized": "Maimonides",
}


def _phone_token(user):
    """Sign a title-target QR token for the given user."""
    return TimestampSigner().sign(f"{user.pk}:title")


@pytest.mark.django_db(transaction=True)
class TestTitlePageHandoff:
    def test_phone_auth_lands_on_title_capture(self, page, live_server, staff_user):
        """Scanning a title-target QR drops the phone on the capture page."""
        page.goto(f"{live_server.url}/ingest/phone-auth/{_phone_token(staff_user)}/")
        page.wait_for_url("**/ingest/scan-title/", timeout=5000)

        expect(page.locator("h1")).to_contain_text("Title page capture")
        # Phone view: no QR sidebar.
        expect(page.locator("text=Capture on your phone")).to_have_count(0)
        # Capture form is present.
        expect(page.locator("#image-input")).to_have_count(1)

    def test_desktop_view_shows_qr_sidebar(self, page, live_server, staff_user):
        """Desktop view renders the QR handoff sidebar with target=title."""
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan-title/")

        expect(page.locator("h1")).to_contain_text("Scan title page")
        qr_img = page.locator('img[alt*="QR code"]')
        expect(qr_img).to_be_visible()
        src = qr_img.get_attribute("src")
        assert "target=title" in (src or "")

    def test_phone_upload_appears_in_desktop_poll(
        self, browser, live_server, staff_user
    ):
        """Two contexts: phone uploads a photo; desktop poll picks it up."""
        # Desktop context — logged in via session form.
        desktop = browser.new_context()
        desktop_page = desktop.new_page()
        login(desktop_page, live_server)
        desktop_page.goto(f"{live_server.url}/ingest/scan-title/")

        # Initial poll shows empty state.
        expect(desktop_page.locator("text=Waiting for photos")).to_be_visible()

        # Phone context — authenticates via QR token.
        phone = browser.new_context()
        phone_page = phone.new_page()
        phone_page.goto(
            f"{live_server.url}/ingest/phone-auth/{_phone_token(staff_user)}/"
        )
        phone_page.wait_for_url("**/ingest/scan-title/", timeout=5000)

        # Phone uploads the fixture image.
        phone_page.set_input_files("#image-input", FIXTURE_IMAGE)
        # The form's client-side resize is async; wait for the upload button
        # to become enabled before submitting.
        expect(phone_page.locator("#upload-btn")).to_be_enabled(timeout=5000)
        phone_page.click("#upload-btn")

        # Phone view shows the card.
        expect(phone_page.locator("[id^='title-page-card-']")).to_be_visible(
            timeout=5000
        )

        # Desktop poll picks it up within the next cycle.
        expect(desktop_page.locator("[id^='title-page-card-']")).to_be_visible(
            timeout=10000
        )
        expect(desktop_page.locator('button:text("Run OCR")')).to_be_visible()
        expect(desktop_page.locator('button:text("Discard")')).to_be_visible()

        # ScanResult was created and is awaiting OCR.
        scan = ScanResult.objects.get(scan_type="ocr")
        assert scan.status == "awaiting_ocr"
        assert scan.scanned_by == staff_user

        desktop.close()
        phone.close()

    @patch("ingest.views.extract_metadata_from_image")
    def test_run_ocr_from_desktop_shows_metadata(
        self, mock_ocr, page, live_server, staff_user
    ):
        """A user who uploaded an image can trigger OCR from the desktop poll
        and see the editable metadata partial."""
        mock_ocr.return_value = SAMPLE_OCR_RESPONSE

        # Pre-create a scan as if the phone had uploaded.
        with open(FIXTURE_IMAGE, "rb") as fh:
            from django.core.files.base import ContentFile

            scan = ScanResult.objects.create(
                scan_type="ocr",
                status="awaiting_ocr",
                scanned_by=staff_user,
            )
            scan.image.save("blank.jpg", ContentFile(fh.read()))

        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan-title/")

        # Card appears via poll.
        expect(page.locator(f"#title-page-card-{scan.pk}")).to_be_visible(timeout=10000)

        # Click Run OCR; the card swaps with the metadata edit partial.
        page.click('button:text("Run OCR")')
        expect(page.locator("text=Extracted metadata")).to_be_visible(timeout=10000)
        expect(page.locator('input[name="title_romanized"]')).to_have_value(
            "Mishneh Torah"
        )

        scan.refresh_from_db()
        assert scan.status == "pending"
        assert scan.ocr_output == SAMPLE_OCR_RESPONSE

    def test_discard_removes_card_and_image(self, page, live_server, staff_user):
        """Discarding from the desktop card removes the row's image and the
        card disappears."""
        with open(FIXTURE_IMAGE, "rb") as fh:
            from django.core.files.base import ContentFile

            scan = ScanResult.objects.create(
                scan_type="ocr",
                status="awaiting_ocr",
                scanned_by=staff_user,
            )
            scan.image.save("blank.jpg", ContentFile(fh.read()))
        image_path = scan.image.path
        assert os.path.exists(image_path)

        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan-title/")
        expect(page.locator(f"#title-page-card-{scan.pk}")).to_be_visible(timeout=10000)

        # hx-confirm pops a JS confirm; auto-accept it.
        page.on("dialog", lambda dialog: dialog.accept())
        page.click('button:text("Discard")')

        expect(page.locator(f"#title-page-card-{scan.pk}")).to_have_count(0)
        scan.refresh_from_db()
        assert scan.status == "discarded"
        assert not scan.image
        assert not os.path.exists(image_path)
