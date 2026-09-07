"""Telling a publisher's series apart from a work issued in parts.

A 490 or 830 carries both, and no subfield says which. The catalog has
to decide, because only one of them has volumes somebody completes:
giving ArtScroll volume positions files unrelated books into a sequence
that does not exist and leaves gaps nobody can fill.
"""

import mrrc
import pytest
from django.contrib.auth.models import User
from django.test import Client

from catalog.models import Record, Series, SeriesVolume
from ingest.series_workflow import classify_series_statement
from sources.marc import extract_marc_records, parse_record
from tests.marc_fixtures import load


def _record(fields: list[tuple[str, str, str, str]]) -> dict:
    """Parse a record carrying *fields*, given as (tag, ind1, ind2, subs).

    ``subs`` is written the way a MARC field is read aloud:
    ``"$aTalmud Bavli$pPesahim"``.
    """
    parts = []
    for tag, ind1, ind2, subs in fields:
        body = "\n".join(
            f'    <subfield code="{sub[0]}">{sub[1:]}</subfield>'
            for sub in subs.split("$")
            if sub
        )
        parts.append(
            f'  <datafield tag="{tag}" ind1="{ind1}" ind2="{ind2}">\n'
            f"{body}\n  </datafield>"
        )
    xml = (
        '<record xmlns="http://www.loc.gov/MARC21/slim">\n'
        "  <leader>00000nam a2200000 i 4500</leader>\n"
        '  <datafield tag="245" ind1="1" ind2="0">\n'
        '    <subfield code="a">A volume</subfield>\n'
        "  </datafield>\n" + "\n".join(parts) + "\n</record>"
    )
    return parse_record(mrrc.xml_to_record(xml))


def _fixture(name: str) -> dict:
    _, records = extract_marc_records(load(name))
    return parse_record(records[0])


class TestASeriesThatNamesAWork:
    """The record says the series is a work by naming it as one."""

    def test_a_uniform_title_repeating_the_series_title(self):
        """One work stated twice: once as a heading, once as a series."""
        parsed = _record(
            [
                ("130", "0", " ", "$aTalmud Bavli.$pPesahim."),
                ("490", "1", " ", "$aTalmud Bavli$vv. 3"),
                ("830", " ", "0", "$aTalmud Bavli.$vv. 3"),
            ]
        )

        assert classify_series_statement(parsed) == Series.KIND_WORK

    def test_the_two_forms_are_compared_without_punctuation(self):
        """The heading and the series statement punctuate differently."""
        parsed = _record(
            [
                ("240", "1", "0", "$aTalmud Bavli"),
                ("490", "1", " ", "$aTalmud Bavli ;$vv. 3"),
            ]
        )

        assert classify_series_statement(parsed) == Series.KIND_WORK

    def test_an_added_uniform_title_counts_too(self):
        """730 is a uniform-title position, so a work can be named there."""
        parsed = _record(
            [
                ("730", "0", " ", "$aMishneh Torah.$pSefer ha-madaʻ."),
                ("490", "1", " ", "$aMishneh Torah$vv. 1"),
            ]
        )

        assert classify_series_statement(parsed) == Series.KIND_WORK

    def test_a_series_issn_outranks_a_matching_title(self):
        """ISSN is assigned to continuing resources, not to works in parts.

        A record carrying both is one where the cataloger filed the
        series as an ongoing publication, and that is a statement, where
        a repeated title is a resemblance.
        """
        parsed = _record(
            [
                ("130", "0", " ", "$aStudia Judaica."),
                ("490", "1", " ", "$aStudia Judaica$x0585-5306"),
            ]
        )

        assert classify_series_statement(parsed) == Series.KIND_IMPRINT


class TestASeriesThatNamesNoWork:
    """Without that, the statement is read as a publication fact."""

    def test_a_label_matching_nothing_the_record_names(self):
        parsed = _record(
            [
                ("130", "0", " ", "$aBible.$pPentateuch.$lEnglish."),
                ("490", "1", " ", "$aArtScroll series"),
            ]
        )

        assert classify_series_statement(parsed) == Series.KIND_IMPRINT

    def test_a_record_naming_no_work_at_all(self):
        parsed = _record([("490", "1", " ", "$aArtScroll series")])

        assert classify_series_statement(parsed) == Series.KIND_IMPRINT

    def test_a_volume_number_does_not_make_a_set(self):
        """A monographic series counts its books; that is not a work.

        Nobody sets out to hold every number of the Schriften des
        Institutum Judaicum, and a gap in it is not a gap in anything.
        """
        parsed = _record(
            [
                ("130", "0", " ", "$aMishnah.$pSanhedrin.$lGerman."),
                (
                    "490",
                    "1",
                    " ",
                    "$aSchriften des Institutum Judaicum in Berlin ;$vNr. 38",
                ),
            ]
        )

        assert classify_series_statement(parsed) == Series.KIND_IMPRINT


