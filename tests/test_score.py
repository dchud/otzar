"""Tests for scoring catalog candidates against a title-page reading.

The pure scorer lives in ``sources.score`` and its normalizers in
``sources.normalize``; the view-level tests at the end prove that the
candidate table is ordered by that score across catalogs.

The catalog records come from the real SRU fixtures in
``tests.test_marc`` -- LC with 880 linkage, NLI with Hebrew fields and a
gematria date, DNB, and a multi-volume set -- reached through the module
object so pytest does not collect that module's tests a second time.
"""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from ingest.models import ScanResult
from sources.cascade import CascadeResult
from sources.marc import extract_marc_records, parse_record
from sources.normalize import (
    extract_years,
    hebrew_year_to_gregorian,
    match_tokens,
)
from sources.score import (
    AGREED,
    DISAGREED,
    PARTIAL,
    WEIGHTS,
    rank_candidates,
    score_candidate,
)
from tests import test_marc as marc_fixtures


def _parsed(sru_xml: str) -> dict:
    _, records = extract_marc_records(sru_xml)
    return parse_record(records[0])


@pytest.fixture()
def lc_record():
    """LC pattern: romanised 245/100 with Hebrew in linked 880 fields."""
    return _parsed(marc_fixtures.LC_SRU_XML)


@pytest.fixture()
def nli_record():
    """NLI pattern: Hebrew in the primary fields, gematria in 260$c."""
    return _parsed(marc_fixtures.NLI_SRU_XML)


@pytest.fixture()
def dnb_record():
    """A record with no Hebrew anywhere."""
    return _parsed(marc_fixtures.DNB_SRU_XML)


@pytest.fixture()
def set_record():
    """A multi-volume set: part in 245 $n/$p, contributors in 700s."""
    return _parsed(marc_fixtures.MULTIVOLUME_SRU_XML)


def _verdicts(match) -> dict:
    return {v.field: v for v in match.verdicts}


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


class TestMatchTokens:
    def test_marc_display_punctuation_is_not_a_token(self):
        assert match_tokens("Halakhic man / a philosophical essay.") == {
            "halakhic",
            "man",
            "philosophical",
            "essay",
        }

    def test_case_folded(self):
        assert match_tokens("Sefer Press") == match_tokens("SEFER PRESS")

    def test_typographic_and_ascii_gershayim_agree(self):
        assert match_tokens("רש״י") == match_tokens('רש"י') == {"רשי"}

    def test_typographic_and_ascii_geresh_agree(self):
        assert (
            match_tokens("סולובייצ׳יק")
            == match_tokens("סולובייצ'יק")
            == match_tokens("סולובייצ’יק")
        )

    def test_niqqud_stripped(self):
        assert match_tokens("שָׁלוֹם") == {"שלום"}

    def test_latin_diacritics_and_ayin_marks_stripped(self):
        # ALA-LC romanization: ḥ carries a dot, ʻ stands for ayin.
        assert match_tokens("Ha-ḥayim ʻal") == {"ha", "hayim", "al"}

    def test_maqaf_separates_words(self):
        assert match_tokens("בית־המדרש") == {"בית", "המדרש"}

    def test_single_character_tokens_dropped(self):
        # Abbreviation fragments and initials: "N.Y.", "A.Z."
        assert match_tokens("Brooklyn, N.Y.") == {"brooklyn"}
        assert match_tokens("דפוס א.ז. וו. סאלאט") == {"דפוס", "וו", "סאלאט"}

    def test_empty_and_none(self):
        assert match_tokens("") == frozenset()
        assert match_tokens(None) == frozenset()
        assert match_tokens(" / : ") == frozenset()


# ---------------------------------------------------------------------------
# Years
# ---------------------------------------------------------------------------


