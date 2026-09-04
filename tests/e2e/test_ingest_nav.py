"""End-to-end tests for the ingest mode bar.

Cataloguing is item-by-item and the route changes with the book, so
the three ways in belong on every ingest page rather than only on
/ingest/. On a phone this is not a convenience: base.html hides the
site nav below the sm breakpoint, so a phone that landed on a scan
page previously had no navigation at all.
"""

import pytest
from django.core.signing import TimestampSigner
from playwright.sync_api import expect

from tests.e2e.conftest import login

INGEST_PAGES = [
    ("/ingest/scan/", "Scan barcode"),
    ("/ingest/scan-title/", "Title page"),
    ("/ingest/new/", "Enter manually"),
]


@pytest.mark.django_db(transaction=True)
class TestIngestModeNav:
    @pytest.mark.parametrize("path,label", INGEST_PAGES)
    def test_bar_is_present_and_marks_the_current_route(
        self, page, live_server, staff_user, path, label
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}{path}")

        nav = page.locator("#ingest-mode-nav")
        expect(nav).to_be_visible()
        for _, other in INGEST_PAGES:
            expect(nav.locator(f'a:text-is("{other}")')).to_be_visible()

        expect(nav.locator('a[aria-current="page"]')).to_have_text(label)

    def test_bar_navigates_between_routes(self, page, live_server, staff_user):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/")

        page.click('#ingest-mode-nav a:text-is("Title page")')
        page.wait_for_url("**/ingest/scan-title/", timeout=5000)
        expect(page.locator("h1")).to_contain_text("Scan title page")

        page.click('#ingest-mode-nav a:text-is("Enter manually")')
        page.wait_for_url("**/ingest/new/", timeout=5000)
        expect(page.locator("h1")).to_contain_text("Add a new record")

    def test_bar_is_reachable_at_phone_width(
        self, page, live_server, staff_user
    ):
        """base.html hides its own nav here, so this bar is all there is."""
        page.set_viewport_size({"width": 375, "height": 812})
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan-title/")

        nav = page.locator("#ingest-mode-nav")
        expect(nav).to_be_visible()
        expect(nav.locator('a:text-is("Scan barcode")')).to_be_visible()

        # No horizontal overflow at phone width.
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth"
            " - document.documentElement.clientWidth"
        )
        assert overflow <= 0, f"page scrolls sideways by {overflow}px"

    def test_phone_from_barcode_qr_can_switch_to_title_capture(
        self, page, live_server, staff_user
    ):
        """A phone that authenticated for barcodes must get the phone
        title-page layout when it switches, not the desktop one."""
        page.set_viewport_size({"width": 375, "height": 812})
        token = TimestampSigner().sign(f"{staff_user.pk}:isbn")
        page.goto(f"{live_server.url}/ingest/phone-auth/{token}/")
        page.wait_for_url("**/ingest/scan/", timeout=5000)

        page.click('#ingest-mode-nav a:text-is("Title page")')
        page.wait_for_url("**/ingest/scan-title/", timeout=5000)

        expect(page.locator("h1")).to_contain_text("Title page capture")
        expect(page.locator("text=Capture on your phone")).to_have_count(0)

    @pytest.mark.parametrize("path,_label", INGEST_PAGES)
    def test_no_template_comment_leaks(
        self, page, live_server, staff_user, path, _label
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}{path}")
        body = page.locator("body").inner_text()
        assert "{#" not in body
        assert "#}" not in body
        assert "{% comment %}" not in body
