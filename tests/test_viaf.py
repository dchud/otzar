"""Tests for the VIAF client module."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from sources.cache import DEFAULT_TTL, EMPTY_TTL, ResponseCache
from sources.viaf import (
    AMBIGUOUS,
    HEADING,
    INCOMPLETE,
    MATCHED,
    NO_MATCH,
    UNSUPPORTED,
    VARIANT,
    VARIANT_ONLY,
    VIAFClient,
    VIAFSearchResult,
    _build_author_queries,
    _normalize,
    birth_year,
    choose_cluster,
    cluster_matches,
    match_cluster,
    name_tokens,
    parse_clusters,
    parse_record_count,
    parse_response,
    storable_forms,
    viaf_enrich,
)
from tests.viaf_fixtures import (
    COHEN_1949,
    COHEN_1949_ID,
    COHEN_1955,
    COHEN_PLAIN,
    COHEN_PLAIN_ID,
    DOV_BER,
    EMPTY,
    FRADKIN,
    FRADKIN_ID,
    FREIDA,
    HESCHEL_DNB,
    PTBNP_SPLIT,
    PTBNP_SPLIT_ID,
    SHNEUR_ZALMAN,
    SHNEUR_ZALMAN_ID,
    cluster,
    response,
    x400,
)

# ---------------------------------------------------------------------------
# Sample XML fixture — minimal SRU response with one VIAF cluster
# ---------------------------------------------------------------------------

SAMPLE_VIAF_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>1</numberOfRecords>
  <records>
    <record>
      <recordSchema>VIAF</recordSchema>
      <recordData>
        <VIAFCluster xmlns="http://viaf.org/viaf/terms#">
          <viafID>12345678</viafID>
          <nameType>Personal</nameType>
          <mainHeadings>
            <data>
              <text>משה בן מימון</text>
              <sources>
                <s>J9U</s>
                <s>LC</s>
              </sources>
            </data>
            <data>
              <text>Maimonides, Moses, 1138-1204</text>
              <sources>
                <s>LC</s>
              </sources>
            </data>
          </mainHeadings>
          <sources>
            <source>J9U|987007279341105171</source>
            <source>LC|n  80032695</source>
          </sources>
          <x400s>
            <x400>
              <datafield dtype="MARC21" ind1="0" ind2=" " tag="400">
                <subfield code="a">Rambam</subfield>
                <normalized>rambam</normalized>
              </datafield>
              <sources>
                <s>LC</s>
              </sources>
            </x400>
            <x400>
              <datafield dtype="MARC21" ind1="0" ind2=" " tag="400">
                <subfield code="a">Moses</subfield>
                <subfield code="c">ben Maimon</subfield>
              </datafield>
              <sources>
                <s>J9U</s>
              </sources>
            </x400>
          </x400s>
        </VIAFCluster>
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>
"""

SAMPLE_EMPTY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>0</numberOfRecords>
  <records/>
</searchRetrieveResponse>
"""

SAMPLE_MULTI_CLUSTER_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>2</numberOfRecords>
  <records>
    <record>
      <recordSchema>VIAF</recordSchema>
      <recordData>
        <VIAFCluster xmlns="http://viaf.org/viaf/terms#">
          <viafID>11111111</viafID>
          <mainHeadings>
            <data>
              <text>No Source Author</text>
              <sources><s>DNB</s></sources>
            </data>
          </mainHeadings>
          <sources>
            <source>DNB|118575449</source>
          </sources>
          <x400s/>
        </VIAFCluster>
      </recordData>
    </record>
    <record>
      <recordSchema>VIAF</recordSchema>
      <recordData>
        <VIAFCluster xmlns="http://viaf.org/viaf/terms#">
          <viafID>22222222</viafID>
          <mainHeadings>
            <data>
              <text>Good Author</text>
              <sources><s>J9U</s><s>LC</s></sources>
            </data>
          </mainHeadings>
          <sources>
            <source>J9U|9870001</source>
            <source>LC|n  12345</source>
          </sources>
          <x400s/>
        </VIAFCluster>
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>
"""

LC_HEADING = "Shneur Zalman, of Lyady, 1745-1812"
NLI_HEADING = "שניאור זלמן בן ברוך, 1745-1812"
SHORT_HEBREW = "שניאור זלמן מלאדי"


def clusters_of(xml_text):
    """Parse a response into clusters keyed by VIAF ID."""
    return {c.viaf_id: c for c in parse_clusters(xml_text)}


