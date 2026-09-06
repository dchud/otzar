"""End-to-end tests for how the browser gets its assets.

Every one of these tests severs the browser's access to everything
except the application itself. That is the point: a test that quietly
lets the browser reach a CDN proves nothing about a phone at the
shelves whose wifi cannot.
"""

import re

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import login


@pytest.fixture
def offline_page(page, live_server):
    """A page that can talk to the application and to nothing else.

    Requests to any other origin are aborted the way a failed DNS
    lookup or a captive portal would fail them, and every one is
    recorded so a test can assert none were attempted.
    """
    blocked = []

    def route_handler(route, request):
        if request.url.startswith(live_server.url):
            route.continue_()
        else:
            blocked.append(request.url)
            route.abort("connectionfailed")

    page.route("**/*", route_handler)
    page.blocked_urls = blocked
    return page


def _served_by_the_application(page, live_server, path):
    responses = []
    page.on("response", lambda r: responses.append((r.url, r.status)))
    page.goto(f"{live_server.url}{path}")
    page.wait_for_load_state("load")
    return responses


@pytest.mark.django_db(transaction=True)
class TestScriptsComeFromTheApplication:
    def test_home_page_loads_no_off_origin_asset(
        self, offline_page, live_server
    ):
        errors = []
        offline_page.on("pageerror", lambda e: errors.append(str(e)))

        offline_page.goto(live_server.url)
        offline_page.wait_for_load_state("load")

        assert offline_page.blocked_urls == [], (
            f"the page reached off-origin for: {offline_page.blocked_urls}"
        )
        assert errors == [], f"JavaScript errors: {errors}"

    def test_htmx_and_alpine_are_defined_with_no_network(
        self, offline_page, live_server
    ):
        offline_page.goto(live_server.url)
        offline_page.wait_for_function("() => window.htmx !== undefined")
        offline_page.wait_for_function("() => window.Alpine !== undefined")

        assert offline_page.evaluate("typeof window.htmx") == "object"
        assert offline_page.evaluate("window.htmx.version") == "2.0.4"
        assert offline_page.evaluate("window.Alpine.version") == "3.14.8"

    def test_the_scripts_are_fetched_from_the_application(
        self, page, live_server
    ):
        seen = _served_by_the_application(page, live_server, "/")
        scripts = [
            (url, status)
            for url, status in seen
            if url.endswith(".js") and "vendor/" in url
        ]
        assert len(scripts) == 2, f"expected two vendored scripts, got {seen}"
        for url, status in scripts:
            assert url.startswith(live_server.url)
            assert status == 200

    def test_dark_mode_toggle_works_with_no_network(
        self, offline_page, live_server
    ):
        """Alpine drives the toggle; without Alpine the button is inert."""
        offline_page.goto(live_server.url)
        offline_page.wait_for_function("() => window.Alpine !== undefined")

        offline_page.click('button[aria-label="Toggle dark mode"]')
        expect(offline_page.locator("html")).to_have_class(re.compile("dark"))
        assert offline_page.blocked_urls == []


@pytest.mark.django_db(transaction=True)
class TestIngestWorkflowWithNoNetwork:
    def test_htmx_swaps_on_the_scan_page_with_no_network(
        self, offline_page, live_server, staff_user
    ):
        """An htmx round trip, start to finish, with the CDN unreachable.

        Submitting an empty ISBN keeps the exchange inside the
        application -- no catalogue is queried -- so what the test
        proves is that htmx itself loaded, bound the form, posted, and
        swapped the reply in.
        """
        login(offline_page, live_server)
        offline_page.goto(f"{live_server.url}/ingest/scan/")
        offline_page.wait_for_function("() => window.htmx !== undefined")

        results = offline_page.locator("#results").first
        expect(results).to_be_empty()

        offline_page.locator(
            'form[hx-post] button[type="submit"]'
        ).first.click()

        expect(results).to_contain_text("Please enter an ISBN")
        assert offline_page.blocked_urls == []

    def test_the_queue_page_renders_with_no_network(
        self, offline_page, live_server, staff_user
    ):
        errors = []
        offline_page.on("pageerror", lambda e: errors.append(str(e)))

        login(offline_page, live_server)
        offline_page.goto(f"{live_server.url}/ingest/queue/")
        offline_page.wait_for_function("() => window.htmx !== undefined")

        expect(offline_page.locator("h1")).to_be_visible()
        assert offline_page.blocked_urls == []
        assert errors == [], f"JavaScript errors: {errors}"


@pytest.mark.django_db(transaction=True)
class TestResponsesAreCompressed:
    def test_pages_arrive_gzipped(self, page, live_server, sample_record):
        """What the browser actually negotiates, not what a unit test asks for.

        Playwright sends a real ``Accept-Encoding``, so this is the
        header a phone would get.
        """
        headers = {}

        def record(response):
            if response.url.rstrip("/") == live_server.url.rstrip("/"):
                headers.update(response.all_headers())

        page.on("response", record)
        page.goto(live_server.url)
        page.wait_for_load_state("load")

        assert headers.get("content-encoding") == "gzip", headers
        assert "accept-encoding" in headers.get("vary", "").lower()

    def test_a_record_page_arrives_gzipped(
        self, page, live_server, sample_record
    ):
        url = (
            f"{live_server.url}/catalog/{sample_record.record_id}/"
            f"{sample_record.slug}/"
        )
        response = page.goto(url)
        assert response.status == 200
        assert response.all_headers().get("content-encoding") == "gzip"