class TestExtractYears:
    @pytest.mark.parametrize(
        "value",
        [
            "1999",
            "[1999]",
            "c1999",
            "©1999",
            "1999.",
            "[1999?]",
            "5759 [1999]",
        ],
    )
    def test_catalog_date_forms(self, value):
        assert extract_years(value) == {1999}

    def test_range(self):
        assert extract_years("1994-2003") == {1994, 2003}

    def test_no_year(self):
        assert extract_years("n.d.") == frozenset()
        assert extract_years("") == frozenset()
        assert extract_years(None) == frozenset()

    def test_gematria_year(self):
        # The NLI fixture's 260$c; its 008 says 1887.
        assert extract_years('תרמ"ז.') == {1887}

    def test_gematria_with_typographic_gershayim(self):
        assert extract_years("תשע״ד") == {2014}

    def test_gematria_with_thousands(self):
        assert extract_years("ה'תשפ\"ה") == {2025}

    def test_gematria_beside_gregorian(self):
        assert extract_years('תשע"ד (2014)') == {2014}

    def test_lefrat_katan_is_not_a_year(self):
        # "לפ"ק" follows the year on a title page and is not one.
        assert extract_years('תרמ"ז לפ"ק') == {1887}

    def test_word_without_gershayim_is_not_a_year(self):
        # "שנת" (year) sums to 750 but is a word, not a year.
        assert extract_years("שנת") == frozenset()


class TestHebrewYearToGregorian:
    def test_final_letter_counts_at_base_value(self):
        # תש"ן: final nun is 50, so 5750, the year 1990.
        assert hebrew_year_to_gregorian('תש"ן') == 1990

    def test_out_of_range_is_rejected(self):
        assert hebrew_year_to_gregorian('לפ"ק') is None

    def test_plain_word_is_rejected(self):
        assert hebrew_year_to_gregorian("שנת") is None
        assert hebrew_year_to_gregorian("") is None


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------


class TestTitle:
    def test_hebrew_page_title_against_lc_880(self, lc_record):
        match = score_candidate({"title": "איש ההלכה"}, lc_record)
        assert _verdicts(match)["title"].verdict == AGREED

    def test_romanized_page_title_against_lc_245(self, lc_record):
        match = score_candidate({"title_romanized": "Halakhic man"}, lc_record)
        assert _verdicts(match)["title"].verdict == AGREED

    def test_hebrew_page_title_against_nli_245(self, nli_record):
        match = score_candidate({"title": "ספר מאה שערים"}, nli_record)
        assert _verdicts(match)["title"].verdict == AGREED

    def test_subtitle_in_245b_does_not_count_against(self, nli_record):
        # The record's $b is a subtitle the page reading kept separate.
        match = score_candidate({"title": "מאה שערים"}, nli_record)
        assert _verdicts(match)["title"].similarity == 1.0

    def test_hebrew_prefix_letter_is_a_near_match(self, nli_record):
        match = score_candidate({"title": "ספר מאה השערים"}, nli_record)
        assert _verdicts(match)["title"].verdict == AGREED

    def test_agreement_in_either_script_counts(self, lc_record):
        # The romanization the OCR produced differs from the catalog's,
        # but the Hebrew agrees, and the Hebrew is what was photographed.
        match = score_candidate(
            {"title": "איש ההלכה", "title_romanized": "Ish ha-halakhah"},
            lc_record,
        )
        assert _verdicts(match)["title"].verdict == AGREED

    def test_different_title_disagrees(self, lc_record):
        match = score_candidate({"title": "ספר תהלים"}, lc_record)
        assert _verdicts(match)["title"].verdict == DISAGREED

    def test_hebrew_only_page_against_record_with_no_hebrew(self, dnb_record):
        # Nothing to compare: no verdict rather than a disagreement.
        match = score_candidate({"title": "איש ההלכה"}, dnb_record)
        assert "title" not in _verdicts(match)

    def test_romanized_only_page_against_hebrew_only_record(self, nli_record):
        match = score_candidate(
            {"title_romanized": "Sefer meah shearim"}, nli_record
        )
        assert "title" not in _verdicts(match)

    def test_part_title_of_a_set_record(self, set_record):
        # A photographed volume names its part; the set record carries
        # that in 245 $p, outside ``title``.
        match = score_candidate(
            {"title_romanized": "Rashi Sefer Mishpatim"}, set_record
        )
        assert _verdicts(match)["title"].verdict == AGREED


# ---------------------------------------------------------------------------
# Author
# ---------------------------------------------------------------------------


