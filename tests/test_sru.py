"""Tests for the SRU client module.

All tests use mocked HTTP — no live server requests.
"""

from unittest.mock import patch

import httpx

from sources.sru import (
    SRUClient,
    SRUResult,
    build_sru_params,
    quote_alma_values,
)


# --- CQL query building ---


class TestBuildSRUParams:
    def test_defaults(self):
        params = build_sru_params("alma.title = Talmud")
        assert params["operation"] == "searchRetrieve"
        assert params["version"] == "1.1"
        assert params["query"] == "alma.title = Talmud"
        assert params["maximumRecords"] == "20"
        assert params["recordSchema"] == "marcxml"

    def test_custom_values(self):
        params = build_sru_params(
            "dc.title = test", version="1.2", max_records=5, record_schema="dc"
        )
        assert params["version"] == "1.2"
        assert params["maximumRecords"] == "5"
        assert params["recordSchema"] == "dc"


# --- NLI phrase quoting ---


class TestQuoteAlmaValues:
    def test_simple_value(self):
        result = quote_alma_values("alma.title = Talmud Bavli")
        assert result == 'alma.title = "Talmud Bavli"'

    def test_already_quoted(self):
        result = quote_alma_values('alma.title = "Talmud Bavli"')
        assert result == 'alma.title = "Talmud Bavli"'

    def test_with_boolean(self):
        result = quote_alma_values("alma.title = Talmud Bavli AND alma.creator = Rashi")
        assert 'alma.title = "Talmud Bavli"' in result
        assert 'alma.creator = "Rashi"' in result

    def test_non_alma_index_untouched(self):
        query = "dc.title = Talmud Bavli"
        result = quote_alma_values(query)
        assert result == query

    def test_single_word_value(self):
        result = quote_alma_values("alma.isbn = 9780123456789")
        assert result == 'alma.isbn = "9780123456789"'


# --- SRUClient search ---

FAKE_REQUEST = httpx.Request("GET", "https://example.com/sru")

FAKE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>1</numberOfRecords>
  <records>
    <record>
      <recordData>fake</recordData>
    </record>
  </records>
</searchRetrieveResponse>
"""


class TestSRUClientSearch:
    def _make_client(self, **kwargs):
        defaults = dict(
            base_url="https://example.com/sru",
            request_delay=0,
        )
        defaults.update(kwargs)
        return SRUClient(**defaults)

    @patch("sources.sru.httpx.get")
    def test_successful_search(self, mock_get):
        mock_response = httpx.Response(200, text=FAKE_XML, request=FAKE_REQUEST)
        mock_get.return_value = mock_response

        client = self._make_client()
        result = client.search("dc.title = test")

        assert result.success is True
        assert "<searchRetrieveResponse" in result.data
        assert result.error == ""

        # Verify params were passed correctly.
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["operation"] == "searchRetrieve"

    @patch("sources.sru.httpx.get")
    def test_timeout_returns_error_result(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("timed out")

        client = self._make_client()
        result = client.search("dc.title = test")

        assert result.success is False
        assert "timed out" in result.error.lower()
        assert result.data == ""

    @patch("sources.sru.httpx.get")
    def test_http_status_error(self, mock_get):
        mock_response = httpx.Response(500, text="Internal Server Error")
        mock_get.side_effect = httpx.HTTPStatusError(
            "server error",
            request=httpx.Request("GET", "https://example.com"),
            response=mock_response,
        )

        client = self._make_client()
        result = client.search("dc.title = test")

        assert result.success is False
        assert "500" in result.error

    @patch("sources.sru.httpx.get")
    def test_non_xml_response(self, mock_get):
        mock_response = httpx.Response(
            200, text="this is not xml", request=FAKE_REQUEST
        )
        mock_get.return_value = mock_response

        client = self._make_client()
        result = client.search("dc.title = test")

        assert result.success is False
        assert "xml" in result.error.lower()

    @patch("sources.sru.httpx.get")
    def test_auto_quote_alma(self, mock_get):
        mock_response = httpx.Response(200, text=FAKE_XML, request=FAKE_REQUEST)
        mock_get.return_value = mock_response

        client = self._make_client(auto_quote_alma=True)
        client.search("alma.title = Talmud Bavli")

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["query"] == 'alma.title = "Talmud Bavli"'

    @patch("sources.sru.httpx.get")
    def test_connection_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("connection refused")

        client = self._make_client()
        result = client.search("dc.title = test")

        assert result.success is False
        assert "error" in result.error.lower()


# --- Delay configuration ---


class TestDelayConfig:
    def test_explicit_delay(self):
        client = SRUClient(base_url="https://example.com", request_delay=5.0)
        assert client._get_delay() == 5.0

    def test_env_delay(self):
        client = SRUClient(base_url="https://example.com")
        with patch.dict("os.environ", {"SRU_REQUEST_DELAY": "7"}):
            assert client._get_delay() == 7.0

    def test_default_delay(self):
        client = SRUClient(base_url="https://example.com")
        # Without env var, default is 3.
        assert client._get_delay() == 3.0


# --- Pre-configured instances ---


class TestPreConfiguredClients:
    def test_nli_client_defaults(self):
        from sources.sru import nli_client

        assert "972NNL_INST" in nli_client.base_url
        assert nli_client.auto_quote_alma is True
        assert nli_client.version == "1.2"

    def test_lc_client_defaults(self):
        from sources.sru import lc_client

        assert "LCDB" in lc_client.base_url
        assert lc_client.auto_quote_alma is False

    def test_viaf_client_defaults(self):
        from sources.sru import viaf_client

        assert "viaf.org" in viaf_client.base_url


# --- SRUResult dataclass ---


class TestSRUResult:
    def test_success_result(self):
        r = SRUResult(success=True, data="<xml/>")
        assert r.success is True
        assert r.data == "<xml/>"
        assert r.error == ""

    def test_error_result(self):
        r = SRUResult(success=False, error="boom")
        assert r.success is False
        assert r.data == ""
        assert r.error == "boom"
