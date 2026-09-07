"""What a person sees of the two things a series statement can be.

A publisher's line and a work issued in parts arrive in the same MARC
field. The catalog reads them apart, and the difference has to reach the
screen: a work-set shows volumes and the gaps in them, a publisher's
series shows the books that carry it and nothing to complete. Where the
reading is wrong, the page a person notices it on is the page they fix
it on, and the fix has to survive the next record that disagrees.
"""

import pytest
from playwright.sync_api import expect

from catalog.models import Record, Series
from catalog.search import ensure_fts_table
from ingest.models import ScanResult
from tests.e2e.conftest import login

# A publisher's label: nothing in the record names it as a work.
ARTSCROLL_CANDIDATE = {
    "title": "Bereshit /",
    "author": "Scherman, Nosson,",
    "date": "2018",
    "publisher": "Mesorah Publications",
    "place": "Brooklyn, N.Y.",
    "language": "eng",
    "series_title": "ArtScroll series ;",
    "source_catalog": "LC",
}

# A work in parts: the uniform title names the same work the series
# statement does, which is what says the two are one thing.
TALMUD_CANDIDATE = {
    "title": "Pesahim /",
    "date": "1990",
    "language": "heb",
    "series_title": "Talmud Bavli.",
    "series_volume": "v. 3",
    "uniform_title": {
        "work": "Talmud Bavli",
        "part_name": "Pesahim",
        "source": "130",
    },
    "source_catalog": "NLI",
}


@pytest.fixture
def artscroll_scan(db, staff_user):
    ensure_fts_table()
    return ScanResult.objects.create(
        scan_type="isbn",
        isbn="9781422617892",
        candidate_records=[ARTSCROLL_CANDIDATE],
        scanned_by=staff_user,
    )


@pytest.fixture
def talmud_scan(db, staff_user):
    ensure_fts_table()
    return ScanResult.objects.create(
        scan_type="isbn",
        isbn="9781422617893",
        candidate_records=[TALMUD_CANDIDATE],
        scanned_by=staff_user,
    )


def confirm_first_candidate(page, live_server, scan):
    page.goto(f"{live_server.url}/ingest/queue/")
    page.click(f"#scan-{scan.pk}-row-0")
    detail = page.locator(f"#scan-{scan.pk}-candidate-0")
    detail.get_by_role("button", name="Confirm").click()
    page.wait_for_url("**/ingest/queue/", timeout=10000)


def record_url(live_server, record):
    return f"{live_server.url}/catalog/{record.record_id}/{record.slug}/"


@pytest.mark.django_db(transaction=True)
class TestConfirmingAPublishersSeries:
    def test_the_record_says_where_it_was_published_not_which_volume(
        self, page, live_server, artscroll_scan
    ):
        login(page, live_server)
        confirm_first_candidate(page, live_server, artscroll_scan)

        record = Record.objects.get(title="Bereshit")
        page.goto(record_url(live_server, record))

        expect(page.get_by_text("Published in")).to_be_visible()
        expect(
            page.get_by_role("link", name="ArtScroll series")
        ).to_be_visible()

    def test_the_series_page_offers_nothing_to_complete(
        self, page, live_server, artscroll_scan
    ):
        login(page, live_server)
        confirm_first_candidate(page, live_server, artscroll_scan)

        series = Series.objects.get(title="ArtScroll series")
        page.goto(f"{live_server.url}/ingest/series/{series.pk}/")

        expect(page.get_by_text("Records in this series")).to_be_visible()
        expect(page.get_by_role("heading", name="Add volumes")).to_have_count(
            0
        )
        expect(page.get_by_text("Missing volumes")).to_have_count(0)

    def test_browsing_series_counts_it_by_record(
        self, page, live_server, artscroll_scan
    ):
        login(page, live_server)
        confirm_first_candidate(page, live_server, artscroll_scan)

        page.goto(f"{live_server.url}/browse/series/")

        expect(page.get_by_text("Publisher's series")).to_be_visible()
        expect(page.get_by_text("1 record")).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestConfirmingAWorkInParts:
    def test_the_series_page_offers_volumes_to_add(
        self, page, live_server, talmud_scan
    ):
        login(page, live_server)
        confirm_first_candidate(page, live_server, talmud_scan)

        series = Series.objects.get(title="Talmud Bavli")
        page.goto(f"{live_server.url}/ingest/series/{series.pk}/")

        expect(page.get_by_role("heading", name="Add volumes")).to_be_visible()
        expect(page.get_by_label("Volume specification")).to_be_visible()

    def test_adding_volumes_shows_which_are_not_held(
        self, page, live_server, talmud_scan
    ):
        """A set of four with one in hand leaves three to look for."""
        login(page, live_server)
        confirm_first_candidate(page, live_server, talmud_scan)

        series = Series.objects.get(title="Talmud Bavli")
        page.goto(f"{live_server.url}/ingest/series/{series.pk}/")
        page.get_by_label("Volume specification").fill("1-4")
        page.get_by_role("button", name="Add volumes").click()

        expect(page.get_by_role("cell", name="Gap")).to_have_count(3)
        expect(page.get_by_role("link", name="Pesahim")).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestCorrectingTheReading:
    def test_a_person_can_refile_a_series_and_the_fix_holds(
        self, page, live_server, talmud_scan, staff_user
    ):
        """The correction outlasts a record arriving with the other reading.

        Two unrelated things can share a title, so a person has to be
        able to say a series is a publisher's line even where the copy
        cataloging reads it as a work. Once said, the next record does
        not get to say otherwise.
        """
        ensure_fts_table()
        series = Series.objects.create(
            title="Talmud Bavli", kind=Series.KIND_WORK
        )

        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/series/{series.pk}/")
        page.get_by_label("Publisher's series").check()
        page.get_by_role("button", name="Save kind").click()

        expect(
            page.get_by_text("Recorded as a publisher's series")
        ).to_be_visible()

        confirm_first_candidate(page, live_server, talmud_scan)

        series.refresh_from_db()
        assert series.kind == Series.KIND_IMPRINT
        assert series.volumes.count() == 0

        page.goto(f"{live_server.url}/ingest/series/{series.pk}/")
        expect(page.get_by_text("Records in this series")).to_be_visible()
        expect(page.get_by_role("heading", name="Add volumes")).to_have_count(
            0
        )
