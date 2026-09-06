from contextlib import contextmanager
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import OperationalError, connection

import catalog.search
from catalog.models import Author, Record, Subject
from catalog.search import (
    FTS_TABLE,
    ensure_fts_table,
    hebrew_stems,
    index_record,
    reindex_all,
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


def fts_columns():
    """Return the FTS table's column names."""
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({FTS_TABLE})")
        return [row[1] for row in cursor.fetchall()]


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


@contextmanager
def record_column_hidden(column):
    """Hide a column of the record table for the duration of the block.

    Renaming a column away leaves the model declaring a field the
    database does not have, so every query against the record table
    raises ``OperationalError``. That is the state a catalog is in when
    the code is ahead of its migrations, and it is what interrupts a
    rebuild between recreating the table and filling it.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE catalog_record "
            f"RENAME COLUMN {column} TO {column}_hidden"
        )
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                f"ALTER TABLE catalog_record "
                f"RENAME COLUMN {column}_hidden TO {column}"
            )


@pytest.mark.django_db
class TestInterruptedRebuild:
    """A rebuild that does not finish must not leave a trusted empty table.

    The rebuild drops the table, recreates it and fills it. If the fill
    step does not run, the table is left with the right columns and no
    rows, which the shape comparison cannot tell from a table that is
    up to date. Search then returns nothing for every query, with no
    error, until someone reindexes by hand.
    """

    def test_a_failed_rebuild_leaves_the_old_table_in_place(self):
        record = Record.objects.create(
            title="Sefer ha-Kuzari",
            provenance="Bookplate of the Sassoon family",
        )
        build_stale_fts_table([(record.record_id, record.title)])

        with record_column_hidden("provenance"):
            with pytest.raises(OperationalError):
                ensure_fts_table()

            assert fts_columns() == [c.split()[0] for c in STALE_FTS_COLUMNS]

        assert [r[0] for r in search("Kuzari")] == [record.record_id]

    def test_a_dropped_table_is_repopulated(self):
        record = Record.objects.create(title="Sefer ha-Kuzari")
        ensure_fts_table()
        index_record(record)

        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE {FTS_TABLE}")

        assert [r[0] for r in search("Kuzari")] == [record.record_id]


@pytest.mark.django_db
class TestUnindexableRecords:
    """One record that cannot be indexed should not cost search the rest."""

    def test_a_record_that_cannot_be_indexed_is_skipped(self, monkeypatch):
        good = Record.objects.create(title="Sefer ha-Kuzari")
        bad = Record.objects.create(title="Mishneh Torah")
        _fail_row_values_for(monkeypatch, {bad.record_id})

        indexed, skipped = reindex_all()

        assert indexed == 1
        assert skipped == [bad.record_id]
        assert [r[0] for r in search("Kuzari")] == [good.record_id]
        assert search("Mishneh") == []

    def test_a_rebuild_that_indexes_nothing_fails(self, monkeypatch):
        record = Record.objects.create(title="Sefer ha-Kuzari")
        ensure_fts_table()
        index_record(record)
        _fail_row_values_for(monkeypatch, {record.record_id})

        with pytest.raises(ValueError):
            reindex_all()

        assert [r[0] for r in search("Kuzari")] == [record.record_id]


def _fail_row_values_for(monkeypatch, record_ids):
    """Make indexing raise for the given records and work for the rest."""
    original = catalog.search._row_values

    def _row_values(record):
        if record.record_id in record_ids:
            raise ValueError(f"cannot index {record.record_id}")
        return original(record)

    monkeypatch.setattr(catalog.search, "_row_values", _row_values)


@pytest.mark.django_db(transaction=True)
def test_a_failed_rebuild_rolls_back_a_real_transaction():
    """The rollback has to hold where it counts, in a real transaction.

    Tests otherwise run inside one already, which turns the rebuild's
    atomic block into a savepoint. A search in a running catalog opens
    the transaction itself, and that is the path this covers.
    """
    record = Record.objects.create(
        title="Sefer ha-Kuzari", provenance="Bookplate of the Sassoon family"
    )
    try:
        build_stale_fts_table([(record.record_id, record.title)])

        with record_column_hidden("provenance"):
            with pytest.raises(OperationalError):
                ensure_fts_table()
            assert fts_columns() == [c.split()[0] for c in STALE_FTS_COLUMNS]

        assert [r[0] for r in search("Kuzari")] == [record.record_id]
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {FTS_TABLE}")


@pytest.mark.django_db
class TestReindexCommand:
    """The command an operator recovers an index with."""

    def test_it_rebuilds_a_dropped_table(self):
        record = Record.objects.create(title="Sefer ha-Kuzari")
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {FTS_TABLE}")

        out = StringIO()
        call_command("reindex", stdout=out)

        assert "Indexed 1 record" in out.getvalue()
        assert [r[0] for r in search("Kuzari")] == [record.record_id]

    def test_it_reports_records_it_could_not_index(self, monkeypatch):
        good = Record.objects.create(title="Sefer ha-Kuzari")
        bad = Record.objects.create(title="Mishneh Torah")
        _fail_row_values_for(monkeypatch, {bad.record_id})

        out = StringIO()
        call_command("reindex", stdout=out)

        assert "Indexed 1 record" in out.getvalue()
        assert bad.record_id in out.getvalue()
        assert [r[0] for r in search("Kuzari")] == [good.record_id]


# Every editable field of the record change form, so a test can post it
# with one value changed and have the form validate.
RECORD_FORM_DEFAULTS = {
    "slug": "",
    "title_romanized": "",
    "subtitle": "",
    "date_of_publication": "",
    "date_of_publication_display": "",
    "place_of_publication": "",
    "language": "",
    "source_marc": "",
    "source_catalog": "",
    "cover_url": "",
    "notes": "",
    "provenance": "",
    "created_by": "",
    "authors": [],
    "subjects": [],
    "publishers": [],
    "locations": [],
    "external_identifiers-TOTAL_FORMS": "0",
    "external_identifiers-INITIAL_FORMS": "0",
    "external_identifiers-MIN_NUM_FORMS": "0",
    "external_identifiers-MAX_NUM_FORMS": "1000",
    "title_page_images-TOTAL_FORMS": "0",
    "title_page_images-INITIAL_FORMS": "0",
    "title_page_images-MIN_NUM_FORMS": "0",
    "title_page_images-MAX_NUM_FORMS": "1000",
}


@pytest.mark.django_db
class TestAdminIndexMaintenance:
    """Writes made through the admin have to reach the index.

    The index denormalizes a record's own text along with the names of
    the authors, subjects and publishers it links to, so an admin write
    that never reaches the index leaves search answering with text the
    catalog no longer holds.
    """

    @pytest.fixture
    def superuser_client(self, client, django_user_model):
        django_user_model.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )
        client.login(username="admin", password="pw")
        ensure_fts_table()
        return client

    def test_editing_a_record_updates_the_index(self, superuser_client):
        record = Record.objects.create(title="Sefer ha-Kuzari")
        index_record(record)

        response = superuser_client.post(
            f"/admin/catalog/record/{record.pk}/change/",
            {**RECORD_FORM_DEFAULTS, "title": "Sefer ha-Zohar"},
        )

        assert response.status_code == 302
        assert [r[0] for r in search("Zohar")] == [record.record_id]
        assert search("Kuzari") == []

    def test_deleting_a_record_clears_its_index_entry(self, superuser_client):
        record = Record.objects.create(title="Sefer ha-Kuzari")
        index_record(record)

        response = superuser_client.post(
            f"/admin/catalog/record/{record.pk}/delete/", {"post": "yes"}
        )

        assert response.status_code == 302
        assert search("Kuzari") == []

    def test_renaming_an_author_reindexes_their_records(
        self, superuser_client
    ):
        author = Author.objects.create(name="Halevi, Yehudah")
        record = Record.objects.create(title="Sefer ha-Kuzari")
        record.authors.add(author)
        index_record(record)

        response = superuser_client.post(
            f"/admin/catalog/author/{author.pk}/change/",
            {
                "name": "Judah Halevi",
                "name_romanized": "",
                "viaf_id": "",
                "variant_names": "[]",
            },
        )

        assert response.status_code == 302
        assert [r[0] for r in search("Judah")] == [record.record_id]
        assert search("Yehudah") == []

    def test_deleting_an_author_reindexes_their_records(
        self, superuser_client
    ):
        author = Author.objects.create(name="Halevi, Yehudah")
        record = Record.objects.create(title="Sefer ha-Kuzari")
        record.authors.add(author)
        index_record(record)

        response = superuser_client.post(
            f"/admin/catalog/author/{author.pk}/delete/", {"post": "yes"}
        )

        assert response.status_code == 302
        assert search("Yehudah") == []
        assert [r[0] for r in search("Kuzari")] == [record.record_id]


def index_titles(*titles):
    """Create and index one record per title, returning them in order."""
    records = [Record.objects.create(title=title) for title in titles]
    for record in records:
        index_record(record)
    return records


def index_filler(count=6):
    """Index unrelated records so bm25 has a rarity to weight hits by.

    bm25 scores a phrase by how rare it is across the index. With two
    records in the index and both matching, the phrase is in every row,
    its weight rounds to nothing, and the order between the two is
    arbitrary. A few records that match nothing make the phrase rare
    enough to rank by, which is the state a real catalog is in.
    """
    index_titles(*(f"Unrelated filler {i}" for i in range(count)))


def result_ids(query):
    return [record_id for record_id, _rank in search(query)]


@pytest.mark.django_db
class TestPrefixMatching:
    """A search word matches every word that begins with it.

    FTS5 supports this natively, but its ranking does not tell a whole
    word from a longer one: a record carrying the longer word several
    times outranks the record carrying the word itself. The query has to
    ask for the whole word as well as the prefix so the exact hit scores
    on both.
    """

    @pytest.fixture(autouse=True)
    def setup_fts(self):
        ensure_fts_table()

    def test_a_partial_word_finds_the_whole_word(self):
        (record,) = index_titles("Rambam on the Torah")
        assert result_ids("Ramb") == [record.record_id]

    def test_every_word_of_a_query_is_a_prefix(self):
        (record,) = index_titles("Guide for the Perplexed")
        assert result_ids("gui perp") == [record.record_id]

    def test_a_prefix_matches_the_start_of_a_word_only(self):
        index_titles("Rambam")
        assert result_ids("amba") == []

    def test_every_word_still_has_to_match(self):
        index_titles("Rambam")
        assert result_ids("Ramb xyz") == []

    def test_a_partial_hebrew_word_finds_the_whole_word(self):
        (record,) = index_titles("משנה תורה")
        assert result_ids("משנ") == [record.record_id]

    def test_the_whole_word_outranks_a_longer_word(self):
        index_filler()
        exact, longer = index_titles(
            "Torah commentary", "Torahs, Torahs and more Torahs"
        )
        assert result_ids("Torah") == [exact.record_id, longer.record_id]

    def test_letters_before_gershayim_find_the_abbreviation(self):
        """The tokenizer splits an abbreviation at the gershayim.

        רמב״ם is indexed as רמב followed by ם, so the letters before
        the mark reach it as a prefix; the abbreviation typed without
        the mark does not, because no token is רמבם.
        """
        (record,) = index_titles("פירוש הרמב״ם")
        assert result_ids("רמב") == [record.record_id]
        assert result_ids("רמב״ם") == [record.record_id]
        assert result_ids("רמבם") == []

    def test_a_straight_quote_in_a_query_is_not_syntax(self):
        """A quote typed as an abbreviation mark must not break the query.

        FTS5 delimits phrases with double quotes, so a query carrying
        one has to escape it rather than raise a syntax error.
        """
        (record,) = index_titles('פירוש הרמב"ם')
        assert result_ids('רמב"ם') == [record.record_id]
        assert result_ids('"') == []

    def test_a_word_of_punctuation_alone_is_ignored(self):
        """A word that tokenizes to nothing cannot be required to match."""
        (record,) = index_titles("Torah commentary")
        assert result_ids("Torah - commentary") == [record.record_id]
        assert result_ids("-") == []


@pytest.mark.django_db
class TestHebrewParticles:
    """Hebrew attaches ב, ה, ו, כ, ל, מ and ש to the front of a word.

    The tokenizer cannot split them off, so every Hebrew word is also
    indexed with up to two leading particle letters removed, as long as
    two letters remain, and a query word beginning with those letters
    is also searched without them. The rule cannot tell a particle from
    a letter of the word, and the tests below pin where it is wrong as
    well as where it is right.
    """

    @pytest.fixture(autouse=True)
    def setup_fts(self):
        ensure_fts_table()

    @pytest.mark.parametrize("particle", list("בהוכלמש"))
    def test_the_base_word_finds_each_particle(self, particle):
        (record,) = index_titles(f"{particle}ספר")
        assert result_ids("ספר") == [record.record_id]

    def test_the_base_word_finds_two_stacked_particles(self):
        ubasefer, mehasefer, shebikhtav = index_titles(
            "ובספר", "מהספר", "תורה שבכתב"
        )
        assert set(result_ids("ספר")) == {
            ubasefer.record_id,
            mehasefer.record_id,
        }
        assert result_ids("כתב") == [shebikhtav.record_id]

    def test_only_two_particles_are_stripped(self):
        index_titles("ולכשיבוא")
        assert result_ids("יבוא") == []

    def test_a_prefixed_query_finds_the_base_word(self):
        (record,) = index_titles("כוזרי")
        assert result_ids("הכוזרי") == [record.record_id]

    def test_a_prefixed_query_finds_another_particle(self):
        (record,) = index_titles("בספר")
        assert result_ids("הספר") == [record.record_id]

    def test_the_written_form_outranks_a_stripped_one(self):
        index_filler()
        written, article, number = index_titles("ספר", "הספר", "מספר")
        ids = result_ids("ספר")
        assert ids[0] == written.record_id
        assert set(ids[1:]) == {article.record_id, number.record_id}

    def test_stems_are_indexed_from_every_text_field(self):
        record = Record.objects.create(title="אורות")
        record.authors.add(Author.objects.create(name="הרב קוק"))
        record.subjects.add(Subject.objects.create(heading="בפילוסופיה"))
        index_record(record)
        assert result_ids("רב קוק") == [record.record_id]
        assert result_ids("פילוסופיה") == [record.record_id]

    def test_a_stem_keeps_at_least_two_letters(self):
        """הרב is the rabbi, and needs the stem רב for the bare noun to
        find it; הר is the mountain, and a stem of ר would match nothing
        useful, so it is not made. The query הר still reaches הרב, as a
        prefix, but not the ר of ר׳ עקיבא.
        """
        harav, mountain, rabbi = index_titles("הרב", "הר סיני", "ר׳ עקיבא")
        assert result_ids("רב") == [harav.record_id]
        assert set(result_ids("הר")) == {harav.record_id, mountain.record_id}

    # Where the rule is wrong.

    def test_a_root_letter_is_taken_for_a_particle(self):
        """מספר is a number and משה is Moses; neither carries a particle."""
        number, moses, heaven = index_titles("מספר", "משה", "שמים")
        assert result_ids("ספר") == [number.record_id]
        assert result_ids("שה") == [moses.record_id]
        assert result_ids("מים") == [heaven.record_id]

    def test_a_stripped_query_matches_whole_words_only(self):
        """Stripping a query word does not also widen it to a prefix.

        A prefix on the stem would turn every word beginning with a
        particle letter into a broad search: במדבר, the book of Numbers,
        strips to דבר and would then match דברים, Deuteronomy. The cost
        is that הספר does not reach ספרים; the base word ספר does.
        """
        numbers, deuteronomy, books = index_titles("במדבר", "דברים", "ספרים")
        assert result_ids("במדבר") == [numbers.record_id]
        assert result_ids("הספר") == []
        assert result_ids("ספר") == [books.record_id]

    def test_a_construct_form_is_not_matched(self):
        """תורת is the construct of תורה; the ending changes, not the start."""
        index_titles("תורת משה")
        assert result_ids("תורה") == []


class TestHebrewStems:
    """The stripping rule itself, on single words."""

    @pytest.mark.parametrize(
        "word, stems",
        [
            ("ספר", []),
            ("הספר", ["ספר"]),
            ("ובספר", ["בספר", "ספר"]),
            ("ולכשיבוא", ["לכשיבוא", "כשיבוא"]),
            ("הרב", ["רב"]),
            ("הר", []),
            ("בן", []),
            ("רמב״ם", []),
            ("והרמב״ם", ["הרמב״ם", "רמב״ם"]),
            ("בְּרֵאשִׁית", ["רֵאשִׁית"]),
            ("Sefer", []),
            ("", []),
        ],
    )
    def test_stems(self, word, stems):
        assert hebrew_stems(word) == stems