class TestAuthor:
    def test_inverted_catalog_form_against_page_order(self, nli_record):
        match = score_candidate({"author": "יצחק הורוויץ"}, nli_record)
        assert _verdicts(match)["author"].verdict == AGREED

    def test_typographic_geresh_against_ascii_in_880(self, lc_record):
        match = score_candidate({"author": "יוסף דב סולובייצ׳יק"}, lc_record)
        assert _verdicts(match)["author"].verdict == AGREED

    def test_romanized_page_author_against_100(self, lc_record):
        match = score_candidate(
            {"author_romanized": "Joseph Dov Soloveitchik"}, lc_record
        )
        assert _verdicts(match)["author"].verdict == AGREED

    def test_additional_author_counts(self, set_record):
        # The page names the translator; the record has him in a 700.
        match = score_candidate(
            {"author_romanized": "Yisrael Isser Zvi Herczeg"}, set_record
        )
        assert _verdicts(match)["author"].verdict == AGREED

    def test_honorifics_on_the_page_are_ignored(self, nli_record):
        match = score_candidate(
            {"author": 'מאת הרב יצחק הורוויץ זצ"ל'}, nli_record
        )
        assert _verdicts(match)["author"].verdict == AGREED

    def test_surname_only_record_form_agrees(self, set_record):
        match = score_candidate({"author_romanized": "Rabbi Gold"}, set_record)
        assert _verdicts(match)["author"].verdict == AGREED

    def test_different_author_disagrees(self, nli_record):
        match = score_candidate({"author": "משה בן מימון"}, nli_record)
        assert _verdicts(match)["author"].verdict == DISAGREED

    def test_no_author_on_record_is_not_compared(self):
        record = parse_record(
            marc_fixtures._record_with_245(
                '    <subfield code="a">Anonymous treatise.</subfield>'
            )
        )
        match = score_candidate({"author": "יצחק הורוויץ"}, record)
        assert "author" not in _verdicts(match)


# ---------------------------------------------------------------------------
# Publisher and place
# ---------------------------------------------------------------------------


class TestPublisherAndPlace:
    def test_corporate_suffix_and_marc_punctuation(self, lc_record):
        match = score_candidate({"publisher": "Sefer Press, Ltd."}, lc_record)
        assert _verdicts(match)["publisher"].verdict == AGREED

    def test_hebrew_generic_publishing_words_ignored(self, nli_record):
        # 260$b is "דפוס א.ז. וו. סאלאט": a printing house.
        match = score_candidate({"publisher": "בדפוס סאלאט"}, nli_record)
        assert _verdicts(match)["publisher"].verdict == AGREED

    def test_publisher_in_a_different_script_is_not_compared(self, lc_record):
        match = score_candidate({"publisher": "הוצאת ספר"}, lc_record)
        assert "publisher" not in _verdicts(match)

    def test_place_abbreviation_against_full_form(self):
        record = {"place": "Brooklyn, N.Y. :"}
        match = score_candidate({"place": "Brooklyn, New York"}, record)
        assert _verdicts(match)["place"].verdict == AGREED

    def test_hebrew_place_with_marc_punctuation(self, nli_record):
        # 260$a is "לעמבערג :" (Lemberg in Yiddish orthography).
        match = score_candidate({"place": "לעמבערג"}, nli_record)
        assert _verdicts(match)["place"].verdict == AGREED

    def test_different_place_disagrees(self, lc_record):
        match = score_candidate({"place": "Tel Aviv"}, lc_record)
        assert _verdicts(match)["place"].verdict == DISAGREED


# ---------------------------------------------------------------------------
# Date
# ---------------------------------------------------------------------------


class TestDate:
    @pytest.mark.parametrize(
        "record_date", ["[1999]", "c1999", "1994-2003", "1999."]
    )
    def test_catalog_date_forms(self, record_date):
        match = score_candidate({"date": "1999"}, {"date": record_date})
        assert _verdicts(match)["date"].verdict == AGREED

    def test_off_by_one_is_partial(self):
        match = score_candidate({"date": "1998"}, {"date": "1999"})
        assert _verdicts(match)["date"].verdict == PARTIAL

    def test_further_off_disagrees(self):
        match = score_candidate({"date": "1990"}, {"date": "1999"})
        assert _verdicts(match)["date"].verdict == DISAGREED

    def test_gematria_record_date_against_gregorian_page(self, nli_record):
        match = score_candidate({"date": "1887"}, nli_record)
        assert _verdicts(match)["date"].verdict == AGREED

    def test_gematria_page_date_against_gregorian_record(self, lc_record):
        # 5767 ran from autumn 2006 to autumn 2007; the record says 2007.
        match = score_candidate({"date": 'תשס"ז'}, lc_record)
        assert _verdicts(match)["date"].verdict == AGREED

    def test_gematria_straddle_is_partial(self, nli_record):
        # Printed in the autumn of 1886, still 5647.
        match = score_candidate({"date": "1886"}, nli_record)
        assert _verdicts(match)["date"].verdict == PARTIAL

    def test_unparseable_date_is_not_compared(self, lc_record):
        match = score_candidate({"date": "n.d."}, lc_record)
        assert "date" not in _verdicts(match)


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------

