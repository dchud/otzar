"""Open Library Covers API client.

Looks up and downloads book cover images using ISBN, OCLC, or LCCN
identifiers. Open Library returns a 1x1 transparent pixel (~43 bytes)
when no cover exists. Since the server doesn't always include
Content-Length, we do a small GET and check the actual response body
size.
"""

import logging
import os
import time
from dataclasses import dataclass

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


@dataclass
class CoverResult:
    """A cover image fetched from a third-party source.

    ``url`` records where the image came from, for attribution and for
    re-fetching. ``content`` is the image bytes already read off the
    wire, so a caller that wants to keep the file does not have to ask
    for it again. Both are empty when no cover was found -- no
    identifier matched, every candidate was Open Library's placeholder,
    or every request failed.
    """

    url: str = ""
    content: bytes = b""

    def __bool__(self):
        return bool(self.url and self.content)


def fetch_cover(record) -> CoverResult:
    """Look up and download a cover image for a catalog record.

    Tries identifiers in order: ISBN, OCLC, LCCN. For each, sends a GET
    request to the Open Library Covers API and checks that the response
    body is a real image (> MIN_COVER_BYTES). Open Library doesn't always
    include Content-Length, so we read the actual body.

    Returns a CoverResult carrying the source URL and the image bytes,
    or an empty (falsy) CoverResult if no cover exists.
    """
    identifiers = {}
    for eid in record.external_identifiers.all():
        identifiers.setdefault(eid.identifier_type, eid.value)

    if not identifiers:
        logger.debug("No external identifiers for record %s", record.record_id)
        return CoverResult()

    base_url = _get_base_url()

    for id_type, url_key in _IDENTIFIER_ORDER:
        value = identifiers.get(id_type)
        if not value:
            continue

        cover_url = f"{base_url}/{url_key}/{value}-M.jpg"
        try:
            response = httpx.get(
                cover_url, timeout=COVER_TIMEOUT, follow_redirects=True
            )
            content = response.content
            body_size = len(content)
            if body_size >= MIN_COVER_BYTES:
                logger.info(
                    "Cover found for record %s via %s=%s (%d bytes)",
                    record.record_id,
                    id_type,
                    value,
                    body_size,
                )
                return CoverResult(url=cover_url, content=content)
            else:
                logger.debug(
                    "Cover too small (%d bytes) for %s=%s, skipping",
                    body_size,
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
    return CoverResult()


def fetch_cover_with_delay(record, delay: float = 0.5) -> CoverResult:
    """Like fetch_cover but with a polite delay before the request.

    Used by the management command to respect rate limits.
    """
    if delay > 0:
        time.sleep(delay)
    return fetch_cover(record)
