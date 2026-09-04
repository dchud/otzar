import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone

from catalog.models import Record, Series, SeriesClaim, SeriesClaimRow
from ingest.models import ScanResult


@pytest.fixture
def user():
    return User.objects.create_user(
        username="cataloger", password="testpass123"
    )


@pytest.fixture
def claim(user):
    return SeriesClaim.objects.create(
        created_by=user, volume_spec="1-3", originating_volume_number="2"
    )


@pytest.mark.django_db
class TestSeriesClaimLifecycle:
    def test_status_defaults_to_pending(self, claim):
        assert claim.status == "pending"

    def test_status_choices_cover_the_lifecycle(self):
        values = [
            value
            for value, _label in SeriesClaim._meta.get_field("status").choices
        ]
        assert values == ["pending", "committed", "cancelled"]

    def test_created_at_is_set_and_resolved_at_is_not(self, claim):
        assert claim.created_at is not None
        assert claim.resolved_at is None

    def test_resolving_records_a_timestamp(self, claim):
        claim.status = "committed"
        claim.resolved_at = timezone.now()
        claim.save()
        claim.refresh_from_db()
        assert claim.status == "committed"
        assert claim.resolved_at is not None

    def test_string_names_the_spec_and_status(self, claim):
        assert "1-3" in str(claim)
        assert "pending" in str(claim)

    def test_string_without_a_series(self, claim):
        assert claim.series is None
        assert str(claim)


@pytest.mark.django_db
class TestSeriesClaimDeletes:
    """Deleting anything a claim points at must leave the claim standing.

    A claim is a record of work someone did. Losing it because a
    series, a user account or a scan was cleaned up would silently
    discard that work, so every foreign key out of ``SeriesClaim``
    nulls instead of cascading.
    """

    def test_deleting_the_series_keeps_the_claim(self, user):
        series = Series.objects.create(title="Talmud Bavli")
        claim = SeriesClaim.objects.create(
            series=series, created_by=user, volume_spec="1-5"
        )
        series.delete()
        claim.refresh_from_db()
        assert claim.series is None
        assert claim.volume_spec == "1-5"

    def test_deleting_the_creator_keeps_the_claim(self, user):
        claim = SeriesClaim.objects.create(created_by=user, volume_spec="1-5")
        user.delete()
        claim.refresh_from_db()
        assert claim.created_by is None

    def test_deleting_the_originating_scan_keeps_the_claim(self, user):
        scan = ScanResult.objects.create(scan_type="isbn", scanned_by=user)
        claim = SeriesClaim.objects.create(
            created_by=user,
            volume_spec="1-5",
            originating_scan=scan,
            originating_volume_number="3",
        )
        scan.delete()
        claim.refresh_from_db()
        assert claim.originating_scan is None
        assert claim.originating_volume_number == "3"

    def test_deleting_the_series_keeps_the_rows(self, user):
        series = Series.objects.create(title="Mishneh Torah")
        claim = SeriesClaim.objects.create(
            series=series, created_by=user, volume_spec="1-2"
        )
        SeriesClaimRow.objects.create(claim=claim, volume_number="1")
        SeriesClaimRow.objects.create(claim=claim, volume_number="2")
        series.delete()
        assert claim.rows.count() == 2


