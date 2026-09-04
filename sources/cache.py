"""Response caching for external source queries.

Uses Django's cache framework with MD5-hashed keys derived from
the base URL and sorted query parameters, mirroring the approach
in the learn/z3950 SRU client but backed by Django's file-based cache.
"""

import hashlib
import re

from django.core.cache import cache

# Default TTL: 30 days in seconds
DEFAULT_TTL = 30 * 24 * 60 * 60

# TTL for a response the server answered with no records: 1 day.
# See :func:`ttl_for_response`.
EMPTY_TTL = 24 * 60 * 60

# ``numberOfRecords`` is the SRU element carrying the server's hit count.
# Servers differ on whether they prefix the SRW namespace, so the prefix
# is optional here.
_ZERO_RECORDS_RE = re.compile(
    r"<(?:[\w.-]+:)?numberOfRecords>\s*0\s*</", re.IGNORECASE
)


def _reports_no_records(response_text: str) -> bool:
    """Return True if an SRU response reports a hit count of zero."""
    return bool(_ZERO_RECORDS_RE.search(response_text))


def ttl_for_response(response_text: str) -> int:
    """Return how long *response_text* should be cached, in seconds.

    A response listing records is a stable fact about a catalog and gets
    the full 30 days. A response reporting zero records is also a real
    answer, and caching it is what saves the cascade its slowest steps --
    the misses it walks through before a hit. But it is the answer most
    likely to go out of date, because it becomes wrong the moment the
    source catalog gains a matching record. So it is cached for a day
    instead of a month: long enough to cover a cataloguing session and
    the retries within it, short enough that a newly added record shows
    up the next day rather than next month.

    Anything whose shape is not recognized is treated as a real answer.
    """
    return EMPTY_TTL if _reports_no_records(response_text) else DEFAULT_TTL


def _make_key(base_url: str, params: dict) -> str:
    """Generate a cache key from a base URL and query parameters.

    The key is the MD5 hex digest of the base URL joined with
    sorted key=value parameter pairs, separated by pipe characters.
    """
    raw = (
        base_url
        + "|"
        + "|".join(f"{k}={v}" for k, v in sorted(params.items()))
    )
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
        cache.set(
            self._key(base_url, params), response_text, ttl or DEFAULT_TTL
        )

    def invalidate(self, base_url: str, params: dict) -> None:
        """Remove a specific entry from the cache."""
        cache.delete(self._key(base_url, params))

    def clear(self) -> None:
        """Remove all entries from the cache."""
        cache.clear()
