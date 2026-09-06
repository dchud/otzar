"""Search over the marks of ownership a copy carries.

A bookplate, a dedication and a stamp are separate fields because they
are separate things, and each has to be findable on its own -- a phrase
that appears in only one of them has to reach the record that holds it.
"""

import pytest

from catalog.models import Record
from catalog.search import (
    FTS_TEXT_COLUMNS,
    ensure_fts_table,
    index_record,
    search,
)

MARKS = {
    "bookplate_text": ("Ex libris David Solomon Sassoon", "Sassoon"),
    "dedication_text": ("To Rivka, from her father, 1932.", "Rivka"),
    "stamp_text": ("Alliance Israélite Universelle, Paris", "Israélite"),
}


@pytest.mark.django_db
class TestOwnershipMarkSearch:
    @pytest.fixture(autouse=True)
    def setup_fts(self):
        ensure_fts_table()

    @pytest.mark.parametrize("field", sorted(MARKS))
    def test_a_record_is_found_by_a_phrase_from_one_mark(self, field):
        value, term = MARKS[field]
        record = Record.objects.create(
            title="Sefer ha-Kuzari", **{field: value}
        )
        index_record(record)

        assert [r[0] for r in search(term)] == [record.record_id]

    @pytest.mark.parametrize("field", sorted(MARKS))
    def test_a_mark_is_indexed_without_the_others_being_set(self, field):
        # Each field feeds its own FTS column, so a record carrying one
        # mark and not the others still indexes: an empty column is a
        # value, not a missing one.
        value, term = MARKS[field]
        record = Record.objects.create(title="Unmarked", **{field: value})
        index_record(record)

        for other, (_, other_term) in MARKS.items():
            expected = [record.record_id] if other == field else []
            assert [r[0] for r in search(other_term)] == expected

    def test_every_mark_is_declared_searchable(self):
        assert set(MARKS) <= set(FTS_TEXT_COLUMNS.values())

    def test_an_edit_that_adds_a_mark_reaches_the_index(self):
        record = Record.objects.create(title="Sefer ha-Kuzari")
        index_record(record)
        assert search("Sassoon") == []

        record.bookplate_text = "Ex libris David Solomon Sassoon"
        record.save()
        index_record(record)

        assert [r[0] for r in search("Sassoon")] == [record.record_id]
