"""End-to-end tests for the rest of the 245.

Two things a MARC title statement carries that the catalog used to drop:
which part of a multi-part work this is (245 $n and $p), and who did
what (245 $c). Both decide whether a reader can tell one volume of a set
from the next, so both have to reach the screen.
"""

import pytest
from playwright.sync_api import expect

from catalog.models import Record
from catalog.search import ensure_fts_table
from ingest.models import ScanResult
from tests.e2e.conftest import login

STATEMENT = (
    "translated, annotated, and elucidated by Yisrael Isser Zvi Herczeg ; "
    "in collaboration with Yaakov Petroff and Yoseph Kamenetsky ; "
    "contributing editor, Avie Gold."
)

# A candidate as the parser hands it over: the cataloger's transcribed
# punctuation still on it, and a series statement whose volume number is
# its own datum rather than a restatement of the part designation.
MULTIVOLUME_CANDIDATE = {
    "title": "Rashi : the Torah, with Rashi's commentary /",
    "volume_part_number": "Volume 2,",
    "volume_part_title": "Sefer Mishpatim /",
    "statement_of_responsibility": STATEMENT,
    "author": "Rashi,",
    "additional_authors": ["Herczeg, Yisrael Isser Zvi."],
    "date": "1999",
    "publisher": "Mesorah Publications",
    "place": "Brooklyn, N.Y.",
    "language": "eng",
    "series_title": "ArtScroll series ;",
    "series_volume": "v. 2",
    "lccn": "2001531851",
    "source_catalog": "LC",
}

PLAIN_CANDIDATE = {
    "title": "Halakhic man /",
    "author": "Soloveitchik, Joseph Dov,",
    "date": "2007",
    "source_catalog": "NLI",
}


@pytest.fixture
def multivolume_record(db, staff_user):
    ensure_fts_table()
    return Record.objects.create(
        title="Rashi: the Torah, with Rashi's commentary",
        volume_part_number="Volume 2",
        volume_part_title="Sefer Mishpatim",
        statement_of_responsibility=STATEMENT,
        date_of_publication=1999,
        created_by=staff_user,
    )


@pytest.fixture
def multivolume_scan(db, staff_user):
    ensure_fts_table()
    return ScanResult.objects.create(
        scan_type="isbn",
        isbn="9780899060149",
        candidate_records=[MULTIVOLUME_CANDIDATE, PLAIN_CANDIDATE],
        scanned_by=staff_user,
    )


def record_url(live_server, record):
    return f"{live_server.url}/catalog/{record.record_id}/{record.slug}/"


@pytest.mark.django_db(transaction=True)
class TestRecordPage:
    def test_the_part_and_the_responsibility_read_under_the_title(
        self, page, live_server, multivolume_record
    ):
        login(page, live_server)
        page.goto(record_url(live_server, multivolume_record))

        header = page.locator("article header")
        expect(header).to_contain_text("Volume 2 : Sefer Mishpatim")
        expect(header).to_contain_text(STATEMENT)

    def test_a_part_with_no_name_shows_without_a_dangling_separator(
        self, page, live_server, staff_user
    ):
        ensure_fts_table()
        record = Record.objects.create(
            title="Collected works",
            volume_part_number="Volume 3",
            created_by=staff_user,
        )
        login(page, live_server)
        page.goto(record_url(live_server, record))

        header = page.locator("article header")
        expect(header).to_contain_text("Volume 3")
        assert ":" not in header.inner_text()

    def test_a_record_with_neither_shows_neither(
        self, page, live_server, sample_record
    ):
        login(page, live_server)
        page.goto(record_url(live_server, sample_record))

        header = page.locator("article header")
        expect(header).to_contain_text("The social life of information")
        header_text = header.inner_text()
        assert "Volume" not in header_text
        assert "translated" not in header_text


@pytest.mark.django_db(transaction=True)
class TestQueueRow:
    def test_the_part_reads_off_the_row_beside_the_title(
        self, page, live_server, multivolume_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        row = page.locator(f"#scan-{multivolume_scan.pk}-row-0")
        expect(row).to_contain_text("Volume 2, Sefer Mishpatim /")

    def test_the_series_statement_keeps_its_own_volume_number(
        self, page, live_server, multivolume_scan
    ):
        # 245 $n numbers the part within the title and 490 $v numbers the
        # item within a set. They can disagree, so neither stands in for
        # the other.
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        row = page.locator(f"#scan-{multivolume_scan.pk}-row-0")
        expect(row).to_contain_text("ArtScroll series")
        expect(row).to_contain_text("v. 2")

    def test_enough_of_the_responsibility_to_tell_editions_apart(
        self, page, live_server, multivolume_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        row = page.locator(f"#scan-{multivolume_scan.pk}-row-0")
        expect(row).to_contain_text("translated, annotated, and elucidated by")

    def test_a_candidate_with_neither_adds_no_empty_lines(
        self, page, live_server, multivolume_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/queue/")

        row = page.locator(f"#scan-{multivolume_scan.pk}-row-1")
        expect(row).to_contain_text("Halakhic man")
        assert "None" not in row.inner_text()


@pytest.mark.django_db(transaction=True)
class TestScanPollCard:
    def test_the_card_carries_the_part_and_the_whole_statement(
        self, page, live_server, multivolume_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/poll/")

        body = page.locator("body")
        expect(body).to_contain_text("Volume 2, Sefer Mishpatim /")
        expect(body).to_contain_text(STATEMENT)

    def test_a_candidate_without_them_renders_no_placeholder(
        self, page, live_server, multivolume_scan
    ):
        login(page, live_server)
        page.goto(f"{live_server.url}/ingest/scan/poll/")

        assert "None" not in page.locator("body").inner_text()