PAGE_FOR_LC = {
    "title": "איש ההלכה",
    "subtitle": "מסה פילוסופי",
    "author": "יוסף דב סולובייצ'יק",
    "publisher": "Sefer Press",
    "place": "Jerusalem",
    "date": "2007",
    "title_romanized": "Halakhic man",
    "author_romanized": "Joseph Dov Soloveitchik",
}


class TestScore:
    def test_full_agreement_scores_one(self, lc_record):
        match = score_candidate(PAGE_FOR_LC, lc_record)
        assert match.score == 1.0
        assert match.agreed == (
            "title",
            "author",
            "date",
            "publisher",
            "place",
        )

    def test_nothing_comparable_scores_zero(self, dnb_record):
        match = score_candidate({"title": "איש ההלכה"}, dnb_record)
        assert match.score == 0.0
        assert match.verdicts == ()

    def test_empty_metadata_scores_zero(self, lc_record):
        match = score_candidate({}, lc_record)
        assert match.score == 0.0
        assert match.verdicts == ()

    def test_score_stays_within_unit_interval(self, lc_record, nli_record):
        for page in (PAGE_FOR_LC, {"title": "ספר תהלים", "date": "1700"}):
            for record in (lc_record, nli_record):
                assert 0.0 <= score_candidate(page, record).score <= 1.0

    def test_verdicts_follow_weight_order(self, lc_record):
        match = score_candidate(PAGE_FOR_LC, lc_record)
        assert [v.field for v in match.verdicts] == list(WEIGHTS)

    def test_sparse_record_is_not_punished_for_omissions(self, lc_record):
        # A title-only record that agrees on the title beats a full
        # record that disagrees on the rest.
        sparse = parse_record(
            marc_fixtures._record_with_245(
                '    <subfield code="a">איש ההלכה /</subfield>'
            )
        )
        page = dict(PAGE_FOR_LC, publisher="Mosad", place="Tel Aviv")
        page["date"] = "1990"
        assert (
            score_candidate(page, sparse).score
            > score_candidate(page, lc_record).score
        )

    def test_more_agreeing_fields_break_a_tie(self, lc_record):
        sparse = parse_record(
            marc_fixtures._record_with_245(
                '    <subfield code="a">איש ההלכה /</subfield>'
            )
        )
        full = score_candidate(PAGE_FOR_LC, lc_record)
        only_title = score_candidate(PAGE_FOR_LC, sparse)
        assert full.score > only_title.score
        assert only_title.score > 0.9

    def test_only_the_publisher_agrees(self, lc_record):
        page = {
            "title": "ספר תהלים",
            "author": "דוד המלך",
            "publisher": "Sefer Press",
            "place": "Tel Aviv",
            "date": "1990",
        }
        match = score_candidate(page, lc_record)
        verdicts = _verdicts(match)
        assert verdicts["publisher"].verdict == AGREED
        assert verdicts["title"].verdict == DISAGREED
        assert verdicts["author"].verdict == DISAGREED
        assert verdicts["place"].verdict == DISAGREED
        assert verdicts["date"].verdict == DISAGREED
        assert match.agreed == ("publisher",)
        assert match.score < 0.2

    def test_percent_is_a_whole_number(self, lc_record):
        match = score_candidate({"title": "איש ההלכה"}, lc_record)
        assert match.percent == 96

    def test_metadata_values_may_be_none_or_blank(self, lc_record):
        page = {key: None for key in PAGE_FOR_LC}
        page["title"] = ""
        page["title_romanized"] = "Halakhic man"
        match = score_candidate(page, lc_record)
        assert _verdicts(match)["title"].verdict == AGREED

    def test_record_values_may_be_none(self):
        record = {
            "title": "איש ההלכה",
            "title_alternate": None,
            "author": None,
            "additional_authors": [],
            "publisher": None,
            "place": None,
            "date": None,
        }
        match = score_candidate(PAGE_FOR_LC, record)
        assert [v.field for v in match.verdicts] == ["title"]


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class TestRankCandidates:
    def test_orders_across_catalogs(self, lc_record, nli_record):
        nli = dict(nli_record, source_catalog="NLI")
        lc = dict(lc_record, source_catalog="LC")
        ranked = rank_candidates(PAGE_FOR_LC, [nli, lc])
        assert [c["source_catalog"] for c, _ in ranked] == ["LC", "NLI"]
        assert ranked[0][1].score > ranked[1][1].score

    def test_ties_keep_arrival_order(self, lc_record):
        first = dict(lc_record, source_catalog="NLI")
        second = dict(lc_record, source_catalog="LC")
        ranked = rank_candidates(PAGE_FOR_LC, [first, second])
        assert [c["source_catalog"] for c, _ in ranked] == ["NLI", "LC"]

    def test_empty(self):
        assert rank_candidates(PAGE_FOR_LC, []) == []


