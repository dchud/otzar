"""Tests for the VIAF client module."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from sources.viaf import (
    VIAFClient,
    _build_author_queries,
    _normalize,
    cluster_matches,
    parse_clusters,
    viaf_enrich,
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
              <text>\u05de\u05e9\u05d4 \u05d1\u05df \u05de\u05d9\u05de\u05d5\u05df</text>
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
              <datafield>
                <subfield>Rambam</subfield>
              </datafield>
              <normalized>rambam</normalized>
            </x400>
            <x400>
              <datafield>
                <subfield>Moses</subfield>
                <subfield>ben Maimon</subfield>
              </datafield>
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
        assert (
            c.main_headings[0]["text"]
            == "\u05de\u05e9\u05d4 \u05d1\u05df \u05de\u05d9\u05de\u05d5\u05df"
        )
        assert "J9U" in c.main_headings[0]["sources"]
        assert "LC" in c.main_headings[0]["sources"]

    def test_parse_source_ids(self):
        clusters = parse_clusters(SAMPLE_VIAF_XML)
        c = clusters[0]
        assert c.source_ids["J9U"] == "987007279341105171"
        assert c.source_ids["LC"] == "n  80032695"

    def test_parse_variants(self):
        clusters = parse_clusters(SAMPLE_VIAF_XML)
        c = clusters[0]
        assert "Rambam" in c.variants
        assert "rambam" in c.variants  # normalized form
        assert "Moses ben Maimon" in c.variants

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
            "\u05de\u05e9\u05d4 \u05d1\u05df \u05de\u05d9\u05de\u05d5\u05df",
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
        assert (
            _normalize("\u05e8\u05de\u05d1\u05f4\u05dd") == "\u05e8\u05de\u05d1\u05dd"
        )


# ---------------------------------------------------------------------------
# Query building tests
# ---------------------------------------------------------------------------


class TestBuildAuthorQueries:
    def test_hebrew_name_generates_cascade(self):
        queries = _build_author_queries(
            "\u05de\u05e9\u05d4 \u05d1\u05df \u05de\u05d9\u05de\u05d5\u05df"
        )
        assert len(queries) >= 3
        assert "local.personalNames all" in queries[0]
        assert "cql.any all" in queries[1]

    def test_romanized_name_included(self):
        queries = _build_author_queries("\u05de\u05e9\u05d4", name_romanized="Moshe")
        assert any("Moshe" in q for q in queries)

    def test_no_name_returns_empty(self):
        queries = _build_author_queries("")
        assert queries == []

    def test_short_words_skip_and_query(self):
        # Single short word shouldn't produce a multi-word AND query
        queries = _build_author_queries("\u05d0\u05d1")
        # Should have personalNames and cql.any but not AND query
        for q in queries:
            assert " AND " not in q

    def test_multi_word_and_query(self):
        # Three long Hebrew words should produce an AND query
        name = "\u05de\u05e9\u05d4\u05d5 \u05d1\u05df\u05d5\u05df \u05de\u05d9\u05de\u05d5\u05df\u05d5"
        queries = _build_author_queries(name)
        and_queries = [q for q in queries if " AND " in q]
        assert len(and_queries) == 1


# ---------------------------------------------------------------------------
# VIAFClient tests (mocked HTTP)
# ---------------------------------------------------------------------------


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
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_VIAF_XML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

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
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_VIAF_XML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = VIAFClient(delay=0)
        clusters = client.search_by_author(
            "\u05de\u05e9\u05d4 \u05d1\u05df \u05de\u05d9\u05de\u05d5\u05df"
        )
        assert len(clusters) == 1
        assert clusters[0].viaf_id == "12345678"
        # Should stop after first successful strategy
        assert mock_get.call_count == 1

    @patch("sources.viaf.httpx.get")
    def test_search_by_author_cascades_on_empty(self, mock_get):
        empty_resp = MagicMock()
        empty_resp.text = SAMPLE_EMPTY_XML
        empty_resp.raise_for_status = MagicMock()

        full_resp = MagicMock()
        full_resp.text = SAMPLE_VIAF_XML
        full_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [empty_resp, full_resp]

        client = VIAFClient(delay=0)
        clusters = client.search_by_author(
            "\u05de\u05e9\u05d4 \u05d1\u05df \u05de\u05d9\u05de\u05d5\u05df",
            name_romanized="Moshe ben Maimon",
        )
        assert len(clusters) == 1
        assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# viaf_enrich tests
# ---------------------------------------------------------------------------


class TestViafEnrich:
    @patch("sources.viaf.httpx.get")
    def test_enrich_returns_best_cluster(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_MULTI_CLUSTER_XML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = VIAFClient(delay=0)
        result = viaf_enrich("Good Author", client=client)
        assert result is not None
        # Cluster 22222222 has J9U + LC + name match => highest score
        assert result.viaf_id == "22222222"

    @patch("sources.viaf.httpx.get")
    def test_enrich_returns_none_on_no_results(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_EMPTY_XML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = VIAFClient(delay=0)
        result = viaf_enrich("Nobody Real", client=client)
        assert result is None

    def test_enrich_returns_none_for_empty_name(self):
        result = viaf_enrich("")
        assert result is None

    def test_enrich_returns_none_for_no_args(self):
        result = viaf_enrich("", author_name_romanized=None)
        assert result is None
