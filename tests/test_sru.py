"""Tests for the SRU client module.

All tests use mocked HTTP — no live server requests.
"""

import os
from unittest.mock import patch

import httpx
import pytest

from sources.cache import DEFAULT_TTL, EMPTY_TTL, ResponseCache
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
        result = quote_alma_values(
            "alma.title = Talmud Bavli AND alma.creator = Rashi"
        )
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
        mock_response = httpx.Response(
            200, text=FAKE_XML, request=FAKE_REQUEST
        )
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
        mock_response = httpx.Response(
            200, text=FAKE_XML, request=FAKE_REQUEST
        )
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
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("SRU_REQUEST_DELAY", None)
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

    def test_dnb_client_defaults(self):
        from sources.sru import dnb_client

        assert "services.dnb.de" in dnb_client.base_url
        assert dnb_client.auto_quote_alma is False
        assert dnb_client.version == "1.1"

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


# --- Response caching ---

FAKE_EMPTY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>0</numberOfRecords>
  <records/>
</searchRetrieveResponse>
"""


def _ok(text=FAKE_XML):
    return httpx.Response(200, text=text, request=FAKE_REQUEST)


class TestSearchCaching:
    """A repeated identical search is answered from the cache.

    The cache sits inside ``search``, below the cascade, so the cascade
    needs no knowledge of it. Every test here runs against the per-test
    locmem cache installed by the root ``conftest.py``.
    """

    def _make_client(self, **kwargs):
        defaults = dict(base_url="https://example.com/sru", request_delay=0)
        defaults.update(kwargs)
        return SRUClient(**defaults)

    @patch("sources.sru.httpx.get")
    def test_second_identical_search_makes_no_request(self, mock_get):
        mock_get.return_value = _ok()
        client = self._make_client()

        first = client.search("dc.title = test")
        second = client.search("dc.title = test")

        assert mock_get.call_count == 1
        assert first.success is True
        assert second.success is True
        assert second.data == first.data

    @pytest.mark.disable_socket
    def test_cached_search_succeeds_with_the_network_blocked(self):
        """The second call could not reach the network even if it tried.

        The mock is out of scope by then, so anything other than a cache
        hit would open a real connection and pytest-socket would raise.
        """
        client = self._make_client()
        with patch("sources.sru.httpx.get", return_value=_ok()) as mock_get:
            client.search("dc.title = blocked")
            assert mock_get.call_count == 1

        result = client.search("dc.title = blocked")

        assert result.success is True
        assert "<searchRetrieveResponse" in result.data

    @patch("sources.sru.time.sleep")
    @patch("sources.sru.httpx.get")
    def test_cache_hit_skips_the_polite_delay(self, mock_get, mock_sleep):
        """The delay is politeness to the server; a hit contacts no server.

        This is where nearly all of the saved time is: the delay defaults
        to three seconds and the request itself is far quicker.
        """
        mock_get.return_value = _ok()
        client = self._make_client(request_delay=3)

        client.search("dc.title = polite")
        client.search("dc.title = polite")

        mock_sleep.assert_called_once_with(3)

    @patch("sources.sru.httpx.get")
    def test_different_query_is_a_separate_entry(self, mock_get):
        mock_get.return_value = _ok()
        client = self._make_client()

        client.search("dc.title = one")
        client.search("dc.title = two")

        assert mock_get.call_count == 2

    @patch("sources.sru.httpx.get")
    def test_different_max_records_is_a_separate_entry(self, mock_get):
        """The key covers every request parameter, not just the query."""
        mock_get.return_value = _ok()
        client = self._make_client()

        client.search("dc.title = same", max_records=5)
        client.search("dc.title = same", max_records=20)

        assert mock_get.call_count == 2

    @patch("sources.sru.httpx.get")
    def test_different_endpoints_do_not_share_entries(self, mock_get):
        mock_get.return_value = _ok()
        nli = self._make_client(base_url="https://nli.example/sru")
        lc = self._make_client(base_url="https://lc.example/sru")

        nli.search("dc.title = shared")
        lc.search("dc.title = shared")

        assert mock_get.call_count == 2

    @patch("sources.sru.httpx.get")
    def test_timeout_is_not_cached(self, mock_get):
        """A transient outage must not be remembered for thirty days."""
        mock_get.side_effect = [httpx.TimeoutException("timed out"), _ok()]
        client = self._make_client()

        first = client.search("dc.title = flaky")
        second = client.search("dc.title = flaky")

        assert first.success is False
        assert second.success is True
        assert mock_get.call_count == 2

    @patch("sources.sru.httpx.get")
    def test_http_error_is_not_cached(self, mock_get):
        mock_get.side_effect = [
            httpx.HTTPStatusError(
                "server error",
                request=FAKE_REQUEST,
                response=httpx.Response(503, text="unavailable"),
            ),
            _ok(),
        ]
        client = self._make_client()

        assert client.search("dc.title = down").success is False
        assert client.search("dc.title = down").success is True
        assert mock_get.call_count == 2

    @patch("sources.sru.httpx.get")
    def test_non_xml_response_is_not_cached(self, mock_get):
        """A proxy error page is a failure, not an answer worth keeping."""
        mock_get.side_effect = [
            httpx.Response(200, text="not xml at all", request=FAKE_REQUEST),
            _ok(),
        ]
        client = self._make_client()

        assert client.search("dc.title = html").success is False
        assert client.search("dc.title = html").success is True
        assert mock_get.call_count == 2

    @patch("sources.sru.httpx.get")
    def test_zero_record_response_is_cached(self, mock_get):
        """Misses are what make the cascade slow, so they get cached too."""
        mock_get.return_value = _ok(FAKE_EMPTY_XML)
        client = self._make_client()

        first = client.search("dc.title = nothing")
        second = client.search("dc.title = nothing")

        assert mock_get.call_count == 1
        assert first.success is True
        assert second.data == first.data

    @patch("sources.sru.httpx.get")
    def test_zero_record_response_uses_the_short_ttl(self, mock_get):
        mock_get.return_value = _ok(FAKE_EMPTY_XML)
        client = self._make_client()

        with patch.object(ResponseCache, "set", autospec=True) as mock_set:
            client.search("dc.title = nothing")

        assert mock_set.call_args.kwargs["ttl"] == EMPTY_TTL

    @patch("sources.sru.httpx.get")
    def test_response_with_records_uses_the_default_ttl(self, mock_get):
        mock_get.return_value = _ok()
        client = self._make_client()

        with patch.object(ResponseCache, "set", autospec=True) as mock_set:
            client.search("dc.title = something")

        assert mock_set.call_args.kwargs["ttl"] == DEFAULT_TTL

    @patch("sources.sru.httpx.get")
    def test_alma_quoting_happens_before_the_key_is_built(self, mock_get):
        """Quoted and unquoted forms of one query are the same search."""
        mock_get.return_value = _ok()
        client = self._make_client(auto_quote_alma=True)

        client.search("alma.title = Talmud Bavli")
        client.search('alma.title = "Talmud Bavli"')

        assert mock_get.call_count == 1
