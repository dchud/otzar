"""End-to-end tests for the title-page phone-to-desktop handoff."""

import os
import time
from unittest.mock import patch

import pytest
from django.core.signing import TimestampSigner
from playwright.sync_api import expect

from ingest.models import ScanResult
from sources.cascade import CascadeResult
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


# Candidate shapes matching what the catalogs return for a Hebrew title:
# long publisher lines, series statements, and three identifiers per row.
WIDE_CANDIDATES = [
    {
        "title": "The book of Leviticus : critical edition of the Hebrew text",
        "author": "Kanotopsky, Zvi Dov",
        "date": "1994-2003, \u00a91989-\u00a91990",
        "publisher": "W\u00fcrttembergische Bibelanstalt",
        "place": "Stuttgart",
        "series_title": "Biblia Hebraica Stuttgartensia",
        "series_volume": "2",
        "isbn": "9783438052285",
        "lccn": "75950123",
        "oclc": "891550895",
        "source_catalog": "NLI",
    },
    {
        "title": "\u05e1\u05e4\u05e8 \u05d5\u05d9\u05e7\u05e8\u05d0 = Vayikra = Leviticus",
        "author": "Scherman, Nosson",
        "date": "1994-2003, \u00a91989-\u00a91990",
        "publisher": "ArtScroll Mesorah Publications",
        "place": "Brooklyn, New York",
        "series_title": "ArtScroll series : Sapirstein edition",
        "series_volume": "3",
        "isbn": "9780899060269",
        "lccn": "2004273599",
        "oclc": "1037696818",
        "source_catalog": "NLI",
    },
]
WIDE_CANDIDATES = WIDE_CANDIDATES * 4


def _phone_token(user):
    """Sign a title-target QR token for the given user."""
    return TimestampSigner().sign(f"{user.pk}:title")


