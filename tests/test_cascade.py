"""Tests for the search cascade engine and ISBN lookup.

All tests mock network calls -- no live server requests.
"""

from unittest.mock import MagicMock, patch

from sources.cascade import (
    NLI_CASCADE,
    CascadeResult,
    _build_lc_keyword_query,
    _format_query,
    isbn_lookup,
    run_cascade,
)
from sources.normalize import normalize_publisher
from sources.sru import SRUClient, SRUResult


# --- Helpers ---

# Minimal valid SRU+MARCXML response with one record.
_SRU_XML_ONE_RECORD = """\
<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>1</numberOfRecords>
  <records>
    <record>
      <recordData>
        <record xmlns="http://www.loc.gov/MARC21/slim">
          <leader>00000nam a2200000 a 4500</leader>
          <controlfield tag="001">test001</controlfield>
          <controlfield tag="008">200101s2020    is            000 0 heb d</controlfield>
          <datafield tag="245" ind1="1" ind2="0">
            <subfield code="a">Test Title</subfield>
          </datafield>
        </record>
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>"""

_SRU_XML_EMPTY = """\
<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>0</numberOfRecords>
  <records/>
</searchRetrieveResponse>"""


def _make_client(**kwargs) -> SRUClient:
    defaults = dict(base_url="https://example.com/sru", request_delay=0)
    defaults.update(kwargs)
    return SRUClient(**defaults)


# --- Cascade step skipping ---


class TestCascadeSkipping:
    """Steps are skipped when required metadata fields are missing."""

    def test_skip_step_missing_place(self):
        """A step requiring {place} is skipped when place is absent."""
        metadata = {"title": "Talmud", "date": "1900"}
        # The first NLI step needs title+place+date.
        query = _format_query(NLI_CASCADE[0][1], metadata)
        assert query is None

    def test_skip_step_missing_date(self):
        metadata = {"title": "Talmud", "place": "Jerusalem"}
        query = _format_query(NLI_CASCADE[0][1], metadata)
        assert query is None

    def test_skip_step_empty_value(self):
        """Empty string values are treated as missing."""
        metadata = {"title": "Talmud", "place": "", "date": "1900"}
        query = _format_query(NLI_CASCADE[0][1], metadata)
        assert query is None

    def test_format_succeeds_with_all_fields(self):
        metadata = {"title": "Talmud", "place": "Jerusalem", "date": "1900"}
        query = _format_query(NLI_CASCADE[0][1], metadata)
        assert query is not None
        assert "Talmud" in query
        assert "Jerusalem" in query
        assert "1900" in query


# --- Cascade stops at first successful step ---


class TestCascadeStopsAtFirstHit:
    @patch("sources.cascade.nli_client")
    def test_stops_at_first_match(self, _mock_nli):
        """Cascade returns after the first step that yields records."""
        client = _make_client()

        # First call: empty result. Second call: one record.
        client.search = MagicMock(
            side_effect=[
                SRUResult(success=True, data=_SRU_XML_EMPTY),
                SRUResult(success=True, data=_SRU_XML_ONE_RECORD),
            ]
        )

        # Use a two-step cascade where both steps have the required field.
        cascade = [
            ("step_a", 'alma.title="{title}"'),
            ("step_b", 'alma.all_for_ui="{title}"'),
        ]
        metadata = {"title": "Talmud"}

        result = run_cascade(client, cascade, metadata)

        assert result.step == "step_b"
        assert result.total_hits == 1
        assert len(result.records) == 1
        assert result.records[0]["title"] == "Test Title"
        # Client should have been called exactly twice.
        assert client.search.call_count == 2

    @patch("sources.cascade.nli_client")
    def test_first_step_succeeds(self, _mock_nli):
        """If the first step matches, later steps are never called."""
        client = _make_client()
        client.search = MagicMock(
            return_value=SRUResult(success=True, data=_SRU_XML_ONE_RECORD)
        )

        cascade = [
            ("step_a", 'alma.title="{title}"'),
            ("step_b", 'alma.all_for_ui="{title}"'),
        ]
        metadata = {"title": "Talmud"}

        result = run_cascade(client, cascade, metadata)

        assert result.step == "step_a"
        assert client.search.call_count == 1


# --- Cascade returns empty when nothing matches ---