def result_of(xml_text, max_records=10):
    """Parse a response into the result the client would hand on."""
    total, clusters = parse_response(xml_text)
    return VIAFSearchResult("test", total, clusters, max_records)


# ---------------------------------------------------------------------------
# Cluster parsing tests
# ---------------------------------------------------------------------------


class TestParseClusters:
    def test_parse_single_cluster(self):
        clusters = parse_clusters(SAMPLE_VIAF_XML)
        assert len(clusters) == 1
        c = clusters[0]
        assert c.viaf_id == "12345678"
        assert len(c.main_headings) == 2
        assert c.main_headings[0]["text"] == "משה בן מימון"
        assert "J9U" in c.main_headings[0]["sources"]
        assert "LC" in c.main_headings[0]["sources"]

    def test_parse_source_ids(self):
        clusters = parse_clusters(SAMPLE_VIAF_XML)
        c = clusters[0]
        assert c.source_ids["J9U"] == "987007279341105171"
        assert c.source_ids["LC"] == "n  80032695"

    def test_parse_variants(self):
        """Tracings are read; the comparison key nested in them is not."""
        clusters = parse_clusters(SAMPLE_VIAF_XML)
        c = clusters[0]
        assert "Rambam" in c.variants
        assert "Moses ben Maimon" in c.variants
        assert "rambam" not in c.variants

    def test_parse_tracing_sources(self):
        c = parse_clusters(SAMPLE_VIAF_XML)[0]
        assert c.x400s[0] == {"text": "Rambam", "sources": ["LC"]}
        assert c.x400s[1]["sources"] == ["J9U"]

    def test_parse_empty_response(self):
        clusters = parse_clusters(SAMPLE_EMPTY_XML)
        assert clusters == []

    def test_parse_multiple_clusters(self):
        clusters = parse_clusters(SAMPLE_MULTI_CLUSTER_XML)
        assert len(clusters) == 2
        assert clusters[0].viaf_id == "11111111"
        assert clusters[1].viaf_id == "22222222"

    def test_parse_invalid_xml(self):
        clusters = parse_clusters("this is not xml at all")
        assert clusters == []

    def test_parse_truncated_xml(self):
        """VIAF sometimes appends HTML after XML; parser should handle it."""
        truncated = SAMPLE_VIAF_XML + "\n<html><body>extra junk</body></html>"
        clusters = parse_clusters(truncated)
        assert len(clusters) == 1
        assert clusters[0].viaf_id == "12345678"

    def test_preferred_heading(self):
        c = parse_clusters(SAMPLE_MULTI_CLUSTER_XML)[1]
        assert c.preferred_heading == "Good Author"
        assert c.has_source({"LC"})
        assert not c.has_source({"BNF"})


class TestParseResponse:
    """The parts of a live response beyond the minimal sample."""

    def test_record_count(self):
        assert parse_record_count(SAMPLE_VIAF_XML) == 1
        assert parse_record_count(SAMPLE_EMPTY_XML) == 0
        assert parse_record_count(response([COHEN_1949], total=390)) == 390

    def test_record_count_missing(self):
        assert parse_record_count("<searchRetrieveResponse/>") is None
        assert parse_record_count("not xml") is None

    def test_count_and_clusters_come_from_one_parse(self):
        total, clusters = parse_response(response([COHEN_1949], total=390))
        assert total == 390
        assert [c.viaf_id for c in clusters] == [COHEN_1949_ID]

    def test_every_tracing_is_kept(self):
        """Nothing is cut off before the Hebrew tracings are reached."""
        c = clusters_of(response([SHNEUR_ZALMAN]))[SHNEUR_ZALMAN_ID]
        assert "שניאור זלמן מלאדי." in c.variants
        assert "Baʻal ha-Tanya, 1745-1812" in c.variants

    def test_only_name_tags_are_tracings(self):
        c = clusters_of(response([SHNEUR_ZALMAN]))[SHNEUR_ZALMAN_ID]
        assert "Ḥabad" not in c.variants
        assert "Šneyʾwr Zalman 1745-1813" in c.variants

    def test_only_name_subfields_are_read(self):
        c = clusters_of(response([SHNEUR_ZALMAN]))[SHNEUR_ZALMAN_ID]
        assert not any("Tanya" in v and "Shneur" in v for v in c.variants)
        assert not any(v.startswith("e ") for v in c.variants)

    def test_a_tracing_without_letters_is_dropped(self):
        c = clusters_of(response([SHNEUR_ZALMAN]))[SHNEUR_ZALMAN_ID]
        assert "+." not in c.variants

    def test_control_and_format_characters_are_stripped(self):
        c = clusters_of(response([SHNEUR_ZALMAN]))[SHNEUR_ZALMAN_ID]
        assert "העילוי 1745-1813" in c.variants
        split = clusters_of(response([PTBNP_SPLIT]))[PTBNP_SPLIT_ID]
        assert split.variants[0] == "Shneur Zalman of Lyady"

    def test_headings_carry_their_sources(self):
        c = clusters_of(response([SHNEUR_ZALMAN]))[SHNEUR_ZALMAN_ID]
        assert c.main_headings[0] == {
            "text": LC_HEADING,
            "sources": ["J9U", "LC"],
        }