class TestAgainstRealCopy:
    """The same reading, run over records as the catalogs sent them."""

    def test_an_artscroll_series_statement_is_a_publishers_line(self):
        parsed = _fixture("artscroll_chumash_contents_enhanced_lc")

        assert parsed["series_title"] == "ArtScroll series."
        assert classify_series_statement(parsed) == Series.KIND_IMPRINT

    def test_the_obsolete_440_form_reads_the_same_way(self):
        parsed = _fixture("sapirstein_rashi_obsolete_series_lc")

        assert parsed["series_title"] == "The ArtScroll series"
        assert classify_series_statement(parsed) == Series.KIND_IMPRINT

    def test_a_numbered_monographic_series_is_still_a_publishers_line(self):
        parsed = _fixture("mishnah_leipzig_series_1910_nli")

        assert parsed["series_volume"] == "Nr. 38"
        assert classify_series_statement(parsed) == Series.KIND_IMPRINT

    def test_a_work_set_record_whose_series_names_the_publishers_line(self):
        """The set here is in the 130, and the 830 is Judaica Press's line.

        The record is one of the Five Megilloth in Judaica Press's
        Hagiographa translations. Its 130 says the work is ``Bible. Five
        scrolls``; its 830 says ``Judaica books of the Hagiographa``,
        which names no work the record names and belongs to the
        publisher. Reading the series statement as a work-set would give
        the publisher's line volume positions; the set this record
        belongs to is stated elsewhere in it.
        """
        parsed = _fixture("miqraot_gedolot_parallel_script_nli")

        assert parsed["uniform_title"]["work"] == "Bible"
        assert classify_series_statement(parsed) == Series.KIND_IMPRINT


@pytest.mark.django_db
class TestMembershipAndPosition:
    """Both kinds keep members; only a work-set hands out positions."""

    @pytest.fixture
    def record(self):
        return Record.objects.create(title="Bereshit")

    @pytest.fixture
    def other(self):
        return Record.objects.create(title="Shemot")

    def test_a_publishers_series_keeps_the_record_without_placing_it(
        self, record
    ):
        from ingest.series_workflow import link_record_to_series

        volume = link_record_to_series(
            record, "ArtScroll series ;", "", Series.KIND_IMPRINT
        )

        assert volume is None
        series = Series.objects.get()
        assert series.kind == Series.KIND_IMPRINT
        assert list(record.series.all()) == [series]
        assert SeriesVolume.objects.count() == 0

    def test_two_books_under_one_imprint_are_not_volumes_of_each_other(
        self, record, other
    ):
        """Both belong to the label; neither is numbered against it."""
        from ingest.series_workflow import link_record_to_series

        link_record_to_series(
            record, "ArtScroll series ;", "v. 1", Series.KIND_IMPRINT
        )
        link_record_to_series(
            other, "Artscroll Series.", "v. 2", Series.KIND_IMPRINT
        )

        series = Series.objects.get()
        assert set(series.records.all()) == {record, other}
        assert SeriesVolume.objects.count() == 0

    def test_a_work_set_places_the_record_and_keeps_it(self, record):
        from ingest.series_workflow import link_record_to_series

        volume = link_record_to_series(
            record, "Talmud Bavli.", "v. 3", Series.KIND_WORK
        )

        series = Series.objects.get()
        assert series.kind == Series.KIND_WORK
        assert volume.volume_number == "3"
        assert list(record.series.all()) == [series]


@pytest.mark.django_db
class TestKeepingAClassification:
    """Evidence raises, a person decides, and a decision holds."""

    @pytest.fixture
    def record(self):
        return Record.objects.create(title="Pesahim")

    @pytest.fixture
    def other(self):
        return Record.objects.create(title="Sukkah")

    def test_a_record_naming_the_work_raises_a_publishers_series(
        self, record, other
    ):
        """The first record said nothing; the second one says it is a work."""
        from ingest.series_workflow import link_record_to_series

        link_record_to_series(record, "Talmud Bavli", "", Series.KIND_IMPRINT)
        volume = link_record_to_series(
            other, "Talmud Bavli", "v. 4", Series.KIND_WORK
        )

        series = Series.objects.get()
        assert series.kind == Series.KIND_WORK
        assert volume.volume_number == "4"

    def test_a_silent_record_does_not_lower_a_work_set(self, record, other):
        """Most records carry no uniform title, so silence says nothing."""
        from ingest.series_workflow import link_record_to_series

        link_record_to_series(record, "Talmud Bavli", "v. 3", Series.KIND_WORK)
        link_record_to_series(
            other, "Talmud Bavli", "v. 4", Series.KIND_IMPRINT
        )

        series = Series.objects.get()
        assert series.kind == Series.KIND_WORK
        assert series.volumes.count() == 2

    def test_a_persons_decision_outranks_a_disagreeing_record(
        self, record, other
    ):
        """An asserted kind is otzar's, and copy cataloging does not vote."""
        from ingest.series_workflow import link_record_to_series

        link_record_to_series(record, "Talmud Bavli", "", Series.KIND_IMPRINT)
        series = Series.objects.get()
        series.kind_source = Series.SOURCE_ASSERTED
        series.save(update_fields=["kind_source"])

        volume = link_record_to_series(
            other, "Talmud Bavli", "v. 4", Series.KIND_WORK
        )

        series.refresh_from_db()
        assert series.kind == Series.KIND_IMPRINT
        assert volume is None
        assert SeriesVolume.objects.count() == 0


