"""Tests for sources.cache.ResponseCache."""

import pytest

from sources.cache import ResponseCache, _make_key


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