# ---------------------------------------------------------------------------
# Cluster matching tests
# ---------------------------------------------------------------------------


class TestClusterMatches:
    @pytest.fixture()
    def sample_cluster(self):
        clusters = parse_clusters(SAMPLE_VIAF_XML)
        return clusters[0]

    def test_exact_hebrew_match(self, sample_cluster):
        assert cluster_matches(
            sample_cluster,
            "משה בן מימון",
        )

    def test_romanized_match(self, sample_cluster):
        assert cluster_matches(sample_cluster, "Maimonides, Moses, 1138-1204")

    def test_variant_match(self, sample_cluster):
        assert cluster_matches(sample_cluster, "Rambam")

    def test_partial_word_match(self, sample_cluster):
        assert cluster_matches(sample_cluster, "Moses ben Maimon")

    def test_no_match(self, sample_cluster):
        assert not cluster_matches(sample_cluster, "Albert Einstein")

    def test_empty_query(self, sample_cluster):
        assert not cluster_matches(sample_cluster, "")

    def test_case_insensitive(self, sample_cluster):
        assert cluster_matches(sample_cluster, "rambam")
        assert cluster_matches(sample_cluster, "RAMBAM")

    def test_punctuation_ignored(self, sample_cluster):
        # Stripping commas/periods shouldn't prevent matching
        assert cluster_matches(sample_cluster, "Maimonides Moses 1138-1204")


# ---------------------------------------------------------------------------
# Normalize helper tests
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_strips_punctuation(self):
        assert _normalize('hello, "world"') == "hello world"

    def test_lowercases(self):
        assert _normalize("Hello World") == "hello world"

    def test_empty(self):
        assert _normalize("") == ""
        assert _normalize(None) == ""

    def test_hebrew_punctuation(self):
        # geresh and gershayim
        assert _normalize("רמב״ם") == "רמבם"


class TestNameTokens:
    """What two files disagree on about one person is set aside."""

    def test_order_punctuation_and_dates_do_not_count(self):
        expected = ("lyady", "of", "shneur", "zalman")
        assert name_tokens(LC_HEADING) == expected
        assert name_tokens("Shneur Zalman 1745-1813 of Lyady") == expected
        assert name_tokens("Shneur Zalman, of Lyady") == expected

    def test_words_are_kept_whole(self):
        assert name_tokens("Shneur Zalman ben Baruch, of Lyady") != (
            name_tokens(LC_HEADING)
        )

    def test_hebrew(self):
        assert name_tokens(NLI_HEADING) == ("בן", "ברוך", "זלמן", "שניאור")
        assert name_tokens("שניאור זלמן בן־ברוך") == name_tokens(
            "שניאור זלמן בן ברוך"
        )

    def test_date_words_go_with_the_digits(self):
        assert name_tokens("Rashi, approximately 1040-1105") == ("rashi",)
        assert name_tokens("Cohen, David, active 15th century") == (
            "century",
            "cohen",
            "david",
        )

    def test_empty(self):
        assert name_tokens("") == ()
        assert name_tokens("1745-1812") == ()


class TestBirthYear:
    def test_first_year_is_the_birth(self):
        assert birth_year(LC_HEADING) == "1745"
        assert birth_year("Cohen, David, 1949-") == "1949"
        assert birth_year("Cohen, David, 1955 December 15-") == "1955"

    def test_a_lone_death_year_is_not_a_birth(self):
        assert birth_year("Rashi, d. 1105") is None
        assert birth_year("Rashi, died 1105") is None

    def test_no_year(self):
        assert birth_year("Cohen, David") is None
        assert birth_year("") is None