class TestCascadeEmptyResult:
    def test_no_results(self):
        client = _make_client()
        client.search = MagicMock(
            return_value=SRUResult(success=True, data=_SRU_XML_EMPTY)
        )

        cascade = [("only_step", 'alma.title="{title}"')]
        metadata = {"title": "Nonexistent"}

        result = run_cascade(client, cascade, metadata)

        assert result == CascadeResult()
        assert result.step == ""
        assert result.query_used == ""
        assert result.records == []
        assert result.total_hits == 0

    def test_all_steps_skipped(self):
        """If every step requires a missing field, result is empty."""
        client = _make_client()
        client.search = MagicMock()

        cascade = [
            (
                "needs_date",
                'alma.title="{title}" AND alma.main_pub_date={date}',
            )
        ]
        metadata = {"title": "Talmud"}  # no date

        result = run_cascade(client, cascade, metadata)

        assert result == CascadeResult()
        # Search should never have been called.
        client.search.assert_not_called()

    def test_sru_failure_continues(self):
        """If an SRU request fails, the cascade moves to the next step."""
        client = _make_client()
        client.search = MagicMock(
            side_effect=[
                SRUResult(success=False, error="timeout"),
                SRUResult(success=True, data=_SRU_XML_ONE_RECORD),
            ]
        )

        cascade = [
            ("step_a", 'alma.title="{title}"'),
            ("step_b", 'alma.all_for_ui="{title}"'),
        ]
        metadata = {"title": "Talmud"}

        result = run_cascade(client, cascade, metadata)

        assert result.step == "step_b"
        assert client.search.call_count == 2


# --- LC multi-keyword AND query ---


class TestLCKeywordQuery:
    def test_builds_and_query(self):
        # Hebrew words longer than 2 chars.
        metadata = {
            "title": "\u05ea\u05dc\u05de\u05d5\u05d3 \u05d1\u05d1\u05dc\u05d9 \u05de\u05e1\u05db\u05ea"
        }
        query = _build_lc_keyword_query(metadata)
        assert query is not None
        assert "AND" in query
        # Each word wrapped in cql.anywhere="..."
        assert 'cql.anywhere="' in query

    def test_returns_none_for_short_title(self):
        metadata = {"title": "\u05d0\u05d1"}  # single 2-char Hebrew word
        query = _build_lc_keyword_query(metadata)
        assert query is None

    def test_returns_none_for_non_hebrew(self):
        metadata = {"title": "Talmud Bavli"}
        query = _build_lc_keyword_query(metadata)
        assert query is None

    def test_returns_none_when_title_missing(self):
        query = _build_lc_keyword_query({})
        assert query is None

    def test_filters_short_words(self):
        # Mix of short and long Hebrew words.
        metadata = {
            "title": "\u05ea\u05dc\u05de\u05d5\u05d3 \u05d0\u05d1 \u05d1\u05d1\u05dc\u05d9"
        }
        query = _build_lc_keyword_query(metadata)
        assert query is not None
        # The 2-char word should be excluded.
        assert "\u05d0\u05d1" not in query

    def test_keyword_step_in_cascade(self):
        """The LC cascade keywords step uses the dynamic builder."""
        client = _make_client()
        client.search = MagicMock(
            return_value=SRUResult(success=True, data=_SRU_XML_ONE_RECORD)
        )

        # Only include the keywords step.
        cascade = [("keywords", "__LC_KEYWORDS__")]
        metadata = {
            "title": "\u05ea\u05dc\u05de\u05d5\u05d3 \u05d1\u05d1\u05dc\u05d9 \u05de\u05e1\u05db\u05ea"
        }

        result = run_cascade(client, cascade, metadata)

        assert result.step == "keywords"
        assert "cql.anywhere" in result.query_used


# --- ISBN lookup ---


