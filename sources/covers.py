"""Open Library Covers API client.

Looks up book cover images using ISBN, OCLC, or LCCN identifiers.
Open Library returns a 1x1 transparent pixel (~43 bytes) when no cover
exists, so we check Content-Length to detect missing covers.
"""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

# Minimum Content-Length to consider a response a real cover image.
# Open Library returns ~43 bytes for its 1x1 transparent pixel placeholder.
MIN_COVER_BYTES = 100

# Timeout for cover lookups (seconds).
COVER_TIMEOUT = 5

# Identifier types to try, in priority order.
_IDENTIFIER_ORDER = [
    ("ISBN", "isbn"),
    ("OCLC", "oclc"),
    ("LCCN", "lccn"),
]


def _get_base_url() -> str:
    return os.environ.get("COVER_API_URL", "https://covers.openlibrary.org/b")


def fetch_cover_url(record) -> str:
    """Look up a cover image URL for a catalog record.

    Tries identifiers in order: ISBN, OCLC, LCCN. For each, sends a HEAD
    request to the Open Library Covers API and checks that the response is
    a real image (Content-Length > MIN_COVER_BYTES).

    Returns the cover URL string if found, or empty string if no cover exists.
    """
    identifiers = {}
    for eid in record.external_identifiers.all():
        identifiers.setdefault(eid.identifier_type, eid.value)

    if not identifiers:
        logger.debug("No external identifiers for record %s", record.record_id)
        return ""

    base_url = _get_base_url()

    for id_type, url_key in _IDENTIFIER_ORDER:
        value = identifiers.get(id_type)
        if not value:
            continue

        cover_url = f"{base_url}/{url_key}/{value}-M.jpg"
        try:
            response = httpx.head(
                cover_url, timeout=COVER_TIMEOUT, follow_redirects=True
            )
            content_length = int(response.headers.get("content-length", "0"))
            if content_length >= MIN_COVER_BYTES:
                logger.info(
                    "Cover found for record %s via %s=%s",
                    record.record_id,
                    id_type,
                    value,
                )
                return cover_url
            else:
                logger.debug(
                    "Cover too small (%d bytes) for %s=%s, skipping",
                    content_length,
                    id_type,
                    value,
                )
        except httpx.TimeoutException:
            logger.warning(
                "Timeout checking cover for %s=%s",
                id_type,
                value,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "HTTP error checking cover for %s=%s: %s",
                id_type,
                value,
                exc,
            )

    logger.debug("No cover found for record %s", record.record_id)
    return ""


def fetch_cover_url_with_delay(record, delay: float = 0.5) -> str:
    """Like fetch_cover_url but with a polite delay before the request.

    Used by the management command to respect rate limits.
    """
    if delay > 0:
        time.sleep(delay)
    return fetch_cover_url(record)
