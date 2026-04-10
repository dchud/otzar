import pytest
from django.core.management import call_command

from catalog.models import (
    Record,
    Series,
    SeriesVolume,
)
from catalog.search import ensure_fts_table, search


@pytest.mark.django_db
class TestLoadTestData:
    def test_creates_expected_record_count(self):
        call_command("load_test_data")
        assert Record.objects.count() == 26

    def test_series_with_gaps_exist(self):
        call_command("load_test_data")
        # Mishneh Torah: vols 1-3 held, vols 4-14 not held
        mt = Series.objects.get(title="משנה תורה")
        held = SeriesVolume.objects.filter(series=mt, held=True).count()
        not_held = SeriesVolume.objects.filter(series=mt, held=False).count()
        assert held >= 3
        assert not_held >= 2
        assert mt.total_volumes == 14

    def test_steinsaltz_series_has_gaps(self):
        call_command("load_test_data")
        st = Series.objects.get(title="תלמוד בבלי - מהדורת שטיינזלץ")
        held = SeriesVolume.objects.filter(series=st, held=True).count()
        not_held = SeriesVolume.objects.filter(series=st, held=False).count()
        assert held >= 4
        assert not_held >= 2

    def test_multiple_languages_present(self):
        call_command("load_test_data")
        languages = set(Record.objects.values_list("language", flat=True).distinct())
        assert "heb" in languages
        assert "eng" in languages
        assert "ger" in languages
        assert "yid" in languages

    def test_records_searchable_via_fts(self):
        call_command("load_test_data")
        ensure_fts_table()

        # Search by English title
        results = search("Halakhic")
        assert len(results) >= 1

        # Search by Hebrew title
        results = search("משנה")
        assert len(results) >= 1

        # Search by author
        results = search("Heschel")
        assert len(results) >= 1

        # Search by romanized title
        results = search("Steinsaltz")
        assert len(results) >= 1

    def test_idempotent_no_duplicates(self):
        call_command("load_test_data")
        count_first = Record.objects.count()
        call_command("load_test_data")
        count_second = Record.objects.count()
        assert count_first == count_second

    def test_source_catalog_variety(self):
        call_command("load_test_data")
        catalogs = set(
            Record.objects.exclude(source_catalog="")
            .values_list("source_catalog", flat=True)
            .distinct()
        )
        assert "NLI" in catalogs
        assert "LC" in catalogs
        assert "DNB" in catalogs
        # Some records have no source_catalog (manual entry)
        manual = Record.objects.filter(source_catalog="").count()
        assert manual >= 1

    def test_clear_flag_removes_data(self):
        call_command("load_test_data")
        assert Record.objects.count() > 0
        call_command("load_test_data", clear=True)
        # After clear + reload, count should be the same as fresh load
        assert Record.objects.count() == 26
