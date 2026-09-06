"""End-to-end tests for what confirming a candidate keeps.

Two kinds of data reached the candidate card and got no further. The
rest of the title statement -- which part of a set this is (245 $n and
$p) and who did what (245 $c) -- was shown and then dropped. So was the
series statement (490/830), so a set catalogued one volume at a time
never became a set on screen.

Both are checked from the browser, because both are only worth having
if a reader can see them on the record afterwards.
"""

from unittest.mock import patch

import pytest
from playwright.sync_api import expect

from catalog.models import Record
from catalog.search import ensure_fts_table
from ingest.models import ScanResult
from tests.e2e.conftest import login

STATEMENT = (
    "translated, annotated, and elucidated by Yisrael Isser Zvi Herczeg ; "
    "contributing editor, Avie Gold."
)

# A candidate as the parser hands it over, the cataloger's transcribed
# punctuation still on it.
VOLUME_TWO = {
    "title": "Rashi : the Torah, with Rashi's commentary /",
    "volume_part_number": "Volume 2,",
    "volume_part_title": "Sefer Mishpatim /",
    "statement_of_responsibility": STATEMENT,
    "author": "Rashi,",
    "date": "1999",
    "publisher": "Mesorah Publications",
    "place": "Brooklyn, N.Y.",
    "language": "eng",
    "series_title": "ArtScroll series ;",
    "series_volume": "v. 2",
    "source_catalog": "LC",
}

# The same set from a catalog that punctuates the series statement
# differently and writes the volume number as a Roman numeral. Neither
# difference is about the set, so neither may split it.
VOLUME_THREE = {
    "title": "Rashi : the Torah, with Rashi's commentary /",
    "volume_part_number": "Volume 3,",
    "volume_part_title": "Sefer Vayikra /",
    "author": "Rashi,",
    "date": "1999",
    "language": "eng",
    "series_title": "Artscroll Series.",
    "series_volume": "vol. III",
    "source_catalog": "NLI",
}

NO_SERIES = {
    "title": "Halakhic man /",
    "author": "Soloveitchik, Joseph Dov,",
    "date": "2007",
    "language": "eng",
    "source_catalog": "NLI",
}


def scan_for(staff_user, *candidates):
    ensure_fts_table()
    return ScanResult.objects.create(
        scan_type="isbn",
        isbn="9780899060149",
        candidate_records=list(candidates),
        scanned_by=staff_user,
    )


def record_url(live_server, record):
    return f"{live_server.url}/catalog/{record.record_id}/{record.slug}/"


def confirm_in_queue(page, live_server, scan, index):
    """Expand a queue row and take the confirm inside it."""
    page.goto(f"{live_server.url}/ingest/queue/")
    page.click(f"#scan-{scan.pk}-row-{index}")
    detail = page.locator(f"#scan-{scan.pk}-candidate-{index}")
    detail.get_by_role("button", name="Confirm").click()
    page.wait_for_url("**/ingest/queue/", timeout=10000)


@pytest.mark.django_db(transaction=True)
class TestReviewPageConfirm:
    """The route that ends on the new record's own page."""

    @patch("ingest.views.fetch_cover_url", return_value="")
    def test_the_part_and_the_responsibility_reach_the_record_page(
        self, _cover, page, live_server, staff_user
    ):
        scan = scan_for(staff_user, VOLUME_TWO)
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        page.click(f"#scan-{scan.pk}-row-0")
        detail = page.locator(f"#scan-{scan.pk}-candidate-0")
        detail.get_by_role("button", name="See full record").click()
        page.wait_for_url("**/ingest/confirm/", timeout=10000)

        page.get_by_role("button", name="Add to catalog").click()
        page.wait_for_url("**/catalog/**", timeout=10000)

        header = page.locator("article header")
        expect(header).to_contain_text("Volume 2 : Sefer Mishpatim")
        expect(header).to_contain_text(
            "translated, annotated, and elucidated by"
        )

    @patch("ingest.views.fetch_cover_url", return_value="")
    def test_the_series_statement_reaches_the_record_page(
        self, _cover, page, live_server, staff_user
    ):
        scan = scan_for(staff_user, VOLUME_TWO)
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        page.click(f"#scan-{scan.pk}-row-0")
        detail = page.locator(f"#scan-{scan.pk}-candidate-0")
        detail.get_by_role("button", name="See full record").click()
        page.wait_for_url("**/ingest/confirm/", timeout=10000)

        page.get_by_role("button", name="Add to catalog").click()
        page.wait_for_url("**/catalog/**", timeout=10000)

        article = page.locator("article")
        expect(article).to_contain_text("Series")
        expect(article).to_contain_text("ArtScroll series")
        expect(article).to_contain_text("vol. 2")


@pytest.mark.django_db(transaction=True)
class TestSecondVolumeJoinsTheSet:
    @patch("ingest.views.fetch_cover_url", return_value="")
    def test_the_second_confirm_lands_in_the_first_one_s_series(
        self, _cover, page, live_server, staff_user
    ):
        """Two volumes of one set are one series with two positions.

        The page proves it: the second volume's record offers a link to
        the first, which it can only do from a shared Series row.
        """
        login(page, live_server)

        # Confirming closes the scan it came from, so each volume
        # arrives as its own scan, the way a second book would.
        confirm_in_queue(
            page, live_server, scan_for(staff_user, VOLUME_TWO), 0
        )
        first = Record.objects.get(volume_part_number="Volume 2")

        confirm_in_queue(
            page, live_server, scan_for(staff_user, VOLUME_THREE), 0
        )
        second = Record.objects.get(volume_part_number="Volume 3")

        page.goto(record_url(live_server, second))

        article = page.locator("article")
        expect(article).to_contain_text("ArtScroll series")
        expect(article).to_contain_text("vol. 3")

        # The chip for the volume this record is not: it is a link
        # because the set already holds that one.
        sibling = article.get_by_role("link", name="2", exact=True)
        expect(sibling).to_have_attribute(
            "href", f"/catalog/{first.record_id}/{first.slug}/"
        )

        sibling.click()
        page.wait_for_url(f"**/{first.record_id}/**", timeout=10000)
        expect(page.locator("article header")).to_contain_text(
            "Volume 2 : Sefer Mishpatim"
        )


@pytest.mark.django_db(transaction=True)
class TestCandidateWithoutSeries:
    @patch("ingest.views.fetch_cover_url", return_value="")
    def test_it_confirms_and_the_page_offers_no_empty_series(
        self, _cover, page, live_server, staff_user
    ):
        scan = scan_for(staff_user, NO_SERIES)
        login(page, live_server)

        confirm_in_queue(page, live_server, scan, 0)

        record = Record.objects.get(title="Halakhic man")
        page.goto(record_url(live_server, record))

        article = page.locator("article")
        expect(article).to_contain_text("Halakhic man")
        expect(article).not_to_contain_text("Series")