@pytest.fixture
def cataloger(db):
    return User.objects.create_user(
        username="cataloger", password="testpass123"
    )


@pytest.fixture
def client_logged_in(cataloger):
    client = Client()
    client.login(username="cataloger", password="testpass123")
    return client


@pytest.mark.django_db
class TestCorrectingAClassificationOnTheSeriesPage:
    """The page a person fixes a misfiled series on.

    The signals are weak and some series will come out wrong. What makes
    that survivable is that the fix is one form away and is recorded as
    a decision rather than as another reading of the evidence.
    """

    @pytest.fixture
    def imprint(self):
        return Series.objects.create(
            title="Talmud Bavli", kind=Series.KIND_IMPRINT
        )

    def test_the_page_offers_both_kinds(self, client_logged_in, imprint):
        content = client_logged_in.get(
            f"/ingest/series/{imprint.pk}/"
        ).content.decode()

        assert "Multi-volume work" in content
        assert "Publisher&#x27;s series" in content

    def test_a_publishers_series_is_offered_no_volumes_to_add(
        self, client_logged_in, imprint
    ):
        content = client_logged_in.get(
            f"/ingest/series/{imprint.pk}/"
        ).content.decode()

        assert "Add volumes" not in content
        assert "Records in this series" in content

    def test_setting_the_kind_records_it_as_a_decision(
        self, client_logged_in, imprint
    ):
        client_logged_in.post(
            f"/ingest/series/{imprint.pk}/", {"kind": Series.KIND_WORK}
        )

        imprint.refresh_from_db()
        assert imprint.kind == Series.KIND_WORK
        assert imprint.kind_source == Series.SOURCE_ASSERTED

    def test_a_corrected_work_set_can_then_take_volumes(
        self, client_logged_in, imprint
    ):
        client_logged_in.post(
            f"/ingest/series/{imprint.pk}/", {"kind": Series.KIND_WORK}
        )
        client_logged_in.post(
            f"/ingest/series/{imprint.pk}/", {"volume_spec": "1-3"}
        )

        assert imprint.volumes.count() == 3

    def test_a_publishers_series_takes_no_volume_spec(
        self, client_logged_in, imprint
    ):
        """The form is not offered, and the endpoint declines it anyway."""
        client_logged_in.post(
            f"/ingest/series/{imprint.pk}/", {"volume_spec": "1-3"}
        )

        assert imprint.volumes.count() == 0

    def test_an_unknown_kind_is_ignored(self, client_logged_in, imprint):
        client_logged_in.post(
            f"/ingest/series/{imprint.pk}/", {"kind": "something else"}
        )

        imprint.refresh_from_db()
        assert imprint.kind == Series.KIND_IMPRINT
        assert imprint.kind_source == Series.SOURCE_IMPORTED


@pytest.mark.django_db
class TestARefiledSeriesOnTheRecordPage:
    """What a record shows after its series is corrected.

    Correcting a work-set to a publisher's line leaves the positions it
    held in the database, so the correction can be undone. The record
    page stops presenting them, because a sequence nobody completes has
    no siblings worth showing.
    """

    @pytest.fixture
    def placed_record(self, client_logged_in):
        from ingest.series_workflow import link_record_to_series

        record = Record.objects.create(title="Pesahim")
        link_record_to_series(record, "Talmud Bavli", "v. 3", Series.KIND_WORK)
        return record

    def test_a_work_set_shows_the_position(
        self, client_logged_in, placed_record
    ):
        url = f"/catalog/{placed_record.record_id}/{placed_record.slug}/"
        content = client_logged_in.get(url).content.decode()

        assert "vol. 3" in content
        assert "Published in" not in content

    def test_refiling_it_moves_the_series_to_the_publication_facts(
        self, client_logged_in, placed_record
    ):
        series = Series.objects.get()
        client_logged_in.post(
            f"/ingest/series/{series.pk}/", {"kind": Series.KIND_IMPRINT}
        )

        url = f"/catalog/{placed_record.record_id}/{placed_record.slug}/"
        content = client_logged_in.get(url).content.decode()

        assert "Published in" in content
        assert "vol. 3" not in content
        assert SeriesVolume.objects.count() == 1