@pytest.mark.django_db
class TestSeriesClaimRows:
    def test_rows_are_reachable_from_the_claim(self, claim):
        SeriesClaimRow.objects.create(claim=claim, volume_number="1")
        SeriesClaimRow.objects.create(claim=claim, volume_number="2")
        assert claim.rows.count() == 2

    def test_search_status_defaults_to_pending(self, claim):
        row = SeriesClaimRow.objects.create(claim=claim, volume_number="1")
        assert row.search_status == "pending"

    def test_search_status_choices(self, claim):
        values = [
            value
            for value, _label in SeriesClaimRow._meta.get_field(
                "search_status"
            ).choices
        ]
        assert values == [
            "pending",
            "searching",
            "found",
            "no_match",
            "multiple",
            "manual_skip",
            "manual_held",
        ]

    def test_candidate_records_defaults_to_an_empty_list(self, claim):
        row = SeriesClaimRow.objects.create(claim=claim, volume_number="1")
        row.refresh_from_db()
        assert row.candidate_records == []
        assert row.selected_candidate_index is None

    def test_candidate_records_round_trip(self, claim):
        candidates = [{"title": "Volume One"}, {"title": "Vol. 1"}]
        row = SeriesClaimRow.objects.create(
            claim=claim,
            volume_number="1",
            candidate_records=candidates,
            selected_candidate_index=0,
            search_status="multiple",
        )
        row.refresh_from_db()
        assert row.candidate_records == candidates
        assert row.selected_candidate_index == 0

    def test_deleting_the_claim_deletes_its_rows(self, claim):
        SeriesClaimRow.objects.create(claim=claim, volume_number="1")
        SeriesClaimRow.objects.create(claim=claim, volume_number="2")
        claim.delete()
        assert SeriesClaimRow.objects.count() == 0

    def test_deleting_the_created_record_keeps_the_row(self, claim):
        record = Record.objects.create(title="Volume One")
        row = SeriesClaimRow.objects.create(
            claim=claim,
            volume_number="1",
            created_record=record,
            search_status="found",
        )
        record.delete()
        row.refresh_from_db()
        assert row.created_record is None
        assert row.search_status == "found"

    def test_volume_number_is_unique_within_a_claim(self, claim):
        SeriesClaimRow.objects.create(claim=claim, volume_number="1")
        with pytest.raises(IntegrityError):
            SeriesClaimRow.objects.create(claim=claim, volume_number="1")

    def test_the_same_volume_number_may_appear_in_another_claim(self, user):
        first = SeriesClaim.objects.create(created_by=user, volume_spec="1-2")
        second = SeriesClaim.objects.create(created_by=user, volume_spec="1-2")
        SeriesClaimRow.objects.create(claim=first, volume_number="1")
        SeriesClaimRow.objects.create(claim=second, volume_number="1")
        assert SeriesClaimRow.objects.filter(volume_number="1").count() == 2

    def test_rows_sort_by_volume_number_as_text(self, claim):
        for number in ["10", "2", "1", "supplement"]:
            SeriesClaimRow.objects.create(claim=claim, volume_number=number)
        assert [row.volume_number for row in claim.rows.all()] == [
            "1",
            "10",
            "2",
            "supplement",
        ]

    def test_updated_at_advances_on_save(self, claim):
        row = SeriesClaimRow.objects.create(claim=claim, volume_number="1")
        first = row.updated_at
        row.search_status = "found"
        row.save()
        row.refresh_from_db()
        assert row.updated_at > first


@pytest.mark.django_db
class TestFieldOptionality:
    """Guard the null/blank pairs that are easy to invert.

    ``null`` governs the database column; ``blank`` governs form
    validation. A claim must name the volumes it covers and who made
    it, while the series it belongs to and the volume it started from
    are both optional.
    """

    @pytest.mark.parametrize(
        "name,null,blank",
        [
            ("series", True, True),
            ("created_by", True, False),
            ("resolved_at", True, True),
            ("volume_spec", False, False),
            ("originating_scan", True, False),
            ("originating_volume_number", False, True),
            ("status", False, False),
        ],
    )
    def test_claim_field_optionality(self, name, null, blank):
        field = SeriesClaim._meta.get_field(name)
        assert field.null is null
        assert field.blank is blank

    @pytest.mark.parametrize(
        "name,null,blank",
        [
            ("claim", False, False),
            ("volume_number", False, False),
            ("search_status", False, False),
            ("candidate_records", False, True),
            ("selected_candidate_index", True, True),
            ("created_record", True, True),
        ],
    )
    def test_row_field_optionality(self, name, null, blank):
        field = SeriesClaimRow._meta.get_field(name)
        assert field.null is null
        assert field.blank is blank

    def test_a_claim_needs_no_series_or_scan(self, user):
        claim = SeriesClaim.objects.create(created_by=user, volume_spec="1-3")
        assert claim.series is None
        assert claim.originating_scan is None
        assert claim.originating_volume_number == ""

    def test_field_lengths_match_the_columns_they_index(self):
        assert SeriesClaim._meta.get_field("volume_spec").max_length == 200
        assert (
            SeriesClaim._meta.get_field("originating_volume_number").max_length
            == 50
        )
        assert SeriesClaim._meta.get_field("status").max_length == 20
        assert SeriesClaimRow._meta.get_field("volume_number").max_length == 50
        assert SeriesClaimRow._meta.get_field("search_status").max_length == 20