# ---------------------------------------------------------------------------
# Matching a cluster against catalog forms
# ---------------------------------------------------------------------------


class TestMatchCluster:
    @pytest.fixture()
    def founder(self):
        return clusters_of(response([SHNEUR_ZALMAN]))[SHNEUR_ZALMAN_ID]

    def test_lc_form_hits_the_lc_heading(self, founder):
        match = match_cluster(founder, ["Shneur Zalman, of Lyady"])
        assert match.tier == HEADING
        assert match.text == LC_HEADING
        assert match.sources == ["J9U", "LC"]

    def test_nli_form_hits_the_nli_heading(self, founder):
        match = match_cluster(founder, [NLI_HEADING])
        assert match.tier == HEADING
        assert match.text == NLI_HEADING

    def test_the_first_form_to_hit_a_heading_is_reported(self, founder):
        match = match_cluster(founder, [SHORT_HEBREW, NLI_HEADING])
        assert match.tier == HEADING
        assert match.form == NLI_HEADING

    def test_a_tracing_is_the_weaker_tier(self, founder):
        match = match_cluster(founder, [SHORT_HEBREW])
        assert match.tier == VARIANT
        assert match.text == "שניאור זלמן מלאדי."
        assert match.sources == ["LC"]

    def test_a_different_birth_year_is_a_different_person(self, founder):
        assert match_cluster(founder, ["Shneur Zalman, of Lyady, 1830-"]) is (
            None
        )

    def test_a_different_death_year_is_not(self, founder):
        match = match_cluster(founder, ["Shneur Zalman, of Lyady, 1745-1813"])
        assert match.tier == HEADING

    def test_a_subset_of_the_words_is_not_a_match(self):
        """A father's heading sits inside his daughter's."""
        daughter = clusters_of(response([FREIDA]))["4169628484782861008"]
        assert match_cluster(daughter, [NLI_HEADING]) is None
        assert match_cluster(daughter, ["שניאור זלמן"]) is None

    def test_no_match(self, founder):
        assert match_cluster(founder, ["Cohen, David", "", None]) is None


# ---------------------------------------------------------------------------
# Choosing the cluster to store
# ---------------------------------------------------------------------------


