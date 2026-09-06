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
from ingest.forms import RecordForm
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
        record = Record.objects.create(
            title="Dated Book", date_of_publication=1920
        )
        assert record.get_date_display() == "1920"

    def test_date_display_empty(self):
        record = Record.objects.create(title="Undated Book")
        assert record.get_date_display() == ""

    def test_source_marc_nullable(self):
        record = Record.objects.create(title="Manual Entry")
        assert record.source_marc is None

    def test_source_marc_json(self):
        marc_data = {"leader": "00000nam a2200000 a 4500", "fields": []}
        record = Record.objects.create(
            title="Cataloged Book", source_marc=marc_data
        )
        record.refresh_from_db()
        assert record.source_marc == marc_data

    def test_provenance_defaults_to_empty(self):
        record = Record.objects.create(title="Untraced Copy")
        record.refresh_from_db()
        assert record.provenance == ""

    def test_provenance_stores_free_text(self):
        text = (
            "Inscribed on the flyleaf: 'From the library of A. Cohen'.\n"
            "Bookplate of the Sassoon family; acquired 1932."
        )
        record = Record.objects.create(
            title="Sefer ha-Kuzari", provenance=text
        )
        record.refresh_from_db()
        assert record.provenance == text


@pytest.mark.django_db
class TestRecordTitleStatement:
    """The rest of the 245: what part this is, and who did what."""

    def test_fields_default_to_empty(self):
        record = Record.objects.create(title="Single Volume")
        record.refresh_from_db()
        assert record.volume_part_number == ""
        assert record.volume_part_title == ""
        assert record.statement_of_responsibility == ""

    def test_volume_part_stored(self):
        record = Record.objects.create(
            title="Rashi : the Torah, with Rashi's commentary",
            volume_part_number="Volume 2",
            volume_part_title="Sefer Mishpatim",
        )
        record.refresh_from_db()
        assert record.volume_part_number == "Volume 2"
        assert record.volume_part_title == "Sefer Mishpatim"

    def test_volume_part_title_holds_hebrew(self):
        record = Record.objects.create(
            title="Mishneh Torah", volume_part_title="ספר המדע"
        )
        record.refresh_from_db()
        assert record.volume_part_title == "ספר המדע"

    def test_statement_of_responsibility_stored(self):
        statement = (
            "translated, annotated, and elucidated by "
            "Yisrael Isser Zvi Herczeg ; in collaboration with "
            "Yaakov Petroff and Yoseph Kamenetsky ; "
            "contributing editor, Avie Gold."
        )
        record = Record.objects.create(
            title="Rashi", statement_of_responsibility=statement
        )
        record.refresh_from_db()
        assert record.statement_of_responsibility == statement

    def test_statement_of_responsibility_has_no_length_ceiling(self):
        # Transcribed responsibility runs as long as the item's title
        # page does -- a multi-editor proceedings, a film credit -- and
        # MARC allows a data field up to 9999 octets. There is no width
        # worth picking, so the field is text rather than a CharField.
        statement = "; ".join(
            f"edited by Editor Number {n}" for n in range(400)
        )
        assert len(statement) > 5000
        record = Record.objects.create(
            title="Proceedings", statement_of_responsibility=statement
        )
        record.refresh_from_db()
        assert record.statement_of_responsibility == statement


@pytest.mark.django_db
class TestRecordFormProvenance:
    def test_form_saves_provenance(self):
        form = RecordForm(
            data={
                "title": "Sefer ha-Kuzari",
                "provenance": "Bookplate of the Sassoon family.",
            }
        )
        assert form.is_valid(), form.errors
        record = form.save()
        record.refresh_from_db()
        assert record.provenance == "Bookplate of the Sassoon family."

    def test_provenance_is_optional(self):
        form = RecordForm(data={"title": "Untraced Copy"})
        assert form.is_valid(), form.errors
        assert form.save().provenance == ""


@pytest.mark.django_db
class TestRecordAdminProvenance:
    @pytest.fixture
    def superuser_client(self, client, django_user_model):
        django_user_model.objects.create_superuser(
            username="root", password="rootpass123", email="root@example.com"
        )
        client.login(username="root", password="rootpass123")
        return client

    def test_change_form_offers_provenance(self, superuser_client):
        record = Record.objects.create(title="Sefer ha-Kuzari")
        response = superuser_client.get(
            f"/admin/catalog/record/{record.pk}/change/"
        )
        assert 'name="provenance"' in response.content.decode()

    def test_admin_search_matches_provenance(self, superuser_client):
        Record.objects.create(
            title="Sefer ha-Kuzari",
            provenance="Bookplate of Solomon Schechter",
        )
        Record.objects.create(title="Some Other Book")
        response = superuser_client.get("/admin/catalog/record/?q=Schechter")
        body = response.content.decode()
        assert "Sefer ha-Kuzari" in body
        assert "Some Other Book" not in body


