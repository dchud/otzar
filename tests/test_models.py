import pytest

from catalog.id_generation import encode_base62, generate_record_id
from catalog.models import (
    Author,
    ExternalIdentifier,
    Location,
    Record,
    Series,
    SeriesVolume,
)
from ingest.models import ScanResult


@pytest.mark.django_db
class TestRecordModel:
    def test_create_record(self):
        record = Record.objects.create(title="Test Book")
        assert record.pk is not None
        assert record.record_id.startswith("otzar-")
        assert record.slug == "test-book"

    def test_record_id_is_unique(self):
        r1 = Record.objects.create(title="Book One")
        r2 = Record.objects.create(title="Book Two")
        assert r1.record_id != r2.record_id

    def test_unicode_slug(self):
        record = Record.objects.create(title="משנה תורה")
        assert record.slug == "משנה-תורה"

    def test_romanized_slug_preferred(self):
        record = Record.objects.create(
            title="משנה תורה", title_romanized="Mishneh Torah"
        )
        assert record.slug == "mishneh-torah"

    def test_date_display_freeform(self):
        record = Record.objects.create(
            title="Old Book",
            date_of_publication=1850,
            date_of_publication_display="ca. 1850",
        )
        assert record.get_date_display() == "ca. 1850"

    def test_date_display_fallback_to_year(self):
        record = Record.objects.create(title="Dated Book", date_of_publication=1920)
        assert record.get_date_display() == "1920"

    def test_date_display_empty(self):
        record = Record.objects.create(title="Undated Book")
        assert record.get_date_display() == ""

    def test_source_marc_nullable(self):
        record = Record.objects.create(title="Manual Entry")
        assert record.source_marc is None

    def test_source_marc_json(self):
        marc_data = {"leader": "00000nam a2200000 a 4500", "fields": []}
        record = Record.objects.create(title="Cataloged Book", source_marc=marc_data)
        record.refresh_from_db()
        assert record.source_marc == marc_data


@pytest.mark.django_db
class TestAuthorModel:
    def test_create_author(self):
        author = Author.objects.create(name="רמבם", name_romanized="Maimonides")
        assert str(author) == "רמבם / Maimonides"

    def test_author_variant_names(self):
        author = Author.objects.create(
            name="רמבם",
            variant_names=["Maimonides", "Moses ben Maimon", "משה בן מימון"],
        )
        assert len(author.variant_names) == 3

    def test_author_record_relationship(self):
        author = Author.objects.create(name="Test Author")
        record = Record.objects.create(title="Test Book")
        record.authors.add(author)
        assert author in record.authors.all()
        assert record in author.records.all()


@pytest.mark.django_db
class TestSeriesModel:
    def test_create_series_with_volumes(self):
        series = Series.objects.create(title="Talmud Bavli", total_volumes=63)
        record = Record.objects.create(title="Bava Metzia")
        vol = SeriesVolume.objects.create(
            series=series, record=record, volume_number="33"
        )
        assert vol.held is True
        assert series.volumes.count() == 1

    def test_series_gap_representation(self):
        series = Series.objects.create(title="Mishneh Torah", total_volumes=14)
        SeriesVolume.objects.create(series=series, volume_number="1", held=True)
        SeriesVolume.objects.create(series=series, volume_number="2", held=False)
        SeriesVolume.objects.create(series=series, volume_number="3", held=True)
        held = series.volumes.filter(held=True).count()
        not_held = series.volumes.filter(held=False).count()
        assert held == 2
        assert not_held == 1

    def test_volume_number_string(self):
        series = Series.objects.create(title="Test Series")
        vol = SeriesVolume.objects.create(series=series, volume_number="supplement")
        assert vol.volume_number == "supplement"


@pytest.mark.django_db
class TestExternalIdentifier:
    def test_create_identifier(self):
        record = Record.objects.create(title="Test")
        eid = ExternalIdentifier.objects.create(
            record=record, identifier_type="ISBN", value="978-0-123456-78-9"
        )
        assert str(eid) == "ISBN: 978-0-123456-78-9"

    def test_unique_constraint(self):
        record = Record.objects.create(title="Test")
        ExternalIdentifier.objects.create(
            record=record, identifier_type="ISBN", value="123"
        )
        with pytest.raises(Exception):
            ExternalIdentifier.objects.create(
                record=record, identifier_type="ISBN", value="123"
            )


@pytest.mark.django_db
class TestLocationModel:
    def test_create_location(self):
        loc = Location.objects.create(label="Floor 1, Room B, Shelf 4a")
        assert str(loc) == "Floor 1, Room B, Shelf 4a"

    def test_location_record_relationship(self):
        loc = Location.objects.create(label="Main Hall")
        record = Record.objects.create(title="Test")
        record.locations.add(loc)
        assert loc in record.locations.all()


@pytest.mark.django_db
class TestScanResultStatus:
    def test_awaiting_ocr_status_is_valid(self):
        scan = ScanResult.objects.create(scan_type="ocr", status="awaiting_ocr")
        scan.refresh_from_db()
        assert scan.status == "awaiting_ocr"

    def test_default_status_unchanged(self):
        scan = ScanResult.objects.create(scan_type="isbn", isbn="978-0-13-110362-7")
        assert scan.status == "pending"

    def test_existing_pending_query_excludes_awaiting_ocr(self):
        ScanResult.objects.create(scan_type="ocr", status="awaiting_ocr")
        ScanResult.objects.create(scan_type="isbn", isbn="123", status="pending")
        pending = ScanResult.objects.filter(status="pending")
        assert pending.count() == 1
        assert pending.first().scan_type == "isbn"


class TestBase62:
    def test_encode_zero(self):
        assert encode_base62(0) == "0"

    def test_encode_small(self):
        assert encode_base62(1) == "1"
        assert encode_base62(61) == "Z"

    def test_encode_62(self):
        assert encode_base62(62) == "10"

    def test_generate_record_id(self):
        rid = generate_record_id(1000)
        assert rid.startswith("otzar-")
        assert len(rid) > 6
