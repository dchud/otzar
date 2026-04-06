"""Response caching for external source queries.

Uses Django's cache framework with MD5-hashed keys derived from
the base URL and sorted query parameters, mirroring the approach
in the learn/z3950 SRU client but backed by Django's file-based cache.
"""

import hashlib

from django.core.cache import cache

# Default TTL: 30 days in seconds
DEFAULT_TTL = 30 * 24 * 60 * 60


def _make_key(base_url: str, params: dict) -> str:
    """Generate a cache key from a base URL and query parameters.

    The key is the MD5 hex digest of the base URL joined with
    sorted key=value parameter pairs, separated by pipe characters.
    """
    raw = base_url + "|" + "|".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hashlib.md5(raw.encode()).hexdigest()


class ResponseCache:
    """Thin wrapper around Django's cache framework for HTTP response text."""

    @staticmethod
    def _key(base_url: str, params: dict) -> str:
        return _make_key(base_url, params)

    def get(self, base_url: str, params: dict) -> str | None:
        """Return cached response text, or None on a miss."""
        return cache.get(self._key(base_url, params))

    def set(
        self,
        base_url: str,
        params: dict,
        response_text: str,
        ttl: int | None = None,
    ) -> None:
        """Store response text in the cache.

        *ttl* is the time-to-live in seconds; defaults to 30 days.
        """
        cache.set(self._key(base_url, params), response_text, ttl or DEFAULT_TTL)

    def invalidate(self, base_url: str, params: dict) -> None:
        """Remove a specific entry from the cache."""
        cache.delete(self._key(base_url, params))

    def clear(self) -> None:
        """Remove all entries from the cache."""
        cache.clear()
