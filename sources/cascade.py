"""Search cascade engine and ISBN lookup for library catalogs.

Runs progressively broader CQL queries against NLI and LC catalogs,
stopping at the first query that returns results. Cascade definitions
are data structures, not hard-coded logic.
"""

import logging
from dataclasses import dataclass, field

from sources.marc import extract_marc_records, has_hebrew, parse_record
from sources.sru import SRUClient, SRUResult, lc_client, nli_client

logger = logging.getLogger(__name__)

# --- Cascade definitions ---

# Each entry: (step_name, CQL template string).
# Template placeholders: {title}, {place}, {date}, {publisher}, {title_romanized}.
# A step is skipped when any placeholder in its template is missing from metadata.

NLI_CASCADE: list[tuple[str, str]] = [
    (
        "title+place+date",
        'alma.title="{title}" AND alma.publisher_location="{place}" AND alma.main_pub_date={date}',
    ),
    (
        "title+publisher+date",
        'alma.title="{title}" AND alma.publisher="{publisher}" AND alma.main_pub_date={date}',
    ),
    (
        "title+place",
        'alma.title="{title}" AND alma.publisher_location="{place}"',
    ),
    (
        "title+publisher",
        'alma.title="{title}" AND alma.publisher="{publisher}"',
    ),
    (
        "title+date",
        'alma.title="{title}" AND alma.main_pub_date={date}',
    ),
    (
        "keywords+date",
        'alma.all_for_ui="{title}" AND alma.main_pub_date={date}',
    ),
    (
        "title",
        'alma.title="{title}"',
    ),
]

LC_CASCADE: list[tuple[str, str]] = [
    (
        "romanized_title+date",
        'dc.title="{title_romanized}" AND dc.date={date}',
    ),
    (
        "hebrew_title+date",
        'cql.anywhere="{title}" AND dc.date={date}',
    ),
    (
        "romanized_title",
        'dc.title="{title_romanized}"',
    ),
    # The "keywords" step is handled specially: see _build_lc_keyword_query.
    (
        "keywords",
        "__LC_KEYWORDS__",
    ),
]

# Sentinel used to identify the dynamic keyword step.
_LC_KEYWORDS_SENTINEL = "__LC_KEYWORDS__"


# --- Result type ---


@dataclass
class CascadeResult:
    """Result from running a search cascade.

    query_used: The CQL query that produced results (empty if none matched).
    step: Name of the cascade step that matched (empty if none matched).
    records: List of parsed bibliographic dicts from :func:`parse_record`.
    total_hits: Server-reported total hit count for the successful query.
    """

    query_used: str = ""
    step: str = ""
    records: list[dict] = field(default_factory=list)
    total_hits: int = 0


# --- Internal helpers ---


def _extract_template_fields(template: str) -> list[str]:
    """Return placeholder names from a CQL template string."""
    import re

    return re.findall(r"\{(\w+)\}", template)


def _build_lc_keyword_query(metadata: dict) -> str | None:
    """Build a multi-word AND keyword query for LC from the Hebrew title.

    Splits the title into Hebrew words (length > 2), joins them with AND
    via ``cql.anywhere``.  Returns None if fewer than 2 usable words.
    """
    title = metadata.get("title")
    if not title or not has_hebrew(title):
        return None

    words = [w for w in title.split() if len(w) > 2 and has_hebrew(w)]
    if len(words) < 2:
        return None

    return " AND ".join(f'cql.anywhere="{w}"' for w in words)


def _format_query(template: str, metadata: dict) -> str | None:
    """Format a CQL template with metadata values.

    Returns None if any required placeholder is missing or empty in metadata.
    """
    fields = _extract_template_fields(template)
    for f in fields:
        value = metadata.get(f)
        if not value:
            return None
    return template.format(**metadata)


# --- Core engine ---


def run_cascade(
    client: SRUClient,
    cascade: list[tuple[str, str]],
    metadata: dict,
    max_records: int = 20,
) -> CascadeResult:
    """Execute a search cascade against a single catalog.

    Iterates through *cascade* steps in order.  For each step, formats the
    CQL template with *metadata* values, skipping steps where a required
    field is missing.  Stops at the first step that returns at least one
    record.

    Returns a :class:`CascadeResult` with the successful query, step name,
    parsed records, and total hit count.  Returns an empty result if no
    step produces results.
    """
    for step_name, template in cascade:
        # Handle the special LC keyword step.
        if template == _LC_KEYWORDS_SENTINEL:
            query = _build_lc_keyword_query(metadata)
        else:
            query = _format_query(template, metadata)

        if query is None:
            logger.debug("Cascade skip %s: missing fields", step_name)
            continue

        result: SRUResult = client.search(query, max_records=max_records)
        if not result.success:
            logger.warning("Cascade %s failed: %s", step_name, result.error)
            continue

        total_hits, marc_records = extract_marc_records(result.data)
        if marc_records:
            parsed = [parse_record(r) for r in marc_records]
            return CascadeResult(
                query_used=query,
                step=step_name,
                records=parsed,
                total_hits=total_hits,
            )

    return CascadeResult()


# --- Convenience functions ---


def search_nli(metadata: dict, max_records: int = 20) -> CascadeResult:
    """Search the National Library of Israel using the NLI cascade."""
    return run_cascade(nli_client, NLI_CASCADE, metadata, max_records=max_records)


def search_lc(metadata: dict, max_records: int = 20) -> CascadeResult:
    """Search the Library of Congress using the LC cascade."""
    return run_cascade(lc_client, LC_CASCADE, metadata, max_records=max_records)


# --- ISBN lookup ---


def isbn_lookup(isbn: str) -> dict:
    """Look up an ISBN in both NLI and LC catalogs.

    Queries NLI with ``alma.isbn`` and LC with ``bath.isbn``.  Returns a
    dict with ``nli_records`` and ``lc_records``, each a list of parsed
    bibliographic dicts.  If one catalog fails, the other's results are
    still returned.
    """
    nli_records: list[dict] = []
    lc_records: list[dict] = []

    # NLI
    try:
        nli_result = nli_client.search(f"alma.isbn={isbn}")
        if nli_result.success:
            _, marc_records = extract_marc_records(nli_result.data)
            nli_records = [parse_record(r) for r in marc_records]
    except Exception:
        logger.exception("ISBN lookup failed for NLI (isbn=%s)", isbn)

    # LC
    try:
        lc_result = lc_client.search(f"bath.isbn={isbn}")
        if lc_result.success:
            _, marc_records = extract_marc_records(lc_result.data)
            lc_records = [parse_record(r) for r in marc_records]
    except Exception:
        logger.exception("ISBN lookup failed for LC (isbn=%s)", isbn)

    return {
        "nli_records": nli_records,
        "lc_records": lc_records,
    }
