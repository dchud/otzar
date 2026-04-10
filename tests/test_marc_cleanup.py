"""Tests for MARC punctuation cleaning utility and management command."""

import pytest

from catalog.utils import strip_marc_punctuation


class TestStripMarcPunctuation:
    """Unit tests for the strip_marc_punctuation utility."""

    def test_trailing_colon(self):
        assert strip_marc_punctuation("Boston :") == "Boston"

    def test_trailing_semicolon(self):
        assert strip_marc_punctuation("New York ;") == "New York"

    def test_trailing_slash(self):
        assert strip_marc_punctuation("Some title /") == "Some title"

    def test_trailing_comma(self):
        assert strip_marc_punctuation("Harvard Business School Press,") == (
            "Harvard Business School Press"
        )

    def test_trailing_period_after_name(self):
        assert strip_marc_punctuation("Brown, John Seely.") == "Brown, John Seely"

    def test_trailing_period_after_name_with_comma(self):
        assert strip_marc_punctuation("Duguid, Paul,") == "Duguid, Paul"

    def test_preserve_initial(self):
        assert strip_marc_punctuation("John A.") == "John A."

    def test_preserve_single_initial(self):
        assert strip_marc_punctuation("J.") == "J."

    def test_preserve_abbreviation_jr(self):
        assert strip_marc_punctuation("Martin Luther King Jr.") == (
            "Martin Luther King Jr."
        )

    def test_preserve_abbreviation_sr(self):
        assert strip_marc_punctuation("John Smith Sr.") == "John Smith Sr."

    def test_preserve_abbreviation_inc(self):
        assert strip_marc_punctuation("Acme Inc.") == "Acme Inc."

    def test_preserve_abbreviation_dr(self):
        assert strip_marc_punctuation("Dr.") == "Dr."

    def test_preserve_abbreviation_ed(self):
        assert strip_marc_punctuation("2nd ed.") == "2nd ed."

    def test_preserve_ellipsis(self):
        assert strip_marc_punctuation("And so on...") == "And so on..."

    def test_whitespace_stripping(self):
        assert strip_marc_punctuation("  spaced  ") == "spaced"

    def test_none_returns_empty(self):
        assert strip_marc_punctuation(None) == ""

    def test_empty_returns_empty(self):
        assert strip_marc_punctuation("") == ""

    def test_whitespace_only_returns_empty(self):
        assert strip_marc_punctuation("   ") == ""

    def test_no_punctuation_unchanged(self):
        assert strip_marc_punctuation("A normal title") == "A normal title"

    def test_combined_trailing_comma_and_space(self):
        assert strip_marc_punctuation("Title,") == "Title"

    def test_preserve_abbreviation_prof(self):
        assert strip_marc_punctuation("Prof.") == "Prof."

    def test_preserve_abbreviation_ltd(self):
        assert strip_marc_punctuation("Company Ltd.") == "Company Ltd."


@pytest.mark.django_db
class TestCleanMarcPunctuationCommand:
    """Tests for the clean_marc_punctuation management command."""

    def test_dry_run_does_not_modify(self):
        from io import StringIO

        from django.core.management import call_command

        from catalog.models import Record

        record = Record.objects.create(
            title="Boston :", place_of_publication="New York ;"
        )
        out = StringIO()
        call_command("clean_marc_punctuation", "--dry-run", stdout=out)

        record.refresh_from_db()
        assert record.title == "Boston :"
        assert record.place_of_publication == "New York ;"
        assert "DRY RUN" in out.getvalue()

    def test_actual_run_cleans_records(self):
        from io import StringIO

        from django.core.management import call_command

        from catalog.models import Author, Publisher, Record, Subject

        record = Record.objects.create(
            title="Some title /",
            title_romanized="Alternate,",
            place_of_publication="Boston :",
            subtitle="A subtitle ;",
        )
        author = Author.objects.create(name="Smith, John.")
        publisher = Publisher.objects.create(name="Acme Press,")
        subject = Subject.objects.create(heading="History.")

        out = StringIO()
        call_command("clean_marc_punctuation", stdout=out)

        record.refresh_from_db()
        assert record.title == "Some title"
        assert record.title_romanized == "Alternate"
        assert record.place_of_publication == "Boston"
        assert record.subtitle == "A subtitle"

        author.refresh_from_db()
        assert author.name == "Smith, John"

        publisher.refresh_from_db()
        assert publisher.name == "Acme Press"

        subject.refresh_from_db()
        assert subject.heading == "History"

        output = out.getvalue()
        assert "Records changed:" in output
        assert "Authors changed:" in output

    def test_preserves_clean_data(self):
        from io import StringIO

        from django.core.management import call_command

        from catalog.models import Record

        record = Record.objects.create(title="Already Clean")
        out = StringIO()
        call_command("clean_marc_punctuation", stdout=out)

        record.refresh_from_db()
        assert record.title == "Already Clean"
        assert "Records changed:    0" in out.getvalue()