class TestISBNLookup:
    @patch("sources.cascade.dnb_client")
    @patch("sources.cascade.lc_client")
    @patch("sources.cascade.nli_client")
    def test_isbn_all_catalogs(self, mock_nli, mock_lc, mock_dnb):
        mock_nli.search.return_value = SRUResult(
            success=True, data=_SRU_XML_ONE_RECORD
        )
        mock_lc.search.return_value = SRUResult(
            success=True, data=_SRU_XML_ONE_RECORD
        )
        mock_dnb.search.return_value = SRUResult(
            success=True, data=_SRU_XML_ONE_RECORD
        )

        result = isbn_lookup("9780123456789")

        assert len(result["nli_records"]) == 1
        assert len(result["lc_records"]) == 1
        assert len(result["dnb_records"]) == 1
        assert result["nli_records"][0]["title"] == "Test Title"
        assert result["lc_records"][0]["title"] == "Test Title"
        assert result["dnb_records"][0]["title"] == "Test Title"

        # Verify correct ISBN query syntax per catalog.
        mock_nli.search.assert_called_once_with("alma.isbn=9780123456789")
        mock_lc.search.assert_called_once_with("bath.isbn=9780123456789")
        mock_dnb.search.assert_called_once_with(
            "dnb.num=9780123456789", record_schema="MARC21-xml"
        )

    @patch("sources.cascade.dnb_client")
    @patch("sources.cascade.lc_client")
    @patch("sources.cascade.nli_client")
    def test_isbn_nli_fails_others_succeed(self, mock_nli, mock_lc, mock_dnb):
        mock_nli.search.side_effect = Exception("NLI down")
        mock_lc.search.return_value = SRUResult(
            success=True, data=_SRU_XML_ONE_RECORD
        )
        mock_dnb.search.return_value = SRUResult(
            success=True, data=_SRU_XML_ONE_RECORD
        )

        result = isbn_lookup("9780123456789")

        assert result["nli_records"] == []
        assert len(result["lc_records"]) == 1
        assert len(result["dnb_records"]) == 1

    @patch("sources.cascade.dnb_client")
    @patch("sources.cascade.lc_client")
    @patch("sources.cascade.nli_client")
    def test_isbn_lc_fails_others_succeed(self, mock_nli, mock_lc, mock_dnb):
        mock_nli.search.return_value = SRUResult(
            success=True, data=_SRU_XML_ONE_RECORD
        )
        mock_lc.search.side_effect = Exception("LC down")
        mock_dnb.search.return_value = SRUResult(
            success=True, data=_SRU_XML_ONE_RECORD
        )

        result = isbn_lookup("9780123456789")

        assert len(result["nli_records"]) == 1
        assert result["lc_records"] == []
        assert len(result["dnb_records"]) == 1

    @patch("sources.cascade.dnb_client")
    @patch("sources.cascade.lc_client")
    @patch("sources.cascade.nli_client")
    def test_isbn_dnb_fails_others_succeed(self, mock_nli, mock_lc, mock_dnb):
        mock_nli.search.return_value = SRUResult(
            success=True, data=_SRU_XML_ONE_RECORD
        )
        mock_lc.search.return_value = SRUResult(
            success=True, data=_SRU_XML_ONE_RECORD
        )
        mock_dnb.search.side_effect = Exception("DNB down")

        result = isbn_lookup("9780123456789")

        assert len(result["nli_records"]) == 1
        assert len(result["lc_records"]) == 1
        assert result["dnb_records"] == []

    @patch("sources.cascade.dnb_client")
    @patch("sources.cascade.lc_client")
    @patch("sources.cascade.nli_client")
    def test_isbn_all_fail(self, mock_nli, mock_lc, mock_dnb):
        mock_nli.search.side_effect = Exception("NLI down")
        mock_lc.search.side_effect = Exception("LC down")
        mock_dnb.search.side_effect = Exception("DNB down")

        result = isbn_lookup("9780123456789")

        assert result["nli_records"] == []
        assert result["lc_records"] == []
        assert result["dnb_records"] == []

    @patch("sources.cascade.dnb_client")
    @patch("sources.cascade.lc_client")
    @patch("sources.cascade.nli_client")
    def test_isbn_empty_results(self, mock_nli, mock_lc, mock_dnb):
        mock_nli.search.return_value = SRUResult(
            success=True, data=_SRU_XML_EMPTY
        )
        mock_lc.search.return_value = SRUResult(
            success=True, data=_SRU_XML_EMPTY
        )
        mock_dnb.search.return_value = SRUResult(
            success=True, data=_SRU_XML_EMPTY
        )

        result = isbn_lookup("0000000000")

        assert result["nli_records"] == []
        assert result["lc_records"] == []
        assert result["dnb_records"] == []


# --- Publisher normalization ---