class TestChooseCluster:
    def test_one_heading_hit_in_a_catalog_file_is_taken(self):
        choice = choose_cluster(
            result_of(response([PTBNP_SPLIT, SHNEUR_ZALMAN, DOV_BER])),
            [LC_HEADING],
        )
        assert choice.outcome == MATCHED
        assert choice.cluster.viaf_id == SHNEUR_ZALMAN_ID
        assert choice.detail == f'by heading "{LC_HEADING}" (J9U, LC)'

    def test_a_split_cluster_elsewhere_does_not_block(self):
        """PTBNP traces LC's heading to its own copy of the person."""
        choice = choose_cluster(
            result_of(response([PTBNP_SPLIT, SHNEUR_ZALMAN])), [LC_HEADING]
        )
        assert choice.outcome == MATCHED
        tiers = {c.viaf_id: m.tier for c, m in choice.matches}
        assert tiers == {SHNEUR_ZALMAN_ID: HEADING, PTBNP_SPLIT_ID: VARIANT}

    def test_a_catalog_file_tracing_elsewhere_blocks(self):
        """LC saying the string is also someone else is ambiguity."""
        rival = cluster(
            FRADKIN_ID,
            headings=[("Shneʾur Zalman ben Shelomoh, mi-Ladi", ["LC"])],
            source_ids={"LC": "n  85158455"},
            x400s=[x400([("a", "Shneur Zalman, of Lyady")], ["LC"])],
        )
        choice = choose_cluster(
            result_of(response([SHNEUR_ZALMAN, rival])), [LC_HEADING]
        )
        assert choice.outcome == AMBIGUOUS
        assert choice.cluster is None
        assert f"to VIAF {FRADKIN_ID}" in choice.detail

    def test_more_clusters_than_seen_is_incomplete(self):
        choice = choose_cluster(
            result_of(response([COHEN_1949, COHEN_PLAIN], total=390)),
            ["Cohen, David"],
        )
        assert choice.outcome == INCOMPLETE
        assert "390 clusters" in choice.detail
        assert "2 were seen" in choice.detail
        assert len(choice.matches) == 2

    def test_no_hit_count_is_incomplete(self):
        result = VIAFSearchResult("q", None, [], 10)
        assert choose_cluster(result, ["Cohen, David"]).outcome == INCOMPLETE

    def test_two_heading_hits_are_ambiguous(self):
        choice = choose_cluster(
            result_of(response([COHEN_1949, COHEN_PLAIN, COHEN_1955])),
            ["Cohen, David"],
        )
        assert choice.outcome == AMBIGUOUS
        assert f"VIAF {COHEN_1949_ID}" in choice.detail
        assert f"VIAF {COHEN_PLAIN_ID}" in choice.detail

    def test_a_dated_form_still_cannot_rule_out_an_undated_heading(self):
        choice = choose_cluster(
            result_of(response([COHEN_1949, COHEN_PLAIN])),
            ["Cohen, David, 1949-"],
        )
        assert choice.outcome == AMBIGUOUS

    def test_a_dated_form_rules_out_a_differently_dated_heading(self):
        choice = choose_cluster(
            result_of(response([COHEN_1949, COHEN_1955])),
            ["Cohen, David, 1949-"],
        )
        assert choice.outcome == MATCHED
        assert choice.cluster.viaf_id == COHEN_1949_ID

    def test_a_tracing_alone_is_not_taken(self):
        choice = choose_cluster(
            result_of(response([FREIDA, FRADKIN, SHNEUR_ZALMAN, DOV_BER])),
            [SHORT_HEBREW],
        )
        assert choice.outcome == VARIANT_ONLY
        assert choice.cluster is None
        assert [c.viaf_id for c, _ in choice.matches] == [SHNEUR_ZALMAN_ID]
        assert "(LC)" in choice.detail

    def test_a_heading_from_another_file_only_is_not_taken(self):
        choice = choose_cluster(
            result_of(response([HESCHEL_DNB])),
            ["Heschel, Abraham Joshua, 1907-1972"],
        )
        assert choice.outcome == UNSUPPORTED
        assert "J9U, LC" in choice.detail

    def test_nothing_matching_is_no_match(self):
        choice = choose_cluster(
            result_of(response([FREIDA, DOV_BER])), ["Cohen, David"]
        )
        assert choice.outcome == NO_MATCH
        assert choice.matches == []

    def test_an_empty_result_is_no_match(self):
        assert choose_cluster(result_of(EMPTY), [LC_HEADING]).outcome == (
            NO_MATCH
        )


# ---------------------------------------------------------------------------
# Forms worth storing
# ---------------------------------------------------------------------------


class TestStorableForms:
    @pytest.fixture()
    def forms(self):
        founder = clusters_of(response([SHNEUR_ZALMAN]))[SHNEUR_ZALMAN_ID]
        return storable_forms(founder)

    def test_catalog_file_headings_come_first(self, forms):
        assert forms[:2] == [LC_HEADING, NLI_HEADING]

    def test_then_their_tracings_of_two_words_or_more(self, forms):
        assert forms[2:5] == [
            "שניאור זלמן מלאדי",
            "Baʻal ha-Tanya, 1745-1812",
            'אדמו"ר הזקן',
        ]

    def test_tracings_alternate_scripts(self):
        """Alphabetical order would put every Latin tracing first."""
        founder = cluster(
            SHNEUR_ZALMAN_ID,
            headings=[(LC_HEADING, ["LC"])],
            source_ids={"LC": "n  81144085"},
            x400s=[
                x400([("a", "Admor ha-Zaḳen")], ["LC"]),
                x400([("a", "Alter Rebe")], ["LC"]),
                x400([("a", "Baʻal ha-Tanya")], ["LC"]),
                x400([("a", "אדמו״ר הזקן")], ["J9U"]),
                x400([("a", "בעל התניא")], ["J9U"]),
            ],
        )
        c = clusters_of(response([founder]))[SHNEUR_ZALMAN_ID]
        assert storable_forms(c)[1:] == [
            "אדמו״ר הזקן",
            "Admor ha-Zaḳen",
            "בעל התניא",
            "Alter Rebe",
            "Baʻal ha-Tanya",
        ]

    def test_then_other_files_headings(self, forms):
        assert forms[5:] == [
            "שניאור זלמן",
            "Schneur Salman von Ljadi 1745-1812",
        ]

    def test_one_word_tracings_are_left_out(self, forms):
        assert not any(form.startswith("אדמוה״ז") for form in forms)

    def test_other_files_tracings_are_left_out(self, forms):
        assert not any("Šneyʾwr" in form for form in forms)
        assert "העילוי 1745-1813" not in forms

    def test_other_scripts_are_left_out(self, forms):
        assert not any("Шнеур" in form for form in forms)

    def test_one_form_per_set_of_words(self, forms):
        """ISNI's and NLA's spellings of LC's heading add nothing."""
        assert "Shneur Zalman 1745-1813 of Lyady" not in forms
        assert "Shneur Zalman, of Lyady, 1745-1813" not in forms

    def test_marc_punctuation_is_stripped(self, forms):
        assert "שניאור זלמן מלאדי." not in forms
        assert "שניאור זלמן מלאדי" in forms

    def test_romanization_marks_are_latin(self):
        """LC's ayin and alef ride on Latin letters."""
        c = clusters_of(response([DOV_BER]))["45222208"]
        assert "Admor ha-emtsaʻi, 1773-1827" in storable_forms(c)


