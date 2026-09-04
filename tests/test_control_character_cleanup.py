"""Tests for the C1 control character repair management command."""

import re
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection

from catalog.management.commands.clean_control_characters import (
    text_field_names,
)
from catalog.models import Author, Publisher, Record, Subject
from catalog.search import FTS_TABLE, ensure_fts_table, index_record

# The MARC non-sorting delimiters, as they arrive from DNB.
NSB = "\u0098"
NSE = "\u009c"

# A title as DNB supplies it: the leading article is bracketed, and both
# delimiters render as nothing, so the title reads as though it had
# stray whitespace in it.
DIRTY_TITLE = f"{NSB}The{NSE} Complete Piano Etudes"
CLEAN_TITLE = "The Complete Piano Etudes"


def run(*args):
    """Call the command, returning its stdout."""
    out = StringIO()
    call_command("clean_control_characters", *args, stdout=out)
    return out.getvalue()


def indexed_column(record, column):
    """Return one column of the record's row in the FTS table."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {column} FROM {FTS_TABLE} WHERE record_id = %s",
            [record.record_id],
        )
        row = cursor.fetchone()
    return row[0] if row else None


class TestTextFieldNames:
    """The scanned field list is derived from the model."""

    def test_includes_every_editable_text_field(self):
        names = text_field_names(Record)
        for expected in (
            "slug",
            "title",
            "title_romanized",
            "subtitle",
            "date_of_publication_display",
            "place_of_publication",
            "language",
            "source_catalog",
            "cover_url",
            "notes",
        ):
            assert expected in names

    def test_excludes_non_text_columns(self):
        names = text_field_names(Record)
        assert "date_of_publication" not in names
        assert "source_marc" not in names
        assert "created_at" not in names

    def test_excludes_generated_identifiers(self):
        assert "record_id" not in text_field_names(Record)

    def test_excludes_relations(self):
        names = text_field_names(Record)
        assert "authors" not in names
        assert "created_by" not in names

    def test_covers_the_related_models(self):
        assert set(text_field_names(Author)) >= {"name", "name_romanized"}
        assert set(text_field_names(Publisher)) >= {"name", "place"}
        assert set(text_field_names(Subject)) >= {
            "heading",
            "heading_romanized",
        }


@pytest.mark.django_db
class TestReportingRun:
    """Without --apply the command reports and writes nothing."""

    def test_reporting_is_the_default(self):
        record = Record.objects.create(title=DIRTY_TITLE)

        output = run()

        record.refresh_from_db()
        assert record.title == DIRTY_TITLE
        assert "--apply" in output

    def test_report_names_the_row_and_the_field(self):
        record = Record.objects.create(title=DIRTY_TITLE)

        output = run()

        assert record.record_id in output
        assert "title" in output
        assert CLEAN_TITLE in output

    def test_report_leaves_the_index_alone(self):
        ensure_fts_table()
        record = Record.objects.create(title=DIRTY_TITLE)
        index_record(record)

        run()

        assert NSB in indexed_column(record, "title")


@pytest.mark.django_db
class TestRepair:
    """--apply rewrites the affected fields."""

    def test_repairs_a_title(self):
        record = Record.objects.create(title=DIRTY_TITLE)

        run("--apply")

        record.refresh_from_db()
        assert record.title == CLEAN_TITLE

    def test_repairs_a_non_title_field(self):
        record = Record.objects.create(
            title="Clean", notes=f"{NSB}A{NSE} note"
        )

        run("--apply")

        record.refresh_from_db()
        assert record.title == "Clean"
        assert record.notes == "A note"

    def test_repairs_every_editable_text_field(self):
        record = Record.objects.create(title="Placeholder")
        names = text_field_names(Record)
        for name in names:
            setattr(record, name, f"{NSB}{name}{NSE}")
        record.save()

        run("--apply")

        record.refresh_from_db()
        for name in names:
            assert getattr(record, name) == name

    def test_repairs_related_models(self):
        author = Author.objects.create(name=f"{NSB}Bach{NSE}, Johann")
        publisher = Publisher.objects.create(name=f"{NSB}Henle{NSE}")
        subject = Subject.objects.create(heading=f"{NSB}Piano{NSE} music")

        run("--apply")

        author.refresh_from_db()
        publisher.refresh_from_db()
        subject.refresh_from_db()
        assert author.name == "Bach, Johann"
        assert publisher.name == "Henle"
        assert subject.heading == "Piano music"

    def test_leaves_clean_rows_untouched(self):
        record = Record.objects.create(title=CLEAN_TITLE, notes="A note")
        before = record.updated_at

        output = run("--apply")

        record.refresh_from_db()
        assert record.title == CLEAN_TITLE
        assert record.updated_at == before
        assert re.search(r"Records changed:\s+0", output)

    def test_does_not_rewrite_source_marc(self):
        record = Record.objects.create(
            title=DIRTY_TITLE, source_marc={"245": DIRTY_TITLE}
        )

        run("--apply")

        record.refresh_from_db()
        assert record.source_marc == {"245": DIRTY_TITLE}


@pytest.mark.django_db
class TestReindexing:
    """A repaired record is re-indexed, or the old bytes stay searchable."""

    def test_index_reflects_a_repaired_title(self):
        ensure_fts_table()
        record = Record.objects.create(title=DIRTY_TITLE)
        index_record(record)
        assert NSB in indexed_column(record, "title")

        run("--apply")

        assert indexed_column(record, "title") == CLEAN_TITLE

    def test_index_reflects_a_repaired_author(self):
        ensure_fts_table()
        record = Record.objects.create(title=CLEAN_TITLE)
        author = Author.objects.create(name=f"{NSB}Bach{NSE}, Johann")
        record.authors.add(author)
        index_record(record)
        assert NSB in indexed_column(record, "authors")

        run("--apply")

        authors = indexed_column(record, "authors")
        assert NSB not in authors
        assert "Bach" in authors

    def test_index_is_not_duplicated(self):
        ensure_fts_table()
        record = Record.objects.create(title=DIRTY_TITLE)
        index_record(record)

        run("--apply")

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) FROM {FTS_TABLE} WHERE record_id = %s",
                [record.record_id],
            )
            assert cursor.fetchone()[0] == 1
