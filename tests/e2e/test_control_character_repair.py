"""End-to-end check that a repaired title renders without stray gaps."""

import pytest
from django.core.management import call_command

from catalog.models import Record
from catalog.search import ensure_fts_table, index_record

# The MARC non-sorting delimiters, as they arrive from DNB.
NSB = "\u0098"
NSE = "\u009c"


@pytest.mark.django_db(transaction=True)
class TestRepairedTitleRendering:
    def test_delimiters_show_as_a_gap_before_the_repair(
        self, page, live_server
    ):
        record = self._dnb_record()

        page.goto(f"{live_server.url}/catalog/{record.record_id}/")

        heading = page.locator("h1").text_content()
        assert NSB in heading

    def test_title_reads_cleanly_after_the_repair(self, page, live_server):
        record = self._dnb_record()

        call_command("clean_control_characters", "--apply")

        page.goto(f"{live_server.url}/catalog/{record.record_id}/")

        heading = page.locator("h1").text_content().strip()
        assert NSB not in heading
        assert NSE not in heading
        assert heading == "The Complete Piano Etudes"

    def _dnb_record(self):
        ensure_fts_table()
        record = Record.objects.create(
            title=f"{NSB}The{NSE} Complete Piano Etudes",
            source_catalog="DNB",
        )
        index_record(record)
        return record