@pytest.mark.django_db
class TestRecordOwnershipMarks:
    """Marks the copy carries: a bookplate, a dedication, a stamp.

    Three different things -- a printed ownership label, a handwritten
    inscription, an institutional mark -- transcribed as they read.
    """

    def test_marks_default_to_empty(self):
        record = Record.objects.create(title="Unmarked Copy")
        record.refresh_from_db()
        assert record.bookplate_text == ""
        assert record.dedication_text == ""
        assert record.stamp_text == ""

    def test_bookplate_text_stores_a_transcription(self):
        record = Record.objects.create(
            title="Sefer ha-Kuzari",
            bookplate_text="Ex libris David Solomon Sassoon",
        )
        record.refresh_from_db()
        assert record.bookplate_text == "Ex libris David Solomon Sassoon"

    def test_stamp_text_holds_one_line_per_stamp(self):
        text = (
            "Bibliothèque de l'Alliance Israélite Universelle, Paris\n"
            "WITHDRAWN"
        )
        record = Record.objects.create(
            title="Sefer ha-Kuzari", stamp_text=text
        )
        record.refresh_from_db()
        assert record.stamp_text == text

    def test_dedication_text_holds_hebrew(self):
        record = Record.objects.create(
            title="Mishneh Torah", dedication_text="לזכר נשמת אמי מורתי"
        )
        record.refresh_from_db()
        assert record.dedication_text == "לזכר נשמת אמי מורתי"

    def test_a_mark_has_no_length_ceiling(self):
        # A dedication transcribes what someone wrote by hand, and
        # nothing about that has a width worth picking: a presentation
        # inscription can run to a paragraph, and a copy can carry more
        # than one bookplate or stamp, each on its own line. So these
        # are text fields rather than CharFields.
        dedication = "\n".join(
            f"For Rivka, on her {n}th birthday, with love from Papa"
            for n in range(100)
        )
        assert len(dedication) > 4000
        record = Record.objects.create(
            title="Siddur", dedication_text=dedication
        )
        record.refresh_from_db()
        assert record.dedication_text == dedication


@pytest.mark.django_db
class TestRecordFormOwnershipMarks:
    def test_form_saves_every_mark(self):
        form = RecordForm(
            data={
                "title": "Sefer ha-Kuzari",
                "bookplate_text": "Ex libris David Solomon Sassoon",
                "dedication_text": "To Rivka, from her father, 1932.",
                "stamp_text": "Alliance Israélite Universelle, Paris",
            }
        )
        assert form.is_valid(), form.errors
        record = form.save()
        record.refresh_from_db()
        assert record.bookplate_text == "Ex libris David Solomon Sassoon"
        assert record.dedication_text == "To Rivka, from her father, 1932."
        assert record.stamp_text == "Alliance Israélite Universelle, Paris"

    def test_marks_are_optional(self):
        form = RecordForm(data={"title": "Unmarked Copy"})
        assert form.is_valid(), form.errors
        record = form.save()
        assert record.bookplate_text == ""
        assert record.dedication_text == ""
        assert record.stamp_text == ""


@pytest.mark.django_db
class TestRecordAdminOwnershipMarks:
    @pytest.fixture
    def superuser_client(self, client, django_user_model):
        django_user_model.objects.create_superuser(
            username="root", password="rootpass123", email="root@example.com"
        )
        client.login(username="root", password="rootpass123")
        return client

    @pytest.mark.parametrize(
        "field", ["bookplate_text", "dedication_text", "stamp_text"]
    )
    def test_change_form_offers_the_mark(self, superuser_client, field):
        record = Record.objects.create(title="Sefer ha-Kuzari")
        response = superuser_client.get(
            f"/admin/catalog/record/{record.pk}/change/"
        )
        assert f'name="{field}"' in response.content.decode()

    @pytest.mark.parametrize(
        "field,term",
        [
            ("bookplate_text", "Sassoon"),
            ("dedication_text", "Rivka"),
            ("stamp_text", "Alliance"),
        ],
    )
    def test_admin_search_matches_the_mark(
        self, superuser_client, field, term
    ):
        Record.objects.create(
            title="Sefer ha-Kuzari", **{field: f"Ex libris {term}"}
        )
        Record.objects.create(title="Some Other Book")
        response = superuser_client.get(f"/admin/catalog/record/?q={term}")
        body = response.content.decode()
        assert "Sefer ha-Kuzari" in body
        assert "Some Other Book" not in body


@pytest.mark.django_db
class TestAuthorModel:
    def test_create_author(self):
        author = Author.objects.create(
            name="רמבם", name_romanized="Maimonides"
        )
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
        SeriesVolume.objects.create(
            series=series, volume_number="1", held=True
        )
        SeriesVolume.objects.create(
            series=series, volume_number="2", held=False
        )
        SeriesVolume.objects.create(
            series=series, volume_number="3", held=True
        )
        held = series.volumes.filter(held=True).count()
        not_held = series.volumes.filter(held=False).count()
        assert held == 2
        assert not_held == 1

    def test_volume_number_string(self):
        series = Series.objects.create(title="Test Series")
        vol = SeriesVolume.objects.create(
            series=series, volume_number="supplement"
        )
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
        scan = ScanResult.objects.create(
            scan_type="ocr", status="awaiting_ocr"
        )
        scan.refresh_from_db()
        assert scan.status == "awaiting_ocr"

    def test_default_status_unchanged(self):
        scan = ScanResult.objects.create(
            scan_type="isbn", isbn="978-0-13-110362-7"
        )
        assert scan.status == "pending"

    def test_existing_pending_query_excludes_awaiting_ocr(self):
        ScanResult.objects.create(scan_type="ocr", status="awaiting_ocr")
        ScanResult.objects.create(
            scan_type="isbn", isbn="123", status="pending"
        )
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