# ---------------------------------------------------------------------------
# The view orders the table by score
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_logged_in(client, db):
    user = User.objects.create_user(username="reader", password="pw")
    client.force_login(user)
    return client


def _search(client, metadata, scan_id=None):
    payload = {"action": "search", **metadata}
    if scan_id is not None:
        payload["scan_id"] = str(scan_id)
    return client.post("/ingest/upload-title/", payload)


def _row_order(html: str, *needles: str) -> list[str]:
    return sorted(needles, key=html.index)


@pytest.mark.django_db
class TestSearchOrdersCandidatesByScore:
    """The table used to list NLI first, then LC, whatever the page said."""

    def test_lc_match_outranks_nli_miss(
        self, client_logged_in, lc_record, nli_record
    ):
        with (
            patch("ingest.views.search_nli") as mock_nli,
            patch("ingest.views.search_lc") as mock_lc,
        ):
            mock_nli.return_value = CascadeResult(records=[nli_record])
            mock_lc.return_value = CascadeResult(records=[lc_record])
            response = _search(client_logged_in, PAGE_FOR_LC)

        html = response.content.decode()
        assert _row_order(html, "Halakhic man", "מאה שערים") == [
            "Halakhic man",
            "מאה שערים",
        ]

    def test_stored_candidates_follow_the_same_order(
        self, client_logged_in, lc_record, nli_record
    ):
        # ``candidate_index`` on the way back through confirm has to name
        # the row the user saw, so what is stored is what was shown.
        user = User.objects.get(username="reader")
        scan = ScanResult.objects.create(
            scan_type="ocr",
            status="pending",
            ocr_output=PAGE_FOR_LC,
            scanned_by=user,
        )
        with (
            patch("ingest.views.search_nli") as mock_nli,
            patch("ingest.views.search_lc") as mock_lc,
        ):
            mock_nli.return_value = CascadeResult(records=[nli_record])
            mock_lc.return_value = CascadeResult(records=[lc_record])
            _search(client_logged_in, PAGE_FOR_LC, scan_id=scan.pk)

        scan.refresh_from_db()
        assert [c["source_catalog"] for c in scan.candidate_records] == [
            "LC",
            "NLI",
        ]

    def test_each_row_says_which_fields_agreed(
        self, client_logged_in, lc_record
    ):
        page = dict(PAGE_FOR_LC, date="1990")
        with (
            patch("ingest.views.search_nli") as mock_nli,
            patch("ingest.views.search_lc") as mock_lc,
        ):
            mock_nli.return_value = CascadeResult(records=[])
            mock_lc.return_value = CascadeResult(records=[lc_record])
            response = _search(client_logged_in, page)

        html = response.content.decode()
        assert "Match" in html
        assert 'data-verdict="agreed">title<' in html
        assert 'data-verdict="disagreed">date<' in html
        assert "Ordered by agreement" in html

    def test_isbn_lookup_table_is_unchanged(self, client_logged_in, lc_record):
        with patch("ingest.views.isbn_lookup") as mock_lookup:
            mock_lookup.return_value = {
                "nli_records": [],
                "lc_records": [lc_record],
                "dnb_records": [],
            }
            response = client_logged_in.post(
                "/ingest/isbn-lookup/", {"isbn": "9789650716745"}
            )

        html = response.content.decode()
        assert "data-verdict" not in html
        assert "Ordered by source catalog" in html