# ---------------------------------------------------------------------------
# Query building tests
# ---------------------------------------------------------------------------


class TestBuildAuthorQueries:
    def test_hebrew_name_generates_cascade(self):
        queries = _build_author_queries("משה בן מימון")
        assert len(queries) >= 3
        assert "local.personalNames all" in queries[0]
        assert "cql.any all" in queries[1]

    def test_romanized_name_included(self):
        queries = _build_author_queries("משה", name_romanized="Moshe")
        assert any("Moshe" in q for q in queries)

    def test_no_name_returns_empty(self):
        queries = _build_author_queries("")
        assert queries == []

    def test_short_words_skip_and_query(self):
        # Single short word shouldn't produce a multi-word AND query
        queries = _build_author_queries("אב")
        # Should have personalNames and cql.any but not AND query
        for q in queries:
            assert " AND " not in q

    def test_multi_word_and_query(self):
        # Three long Hebrew words should produce an AND query
        name = "משהו בןון מימוןו"
        queries = _build_author_queries(name)
        and_queries = [q for q in queries if " AND " in q]
        assert len(and_queries) == 1


# ---------------------------------------------------------------------------
# VIAFClient tests (mocked HTTP)
# ---------------------------------------------------------------------------


def _resp(text=SAMPLE_VIAF_XML):
    mock_resp = MagicMock()
    mock_resp.text = text
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestVIAFClient:
    def test_default_config(self, monkeypatch):
        monkeypatch.delenv("SRU_REQUEST_DELAY", raising=False)
        client = VIAFClient()
        assert client.base_url == "https://viaf.org/viaf/search"
        assert client.delay == 3

    def test_custom_config(self):
        client = VIAFClient(base_url="http://example.com/viaf", delay=0)
        assert client.base_url == "http://example.com/viaf"
        assert client.delay == 0

    def test_env_config(self, monkeypatch):
        monkeypatch.setenv("SRU_VIAF_URL", "http://env.example.com/viaf")
        monkeypatch.setenv("SRU_REQUEST_DELAY", "1")
        client = VIAFClient()
        assert client.base_url == "http://env.example.com/viaf"
        assert client.delay == 1.0

    @patch("sources.viaf.httpx.get")
    def test_search_returns_xml(self, mock_get):
        mock_get.return_value = _resp()

        client = VIAFClient(delay=0)
        result = client.search('local.personalNames all "test"')
        assert result == SAMPLE_VIAF_XML
        mock_get.assert_called_once()

    @patch("sources.viaf.httpx.get")
    def test_search_returns_none_on_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("connection refused")

        client = VIAFClient(delay=0)
        result = client.search("test query")
        assert result is None

    @patch("sources.viaf.httpx.get")
    def test_search_by_author_returns_clusters(self, mock_get):
        mock_get.return_value = _resp()

        client = VIAFClient(delay=0)
        clusters = client.search_by_author("משה בן מימון")
        assert len(clusters) == 1
        assert clusters[0].viaf_id == "12345678"
        # Should stop after first successful strategy
        assert mock_get.call_count == 1

    @patch("sources.viaf.httpx.get")
    def test_search_by_author_cascades_on_empty(self, mock_get):
        mock_get.side_effect = [_resp(SAMPLE_EMPTY_XML), _resp()]

        client = VIAFClient(delay=0)
        clusters = client.search_by_author(
            "משה בן מימון",
            name_romanized="Moshe ben Maimon",
        )
        assert len(clusters) == 1
        assert mock_get.call_count == 2