class TestNormalizePublisher:
    """Corporate suffixes and MARC punctuation are stripped."""

    def test_comma_suffix_with_period(self):
        assert (
            normalize_publisher("Mesorah Publications, Ltd.")
            == "Mesorah Publications"
        )

    def test_suffix_without_comma_or_period(self):
        assert (
            normalize_publisher("Mesorah Publications Ltd")
            == "Mesorah Publications"
        )

    def test_ampersand_name_keeps_its_words(self):
        assert (
            normalize_publisher("W. W. Norton & Company, Inc.")
            == "W. W. Norton & Company"
        )

    def test_llc(self):
        assert normalize_publisher("Random House, LLC") == "Random House"

    def test_gmbh(self):
        assert normalize_publisher("Springer-Verlag GmbH") == "Springer-Verlag"

    def test_suffix_match_is_case_insensitive(self):
        assert normalize_publisher("Feldheim, LTD.") == "Feldheim"
        assert normalize_publisher("Feldheim, inc") == "Feldheim"

    def test_two_stacked_suffixes(self):
        assert (
            normalize_publisher("Soncino Press Ltd., Inc.") == "Soncino Press"
        )

    def test_trailing_marc_comma(self):
        assert normalize_publisher("Schocken Books,") == "Schocken Books"

    def test_trailing_marc_semicolon(self):
        assert (
            normalize_publisher("Yale University Press ;")
            == "Yale University Press"
        )

    def test_trailing_marc_colon_after_suffix(self):
        assert (
            normalize_publisher("Mesorah Publications, Ltd. :")
            == "Mesorah Publications"
        )

    def test_name_needing_no_change(self):
        assert (
            normalize_publisher("Mesorah Publications")
            == "Mesorah Publications"
        )
        assert normalize_publisher("ArtScroll") == "ArtScroll"

    def test_word_ending_in_a_suffix_is_not_truncated(self):
        assert normalize_publisher("Sinclair") == "Sinclair"

    def test_hebrew_name_passes_through(self):
        assert normalize_publisher("מוסד הרב קוק") == "מוסד הרב קוק"

    def test_hebrew_name_loses_only_marc_punctuation(self):
        assert normalize_publisher("מוסד הרב קוק,") == "מוסד הרב קוק"

    def test_none(self):
        assert normalize_publisher(None) == ""

    def test_empty(self):
        assert normalize_publisher("") == ""

    def test_whitespace_only(self):
        assert normalize_publisher("   ") == ""

    def test_suffix_alone_normalizes_to_empty(self):
        assert normalize_publisher("Ltd.") == ""


class TestPublisherStepsUseNormalizedValue:
    """Cascade steps carrying {publisher} query the normalized form."""

    def _publisher_template(self) -> str:
        return dict(NLI_CASCADE)["title+publisher"]

    def test_query_drops_the_suffix(self):
        metadata = {
            "title": "ויקרא",
            "publisher": "Mesorah Publications, Ltd.",
        }
        query = _format_query(self._publisher_template(), metadata)
        assert query == (
            'alma.title="ויקרא" AND alma.publisher="Mesorah Publications"'
        )

    def test_other_fields_are_untouched(self):
        """Only the publisher is normalized; a title keeps its punctuation."""
        metadata = {
            "title": "Rashi : the Torah",
            "publisher": "Mesorah Publications, Ltd.",
        }
        query = _format_query(self._publisher_template(), metadata)
        assert 'alma.title="Rashi : the Torah"' in query

    def test_metadata_is_not_mutated(self):
        metadata = {
            "title": "ויקרא",
            "publisher": "Mesorah Publications, Ltd.",
        }
        _format_query(self._publisher_template(), metadata)
        assert metadata["publisher"] == "Mesorah Publications, Ltd."

    def test_publisher_normalizing_to_empty_skips_the_step(self):
        metadata = {"title": "ויקרא", "publisher": ", Ltd."}
        assert _format_query(self._publisher_template(), metadata) is None

    def test_cascade_falls_through_when_publisher_normalizes_to_empty(self):
        """An empty normalized publisher skips its step, it does not error."""
        client = _make_client()
        client.search = MagicMock(
            return_value=SRUResult(success=True, data=_SRU_XML_ONE_RECORD)
        )

        cascade = [
            ("title+publisher", self._publisher_template()),
            ("title", 'alma.title="{title}"'),
        ]
        metadata = {"title": "ויקרא", "publisher": "Ltd."}

        result = run_cascade(client, cascade, metadata)

        assert result.step == "title"
        assert client.search.call_count == 1
        assert "publisher" not in result.query_used
