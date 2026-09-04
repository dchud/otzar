"""Tests for sources.cache.ResponseCache."""

import pytest

from sources.cache import (
    DEFAULT_TTL,
    EMPTY_TTL,
    ResponseCache,
    _make_key,
    ttl_for_response,
)

_XML_ONE_RECORD = (
    '<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">'
    "<numberOfRecords>1</numberOfRecords>"
    "</searchRetrieveResponse>"
)

_XML_NO_RECORDS = (
    '<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">'
    "<numberOfRecords>0</numberOfRecords><records/>"
    "</searchRetrieveResponse>"
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure a clean cache for every test."""
    rc = ResponseCache()
    rc.clear()
    yield
    rc.clear()


class TestMakeKey:
    """Key generation is deterministic and order-independent."""

    def test_consistent_key(self):
        key1 = _make_key("http://example.com", {"a": "1", "b": "2"})
        key2 = _make_key("http://example.com", {"b": "2", "a": "1"})
        assert key1 == key2

    def test_different_urls_produce_different_keys(self):
        key1 = _make_key("http://example.com", {"q": "x"})
        key2 = _make_key("http://other.com", {"q": "x"})
        assert key1 != key2

    def test_different_params_produce_different_keys(self):
        key1 = _make_key("http://example.com", {"q": "x"})
        key2 = _make_key("http://example.com", {"q": "y"})
        assert key1 != key2


class TestResponseCache:
    """Round-trip, miss, and invalidation behaviour."""

    def test_set_and_get(self):
        rc = ResponseCache()
        rc.set("http://example.com", {"q": "test"}, "<xml>ok</xml>")
        assert rc.get("http://example.com", {"q": "test"}) == "<xml>ok</xml>"

    def test_get_miss_returns_none(self):
        rc = ResponseCache()
        assert rc.get("http://nowhere.example", {"q": "nope"}) is None

    def test_invalidate_removes_entry(self):
        rc = ResponseCache()
        rc.set("http://example.com", {"q": "bye"}, "data")
        rc.invalidate("http://example.com", {"q": "bye"})
        assert rc.get("http://example.com", {"q": "bye"}) is None

    def test_clear_removes_all(self):
        rc = ResponseCache()
        rc.set("http://a.example", {"x": "1"}, "a")
        rc.set("http://b.example", {"x": "2"}, "b")
        rc.clear()
        assert rc.get("http://a.example", {"x": "1"}) is None
        assert rc.get("http://b.example", {"x": "2"}) is None

    def test_custom_ttl_accepted(self):
        """Setting a custom TTL does not raise and the value is retrievable."""
        rc = ResponseCache()
        rc.set("http://example.com", {"q": "ttl"}, "data", ttl=60)
        assert rc.get("http://example.com", {"q": "ttl"}) == "data"


class TestTTLPolicy:
    """A response with no records is cached, but for a shorter time.

    Caching an empty answer for the full 30 days would hide a record
    added to the source catalog tomorrow for a month. Not caching it at
    all would leave the slowest searches -- the ones where every cascade
    step misses -- paying full price on every repeat. A day splits the
    difference.
    """

    def test_response_with_records_gets_the_default_ttl(self):
        assert ttl_for_response(_XML_ONE_RECORD) == DEFAULT_TTL

    def test_response_with_zero_records_gets_the_short_ttl(self):
        assert ttl_for_response(_XML_NO_RECORDS) == EMPTY_TTL

    def test_short_ttl_is_shorter_than_the_default(self):
        assert EMPTY_TTL < DEFAULT_TTL

    def test_namespace_prefixed_element_is_recognized(self):
        """SRU servers vary on whether they prefix the SRW namespace."""
        xml = (
            '<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/'
            'zing/srw/"><srw:numberOfRecords>0</srw:numberOfRecords>'
            "</srw:searchRetrieveResponse>"
        )
        assert ttl_for_response(xml) == EMPTY_TTL

    def test_whitespace_around_the_count_is_tolerated(self):
        xml = "<numberOfRecords> 0 </numberOfRecords>"
        assert ttl_for_response(xml) == EMPTY_TTL

    def test_count_of_ten_is_not_mistaken_for_zero(self):
        xml = "<numberOfRecords>10</numberOfRecords>"
        assert ttl_for_response(xml) == DEFAULT_TTL

    def test_response_without_a_count_gets_the_default_ttl(self):
        """An unrecognized shape is treated as a real answer, not empty."""
        assert ttl_for_response("<somethingElse/>") == DEFAULT_TTL