class TestSearchAuthorClusters:
    """The cascade's result carries what the choice needs to know."""

    @patch("sources.viaf.httpx.get")
    def test_result_carries_the_hit_count_and_query(self, mock_get):
        mock_get.return_value = _resp(response([COHEN_1949], total=390))

        result = VIAFClient(delay=0).search_author_clusters("Cohen, David")

        assert result.total == 390
        assert result.max_records == 10
        assert not result.complete
        assert result.query == 'local.personalNames all "Cohen, David"'
        assert [c.viaf_id for c in result.clusters] == [COHEN_1949_ID]

    @patch("sources.viaf.httpx.get")
    def test_a_full_page_is_complete(self, mock_get):
        mock_get.return_value = _resp(response([COHEN_1949], total=3))

        result = VIAFClient(delay=0).search_author_clusters("Cohen, David")
        assert result.complete

    @patch("sources.viaf.httpx.get")
    def test_all_strategies_empty_returns_the_first_empty_result(
        self, mock_get
    ):
        mock_get.side_effect = [_resp(SAMPLE_EMPTY_XML)] * 4

        result = VIAFClient(delay=0).search_author_clusters(
            "משה בן מימון", name_romanized="Moshe ben Maimon"
        )

        assert result.clusters == []
        assert result.total == 0
        assert result.query == 'local.personalNames all "משה בן מימון"'
        assert mock_get.call_count == 4

    @patch("sources.viaf.httpx.get")
    def test_a_failure_with_no_hit_is_no_result(self, mock_get):
        """VIAF not answering is not VIAF saying nobody."""
        mock_get.side_effect = [
            httpx.ConnectError("down"),
            _resp(SAMPLE_EMPTY_XML),
        ]

        result = VIAFClient(delay=0).search_author_clusters("Cohen, David")
        assert result is None

    @patch("sources.viaf.httpx.get")
    def test_a_hit_after_a_failure_still_counts(self, mock_get):
        mock_get.side_effect = [httpx.ConnectError("down"), _resp()]

        result = VIAFClient(delay=0).search_author_clusters("Cohen, David")
        assert [c.viaf_id for c in result.clusters] == ["12345678"]

    def test_no_name_is_an_empty_result(self):
        result = VIAFClient(delay=0).search_author_clusters("")
        assert result.clusters == []
        assert result.complete


# ---------------------------------------------------------------------------
# viaf_enrich tests
# ---------------------------------------------------------------------------


class TestViafEnrich:
    @patch("sources.viaf.httpx.get")
    def test_enrich_returns_best_cluster(self, mock_get):
        mock_get.return_value = _resp(SAMPLE_MULTI_CLUSTER_XML)

        client = VIAFClient(delay=0)
        result = viaf_enrich("Good Author", client=client)
        assert result is not None
        # Cluster 22222222 carries the heading, from J9U and LC
        assert result.viaf_id == "22222222"

    @patch("sources.viaf.httpx.get")
    def test_enrich_returns_none_on_no_results(self, mock_get):
        mock_get.return_value = _resp(SAMPLE_EMPTY_XML)

        client = VIAFClient(delay=0)
        result = viaf_enrich("Nobody Real", client=client)
        assert result is None

    @patch("sources.viaf.httpx.get")
    def test_enrich_returns_none_when_ambiguous(self, mock_get):
        mock_get.return_value = _resp(
            response([COHEN_1949, COHEN_PLAIN, COHEN_1955])
        )

        client = VIAFClient(delay=0)
        assert viaf_enrich("Cohen, David", client=client) is None

    @patch("sources.viaf.httpx.get")
    def test_enrich_matches_on_the_romanized_form(self, mock_get):
        mock_get.return_value = _resp(response([PTBNP_SPLIT, SHNEUR_ZALMAN]))

        client = VIAFClient(delay=0)
        result = viaf_enrich(SHORT_HEBREW, "Shneur Zalman, of Lyady", client)
        assert result.viaf_id == SHNEUR_ZALMAN_ID

    def test_enrich_returns_none_for_empty_name(self):
        result = viaf_enrich("")
        assert result is None

    def test_enrich_returns_none_for_no_args(self):
        result = viaf_enrich("", author_name_romanized=None)
        assert result is None


# ---------------------------------------------------------------------------
# Response caching
# ---------------------------------------------------------------------------


