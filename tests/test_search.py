import pytest
from django.db import connection

from catalog.models import Author, Record, Subject
from catalog.search import (
    FTS_TABLE,
    ensure_fts_table,
    index_record,
    search,
    search_records,
)


@pytest.mark.django_db
class TestFTS5Search:
    @pytest.fixture(autouse=True)
    def setup_fts(self):
        ensure_fts_table()

    def test_search_by_title(self):
        record = Record.objects.create(title="Mishneh Torah")
        index_record(record)
        results = search("Mishneh")
        assert len(results) == 1
        assert results[0][0] == record.record_id

    def test_search_hebrew_title(self):
        record = Record.objects.create(title="משנה תורה")
        index_record(record)
        results = search("משנה")
        assert len(results) == 1

    def test_search_by_romanized_title(self):
        record = Record.objects.create(
            title="משנה תורה", title_romanized="Mishneh Torah"
        )
        index_record(record)
        results = search("Mishneh")
        assert len(results) == 1

    def test_search_by_author(self):
        record = Record.objects.create(title="Guide for the Perplexed")
        author = Author.objects.create(
            name="רמבם", name_romanized="Maimonides"
        )
        record.authors.add(author)
        index_record(record)
        results = search("Maimonides")
        assert len(results) == 1

    def test_search_by_provenance(self):
        record = Record.objects.create(
            title="Sefer ha-Kuzari",
            provenance="Bookplate of the Sassoon family; acquired 1932.",
        )
        index_record(record)
        results = search("Sassoon")
        assert len(results) == 1
        assert results[0][0] == record.record_id

    def test_search_by_subject(self):
        record = Record.objects.create(title="Some Book")
        subject = Subject.objects.create(heading="Jewish law")
        record.subjects.add(subject)
        index_record(record)
        results = search("Jewish law")
        assert len(results) == 1

    def test_search_no_results(self):
        results = search("nonexistent")
        assert len(results) == 0

    def test_search_empty_query(self):
        results = search("")
        assert len(results) == 0

    def test_search_records_returns_objects(self):
        record = Record.objects.create(title="Test Book")
        index_record(record)
        records = search_records("Test")
        assert len(records) == 1
        assert records[0].pk == record.pk

    def test_multiple_results_ranked(self):
        r1 = Record.objects.create(title="Torah commentary")
        r2 = Record.objects.create(title="Torah study guide")
        index_record(r1)
        index_record(r2)
        results = search("Torah")
        assert len(results) == 2


# An earlier column list, without provenance. A catalog in use holds an
# FTS table of this shape until something rebuilds it.
STALE_FTS_COLUMNS = [
    "record_id UNINDEXED",
    "title",
    "title_romanized",
    "subtitle",
    "authors",
    "subjects",
    "publishers",
    "place",
    "notes",
    "identifiers",
]


def build_stale_fts_table(rows):
    """Replace the FTS table with one of an earlier shape, holding rows.

    Each row is a ``(record_id, title)`` pair, which is all the tests
    need to tell repopulated content from content that was there.
    """
    columns = ", ".join(STALE_FTS_COLUMNS)
    with connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {FTS_TABLE}")
        cursor.execute(
            f"CREATE VIRTUAL TABLE {FTS_TABLE} USING fts5({columns})"
        )
        for record_id, title in rows:
            cursor.execute(
                f"INSERT INTO {FTS_TABLE} (record_id, title) VALUES (%s, %s)",
                [record_id, title],
            )


@pytest.mark.django_db
class TestFTSSchemaChange:
    """The FTS table's schema is not covered by Django migrations.

    Making another field searchable changes the table's columns, so a
    database holding a table built from an earlier column list has to
    be caught and rebuilt; otherwise every insert fails on the column
    count and the new field is searchable only in a fresh database.
    """

    def test_stale_table_is_rebuilt_and_repopulated(self):
        record = Record.objects.create(
            title="Sefer ha-Kuzari",
            provenance="Bookplate of the Sassoon family",
        )
        build_stale_fts_table([(record.record_id, record.title)])

        ensure_fts_table()

        assert [r[0] for r in search("Sassoon")] == [record.record_id]
        assert [r[0] for r in search("Kuzari")] == [record.record_id]

    def test_indexing_survives_a_stale_table(self):
        record = Record.objects.create(title="Sefer ha-Kuzari")
        build_stale_fts_table([(record.record_id, record.title)])

        ensure_fts_table()
        record.provenance = "Inscribed by Solomon Schechter"
        record.save()
        index_record(record)

        assert [r[0] for r in search("Schechter")] == [record.record_id]

    def test_current_table_is_left_alone(self):
        ensure_fts_table()
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {FTS_TABLE} (record_id, title) VALUES (%s, %s)",
                ["otzar-gone", "Deaccessioned"],
            )

        ensure_fts_table()

        assert [r[0] for r in search("Deaccessioned")] == ["otzar-gone"]