@pytest.mark.django_db(transaction=True)
class TestTitlePageHandoff:
    def test_phone_auth_lands_on_title_capture(
        self, page, live_server, staff_user
    ):
        """Scanning a title-target QR drops the phone on the capture page."""
        page.goto(
            f"{live_server.url}/ingest/phone-auth/{_phone_token(staff_user)}/"
        )
        page.wait_for_url("**/ingest/scan-title/", timeout=5000)

        expect(page.locator("h1")).to_contain_text("Title page capture")
        # Phone view: no QR sidebar.
        expect(page.locator("text=Capture on your phone")).to_have_count(0)
        # Capture form is present.
        expect(page.locator("#image-input")).to_have_count(1)
        # Guard against multi-line {# ... #} comment leaks: Django's
        # short-comment syntax is single-line only and silently leaks
        # multi-line comments as visible text.
        body = page.locator("body").inner_text()
        assert "{#" not in body
        assert "#}" not in body

    def test_desktop_view_has_no_template_comment_leaks(
        self, page, live_server, staff_user
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan-title/")
        body = page.locator("body").inner_text()
        assert "{#" not in body
        assert "#}" not in body

    def test_desktop_view_shows_qr_sidebar(
        self, page, live_server, staff_user
    ):
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

        # The card must actually display the uploaded image, not a broken
        # img tag. Fetch the src and verify it 200s.
        card_img = desktop_page.locator(
            "[id^='title-page-card-'] img[alt='Uploaded title page']"
        )
        expect(card_img).to_be_visible()
        img_src = card_img.get_attribute("src")
        assert img_src and img_src.startswith("/media/"), (
            f"image src looks wrong: {img_src!r}"
        )
        img_response = desktop_page.request.get(f"{live_server.url}{img_src}")
        assert img_response.status == 200, (
            f"image url {img_src} returned {img_response.status}"
        )

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
        expect(page.locator(f"#title-page-card-{scan.pk}")).to_be_visible(
            timeout=10000
        )

        # Click Run OCR; the metadata edit partial appears.
        page.click('button:text("Run OCR")')
        expect(page.locator("text=Extracted metadata")).to_be_visible(
            timeout=10000
        )
        expect(page.locator('input[name="title_romanized"]')).to_have_value(
            "Mishneh Torah"
        )

        # The metadata form must survive a poll cycle (>3s) without being
        # wiped by the polling div.
        page.wait_for_timeout(4000)
        expect(page.locator("text=Extracted metadata")).to_be_visible()
        expect(page.locator('input[name="title_romanized"]')).to_have_value(
            "Mishneh Torah"
        )

        scan.refresh_from_db()
        assert scan.status == "pending"
        assert scan.ocr_output == SAMPLE_OCR_RESPONSE

    @patch("ingest.views.extract_metadata_from_image")
    def test_re_run_ocr_from_metadata_form(
        self, mock_ocr, page, live_server, staff_user
    ):
        """The Re-run OCR button on the metadata form re-extracts and
        replaces the metadata."""
        mock_ocr.side_effect = [
            {**SAMPLE_OCR_RESPONSE, "title_romanized": "First Title"},
            {**SAMPLE_OCR_RESPONSE, "title_romanized": "Second Title"},
        ]

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
        expect(page.locator(f"#title-page-card-{scan.pk}")).to_be_visible(
            timeout=10000
        )

        page.click('button:text("Run OCR")')
        expect(page.locator('input[name="title_romanized"]')).to_have_value(
            "First Title", timeout=10000
        )

        page.click('button:text("Re-run OCR")')
        expect(page.locator('input[name="title_romanized"]')).to_have_value(
            "Second Title", timeout=10000
        )
        assert mock_ocr.call_count == 2

    @patch("ingest.views.extract_metadata_from_image")
    def test_discard_from_metadata_form(
        self, mock_ocr, page, live_server, staff_user
    ):
        """The Discard button on the metadata form removes the scan and
        the metadata form."""
        mock_ocr.return_value = SAMPLE_OCR_RESPONSE

        with open(FIXTURE_IMAGE, "rb") as fh:
            from django.core.files.base import ContentFile

            scan = ScanResult.objects.create(
                scan_type="ocr",
                status="awaiting_ocr",
                scanned_by=staff_user,
            )
            scan.image.save("blank.jpg", ContentFile(fh.read()))
        image_path = scan.image.path

        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan-title/")
        expect(page.locator(f"#title-page-card-{scan.pk}")).to_be_visible(
            timeout=10000
        )

        page.click('button:text("Run OCR")')
        expect(page.locator("text=Extracted metadata")).to_be_visible(
            timeout=10000
        )

        page.on("dialog", lambda dialog: dialog.accept())
        # Use the Discard button inside the metadata form (avoid card-level Discard).
        page.locator('#title-page-metadata button:text("Discard")').click()

        expect(page.locator("text=Extracted metadata")).to_have_count(0)
        scan.refresh_from_db()
        assert scan.status == "discarded"
        assert not scan.image
        import os as _os

        assert not _os.path.exists(image_path)

    def test_discard_removes_card_and_image(
        self, page, live_server, staff_user
    ):
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
        expect(page.locator(f"#title-page-card-{scan.pk}")).to_be_visible(
            timeout=10000
        )

        # hx-confirm pops a JS confirm; auto-accept it.
        page.on("dialog", lambda dialog: dialog.accept())
        page.click('button:text("Discard")')

        expect(page.locator(f"#title-page-card-{scan.pk}")).to_have_count(0)
        scan.refresh_from_db()
        assert scan.status == "discarded"
        assert not scan.image
        assert not os.path.exists(image_path)

    @patch("ingest.views.extract_metadata_from_image")
    def test_spinner_runs_while_ocr_is_working(
        self, mock_ocr, page, live_server, staff_user
    ):
        """The wait for the vision API is visible while it happens."""

        def slow_ocr(_image_bytes):
            time.sleep(1.5)
            return SAMPLE_OCR_RESPONSE

        mock_ocr.side_effect = slow_ocr

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
        expect(page.locator(f"#title-page-card-{scan.pk}")).to_be_visible(
            timeout=10000
        )

        spinner = page.locator("#ocr-spinner")
        expect(spinner).to_be_hidden()

        page.click('button:text("Run OCR")')
        expect(spinner).to_be_visible(timeout=2000)

        expect(page.locator("text=Extracted metadata")).to_be_visible(
            timeout=15000
        )
        expect(spinner).to_be_hidden()

    @patch("ingest.views.extract_metadata_from_image")
    def test_failed_ocr_shows_the_photo_once(
        self, mock_ocr, page, live_server, staff_user
    ):
        """A failed OCR leaves one photo on screen, not two."""
        mock_ocr.return_value = None

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
        expect(page.locator(f"#title-page-card-{scan.pk}")).to_be_visible(
            timeout=10000
        )

        page.click('button:text("Run OCR")')
        expect(
            page.locator("text=OCR could not extract metadata")
        ).to_be_visible(timeout=10000)

        expect(page.locator("img[alt='Uploaded title page']")).to_have_count(1)
        expect(page.locator(f"#title-page-card-{scan.pk}")).to_have_count(1)

    def test_retake_after_discard_shows_the_new_photo(
        self, page, live_server, staff_user
    ):
        """The card after a retake points at a different image URL.

        Phone captures share one filename, so a retake used to land on the
        URL the discarded photo had already taught the browser to cache.
        """
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan-title/")

        def upload():
            page.set_input_files("#image-input", FIXTURE_IMAGE)
            expect(page.locator("#upload-btn")).to_be_enabled(timeout=5000)
            page.click("#upload-btn")
            card = page.locator("[id^='title-page-card-']").first
            expect(card).to_be_visible(timeout=5000)
            return card.locator(
                "img[alt='Uploaded title page']"
            ).get_attribute("src")

        first_src = upload()

        page.on("dialog", lambda dialog: dialog.accept())
        page.locator("[id^='title-page-card-'] button:text('Discard')").click()
        expect(page.locator("[id^='title-page-card-']")).to_have_count(0)

        second_src = upload()

        assert second_src and second_src != first_src, (
            f"retake reused the discarded photo's URL: {second_src}"
        )

    def test_candidates_table_fits_beside_qr_sidebar(
        self, page, live_server, staff_user
    ):
        """The candidate table stays fully visible next to the QR sidebar.

        The desktop content column shares a row with the QR sidebar. When
        the column carries a width cap, the table's rightmost column — the
        Use buttons — is pushed outside the scroll container and can only
        be reached by scrolling sideways.
        """
        page.set_viewport_size({"width": 1280, "height": 800})

        with open(FIXTURE_IMAGE, "rb") as fh:
            from django.core.files.base import ContentFile

            scan = ScanResult.objects.create(
                scan_type="ocr",
                status="pending",
                ocr_output=SAMPLE_OCR_RESPONSE,
                scanned_by=staff_user,
            )
            scan.image.save("blank.jpg", ContentFile(fh.read()))

        login(page, live_server)

        with (
            patch("ingest.views.search_nli") as mock_nli,
            patch("ingest.views.search_lc") as mock_lc,
        ):
            mock_nli.return_value = CascadeResult(records=WIDE_CANDIDATES)
            mock_lc.return_value = CascadeResult(records=[])

            page.goto(f"{live_server.url}/ingest/scan-title/")
            expect(page.locator(f"#title-page-card-{scan.pk}")).to_be_visible(
                timeout=10000
            )
            page.click('button:text("Continue editing")')
            expect(page.locator("text=Extracted metadata")).to_be_visible(
                timeout=10000
            )
            page.click('button:text("Search catalogs")')
            expect(page.locator("table")).to_be_visible(timeout=10000)

        # The QR sidebar shares the row, so this asserts the table fits
        # beside it rather than in a full-width column.
        expect(page.locator('img[alt*="QR code"]')).to_be_visible()

        overflow = page.evaluate("""() => {
            const wrap = document.querySelector('.overflow-x-auto');
            const wrapRight = wrap.getBoundingClientRect().right;
            const clipped = [...document.querySelectorAll('table tbody tr')]
                .filter(tr => tr.querySelector('button')
                    .getBoundingClientRect().right > wrapRight + 1).length;
            return {
                scrollOverflow: wrap.scrollWidth - wrap.clientWidth,
                clippedButtons: clipped,
                pageOverflow: document.documentElement.scrollWidth
                    - document.documentElement.clientWidth,
            };
        }""")

        assert overflow["scrollOverflow"] <= 0, (
            f"candidate table overflows its container by {overflow['scrollOverflow']}px"
        )
        assert overflow["clippedButtons"] == 0, (
            f"{overflow['clippedButtons']} Use buttons are outside the "
            f"visible area of the table"
        )
        assert overflow["pageOverflow"] <= 0, "page scrolls horizontally"