class TestVIAFCaching:
    """VIAF answers the same authority query from the cache on a repeat.

    Each test runs against the per-test locmem cache installed by the
    ``tests/conftest.py``, so nothing here depends on test order.
    """

    @patch("sources.viaf.httpx.get")
    def test_second_identical_search_makes_no_request(self, mock_get):
        mock_get.return_value = _resp()
        client = VIAFClient(delay=0)

        first = client.search('local.personalNames all "Maimonides"')
        second = client.search('local.personalNames all "Maimonides"')

        assert mock_get.call_count == 1
        assert first == SAMPLE_VIAF_XML
        assert second == first

    @pytest.mark.disable_socket
    def test_cached_search_succeeds_with_the_network_blocked(self):
        client = VIAFClient(delay=0)
        with patch("sources.viaf.httpx.get", return_value=_resp()) as m:
            client.search('local.personalNames all "blocked"')
            assert m.call_count == 1

        assert client.search('local.personalNames all "blocked"') == (
            SAMPLE_VIAF_XML
        )

    @patch("sources.viaf.time.sleep")
    @patch("sources.viaf.httpx.get")
    def test_cache_hit_skips_the_throttle(self, mock_get, mock_sleep):
        """A hit contacts no server, so it owes the server no wait.

        ``_last_request_time`` is left alone as well, so the next real
        request still waits the full delay measured from the last real
        one.
        """
        mock_get.return_value = _resp()
        client = VIAFClient(delay=100)

        client.search('local.personalNames all "throttled"')
        stamp = client._last_request_time
        client.search('local.personalNames all "throttled"')

        mock_sleep.assert_not_called()
        assert client._last_request_time == stamp

    @patch("sources.viaf.httpx.get")
    def test_different_query_is_a_separate_entry(self, mock_get):
        mock_get.return_value = _resp()
        client = VIAFClient(delay=0)

        client.search('local.personalNames all "one"')
        client.search('local.personalNames all "two"')

        assert mock_get.call_count == 2

    @patch("sources.viaf.httpx.get")
    def test_failure_is_not_cached(self, mock_get):
        """VIAF swallows errors into None; None must not be remembered."""
        mock_get.side_effect = [
            httpx.ConnectError("connection refused"),
            _resp(),
        ]
        client = VIAFClient(delay=0)

        first = client.search('local.personalNames all "flaky"')
        second = client.search('local.personalNames all "flaky"')

        assert first is None
        assert second == SAMPLE_VIAF_XML
        assert mock_get.call_count == 2

    @patch("sources.viaf.httpx.get")
    def test_zero_record_response_is_cached(self, mock_get):
        mock_get.return_value = _resp(SAMPLE_EMPTY_XML)
        client = VIAFClient(delay=0)

        client.search('local.personalNames all "nobody"')
        client.search('local.personalNames all "nobody"')

        assert mock_get.call_count == 1

    @patch("sources.viaf.httpx.get")
    def test_zero_record_response_uses_the_short_ttl(self, mock_get):
        mock_get.return_value = _resp(SAMPLE_EMPTY_XML)
        client = VIAFClient(delay=0)

        with patch.object(ResponseCache, "set", autospec=True) as mock_set:
            client.search('local.personalNames all "nobody"')

        assert mock_set.call_args.kwargs["ttl"] == EMPTY_TTL

    @patch("sources.viaf.httpx.get")
    def test_response_with_records_uses_the_default_ttl(self, mock_get):
        mock_get.return_value = _resp()
        client = VIAFClient(delay=0)

        with patch.object(ResponseCache, "set", autospec=True) as mock_set:
            client.search('local.personalNames all "somebody"')

        assert mock_set.call_args.kwargs["ttl"] == DEFAULT_TTL

    @patch("sources.viaf.httpx.get")
    def test_repeated_author_cascade_replays_from_cache(self, mock_get):
        """The whole author cascade, not just one step, gets reused.

        The first pass misses on the Hebrew heading and matches on the
        romanized name: two requests. The second pass makes none.
        """
        mock_get.side_effect = [_resp(SAMPLE_EMPTY_XML), _resp()]
        client = VIAFClient(delay=0)
        name = "משה בן מימון"

        first = client.search_by_author(
            name, name_romanized="Moshe ben Maimon"
        )
        assert mock_get.call_count == 2

        second = client.search_by_author(
            name, name_romanized="Moshe ben Maimon"
        )

        assert mock_get.call_count == 2
        assert [c.viaf_id for c in second] == [c.viaf_id for c in first]
