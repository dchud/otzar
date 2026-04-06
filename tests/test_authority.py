"""Tests for authority matching and series workflow modules."""

import pytest

from catalog.models import Author, Record, Series, SeriesVolume
from ingest.authority import find_author_matches, normalize_for_comparison
from ingest.series_workflow import (
    create_series_volumes,
    detect_series_from_marc,
    find_matching_series,
)


class TestNormalizeForComparison:
    def test_strips_punctuation(self):
        assert normalize_for_comparison('Hello, "World"!') == "hello world!"

    def test_lowercases(self):
        assert normalize_for_comparison("FOO BAR") == "foo bar"

    def test_strips_hebrew_punctuation(self):
        assert normalize_for_comparison("שם׳ הכהן") == "שם הכהן"

    def test_collapses_whitespace(self):
        assert normalize_for_comparison("  foo   bar  ") == "foo bar"

    def test_empty_string(self):
        assert normalize_for_comparison("") == ""

    def test_none_returns_empty(self):
        assert normalize_for_comparison(None) == ""


@pytest.mark.django_db
class TestFindAuthorMatchesExact:
    def test_exact_name_match(self):
        author = Author.objects.create(name="Rashi")
        matches = find_author_matches("Rashi")
        assert len(matches) == 1
        assert matches[0] == (author, "exact")

    def test_no_match(self):
        Author.objects.create(name="Rashi")
        matches = find_author_matches("Rambam")
        assert len(matches) == 0


@pytest.mark.django_db
class TestFindAuthorMatchesRomanized:
    def test_romanized_name_match(self):
        author = Author.objects.create(
            name="ר׳ שלמה יצחקי",
            name_romanized="Rashi",
        )
        matches = find_author_matches("other name", name_romanized="Rashi")
        assert len(matches) == 1
        assert matches[0] == (author, "romanized")


@pytest.mark.django_db
class TestFindAuthorMatchesVariant:
    def test_variant_name_match(self):
        author = Author.objects.create(
            name="Rashi",
            variant_names=["R. Shlomo Yitzhaki", "Shelomo Yishaki"],
        )
        matches = find_author_matches("R. Shlomo Yitzhaki")
        assert len(matches) == 1
        assert matches[0] == (author, "variant")

    def test_variant_match_normalized(self):
        """Variant matching ignores punctuation differences."""
        author = Author.objects.create(
            name="Some Author",
            variant_names=["Shlomo, Yitzhaki"],
        )
        matches = find_author_matches("Shlomo Yitzhaki")
        assert len(matches) == 1
        assert matches[0] == (author, "variant")


@pytest.mark.django_db
class TestFindAuthorNoMatches:
    def test_empty_input(self):
        assert find_author_matches("") == []

    def test_no_authors_in_db(self):
        assert find_author_matches("Rashi") == []


class TestDetectSeriesFromMarc:
    def test_with_series_info(self):
        parsed = {
            "title": "Book Title",
            "series_title": "Library of Jewish thought",
            "series_volume": "vol. 3",
        }
        result = detect_series_from_marc(parsed)
        assert result is not None
        assert result["series_title"] == "Library of Jewish thought"
        assert result["series_volume"] == "vol. 3"

    def test_without_series_info(self):
        parsed = {"title": "Book Title", "series_title": None, "series_volume": None}
        result = detect_series_from_marc(parsed)
        assert result is None

    def test_empty_series_title(self):
        parsed = {"title": "Book", "series_title": "", "series_volume": "vol. 1"}
        assert detect_series_from_marc(parsed) is None

    def test_missing_keys(self):
        parsed = {"title": "Book"}
        assert detect_series_from_marc(parsed) is None


@pytest.mark.django_db
class TestFindMatchingSeries:
    def test_exact_match(self):
        series = Series.objects.create(title="Library of Jewish thought")
        result = find_matching_series("Library of Jewish thought")
        assert result == series

    def test_normalized_match(self):
        series = Series.objects.create(title="Library of Jewish thought")
        result = find_matching_series("Library of Jewish Thought")
        assert result == series

    def test_no_match(self):
        Series.objects.create(title="Library of Jewish thought")
        assert find_matching_series("Unrelated Series") is None

    def test_empty_title(self):
        assert find_matching_series("") is None


@pytest.mark.django_db
class TestCreateSeriesVolumes:
    def test_range_spec(self):
        series = Series.objects.create(title="Test Series")
        created = create_series_volumes(series, "1-5")
        assert len(created) == 5
        assert SeriesVolume.objects.filter(series=series).count() == 5
        vol_nums = sorted(sv.volume_number for sv in created)
        assert vol_nums == ["1", "2", "3", "4", "5"]

    def test_all_n_spec(self):
        series = Series.objects.create(title="Test Series")
        created = create_series_volumes(series, "all 3")
        assert len(created) == 3

    def test_list_spec(self):
        series = Series.objects.create(title="Test Series")
        created = create_series_volumes(series, [1, 3, 7])
        assert len(created) == 3
        vol_nums = {sv.volume_number for sv in created}
        assert vol_nums == {"1", "3", "7"}

    def test_with_records_marks_held(self):
        series = Series.objects.create(title="Test Series")
        record = Record.objects.create(title="Vol 2 Book")
        created = create_series_volumes(series, "1-3", records={"2": record})
        assert len(created) == 3
        vol2 = SeriesVolume.objects.get(series=series, volume_number="2")
        vol1 = SeriesVolume.objects.get(series=series, volume_number="1")
        assert vol2.held is True
        assert vol2.record == record
        assert vol1.held is False
        assert vol1.record is None

    def test_no_duplicate_volumes(self):
        series = Series.objects.create(title="Test Series")
        create_series_volumes(series, "1-3")
        created2 = create_series_volumes(series, "1-5")
        # Only 4 and 5 should be new
        assert len(created2) == 2
        assert SeriesVolume.objects.filter(series=series).count() == 5
