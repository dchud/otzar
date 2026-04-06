"""VIAF (Virtual International Authority File) client for authority lookups.

Searches VIAF via SRU, parses cluster records, and provides enrichment
for author name resolution with source IDs (J9U/NLI, LC/LCCN).
"""

import logging
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

SRW_NS = "http://www.loc.gov/zing/srw/"
VIAF_NS = "http://viaf.org/viaf/terms#"

DEFAULT_VIAF_URL = "https://viaf.org/viaf/search"
DEFAULT_REQUEST_DELAY = 3


def _has_hebrew(text: str) -> bool:
    """Return True if text contains Hebrew characters."""
    return bool(re.search(r"[\u0590-\u05FF]", text))


def _normalize(text: str) -> str:
    """Normalize text for comparison: strip punctuation, lowercase."""
    if not text:
        return ""
    return re.sub(r'["\-,.:;/\\\'()|\u05F3\u05F4]', "", text).strip().lower()


@dataclass
class VIAFCluster:
    """A single VIAF authority cluster."""

    viaf_id: str
    main_headings: list[dict] = field(default_factory=list)
    source_ids: dict[str, str] = field(default_factory=dict)
    variants: list[str] = field(default_factory=list)


class VIAFClient:
    """HTTP client for VIAF SRU searches."""

    def __init__(self, base_url: str | None = None, delay: float | None = None):
        self.base_url = base_url or os.environ.get("SRU_VIAF_URL", DEFAULT_VIAF_URL)
        if delay is not None:
            self.delay = delay
        else:
            try:
                self.delay = float(
                    os.environ.get("SRU_REQUEST_DELAY", DEFAULT_REQUEST_DELAY)
                )
            except (TypeError, ValueError):
                self.delay = DEFAULT_REQUEST_DELAY
        self._last_request_time: float = 0.0

    def _throttle(self) -> None:
        """Wait if needed to respect the request delay."""
        if self._last_request_time > 0:
            elapsed = time.monotonic() - self._last_request_time
            remaining = self.delay - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def search(self, query: str, max_records: int = 10) -> str | None:
        """Execute an SRU search against VIAF, returning raw XML or None."""
        params = {
            "query": query,
            "maximumRecords": str(max_records),
            "recordSchema": "VIAF",
        }
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/xml",
            "User-Agent": "otzar-viaf-client/0.1 (library-catalog; gentle)",
        }
        self._throttle()
        try:
            resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            self._last_request_time = time.monotonic()
            return resp.text
        except Exception:
            logger.exception("VIAF search failed for query: %s", query)
            self._last_request_time = time.monotonic()
            return None

    def search_by_author(
        self,
        name: str,
        name_romanized: str | None = None,
    ) -> list[VIAFCluster]:
        """Search VIAF for an author using a cascade of query strategies.

        Tries in order:
        1. Exact Hebrew heading (if name has Hebrew)
        2. Romanized name in personalNames (if provided)
        3. Broad Hebrew keyword search
        4. Multi-word AND query on longest Hebrew words

        Returns parsed clusters from the first strategy that yields results.
        """
        queries = _build_author_queries(name, name_romanized)
        for query in queries:
            logger.debug("VIAF author search: %s", query)
            xml_text = self.search(query, max_records=10)
            if xml_text is None:
                continue
            clusters = parse_clusters(xml_text)
            if clusters:
                return clusters
        return []


def _build_author_queries(name: str, name_romanized: str | None = None) -> list[str]:
    """Build a cascade of SRU queries for author name search."""
    queries = []

    # Strategy 1: exact Hebrew heading
    if name and _has_hebrew(name):
        queries.append(f'local.personalNames all "{name}"')

    # Strategy 2: romanized name
    if name_romanized:
        queries.append(f'local.personalNames all "{name_romanized}"')

    # Strategy 2b: non-Hebrew name in personalNames (Latin script)
    if name and not _has_hebrew(name) and not name_romanized:
        queries.append(f'local.personalNames all "{name}"')

    # Strategy 3: broad keyword (Hebrew)
    if name and _has_hebrew(name):
        queries.append(f'cql.any all "{name}"')

    # Strategy 3b: broad keyword (non-Hebrew)
    if name and not _has_hebrew(name):
        queries.append(f'cql.any all "{name}"')

    # Strategy 4: multi-word AND on longest Hebrew words
    if name and _has_hebrew(name):
        words = [w for w in name.split() if len(w) > 2 and _has_hebrew(w)]
        if len(words) >= 2:
            words.sort(key=len, reverse=True)
            word_query = " AND ".join(f'cql.any all "{w}"' for w in words[:3])
            queries.append(word_query)

    return queries


def parse_clusters(xml_text: str) -> list[VIAFCluster]:
    """Parse an SRU XML response into a list of VIAFCluster objects."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # VIAF sometimes appends HTML after XML
        end = xml_text.find("</searchRetrieveResponse>")
        if end > 0:
            xml_text = xml_text[: end + len("</searchRetrieveResponse>")]
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError:
                logger.warning("Failed to parse VIAF XML even after truncation")
                return []
        else:
            logger.warning("Failed to parse VIAF XML response")
            return []

    clusters = []
    for record_data in root.findall(f".//{{{SRW_NS}}}recordData"):
        for child in record_data:
            if "VIAFCluster" not in child.tag:
                continue
            cluster = _parse_single_cluster(child)
            if cluster:
                clusters.append(cluster)
    return clusters


def _parse_single_cluster(el: ET.Element) -> VIAFCluster | None:
    """Parse a single VIAFCluster XML element into a VIAFCluster."""
    viaf_id = el.findtext(f"{{{VIAF_NS}}}viafID")
    if not viaf_id:
        return None

    # Main headings
    main_headings = []
    for data in el.findall(f".//{{{VIAF_NS}}}mainHeadings/{{{VIAF_NS}}}data"):
        text = data.findtext(f"{{{VIAF_NS}}}text")
        if text:
            heading_sources = [
                s.text
                for s in data.findall(f".//{{{VIAF_NS}}}sources/{{{VIAF_NS}}}s")
                if s.text
            ]
            main_headings.append({"text": text, "sources": heading_sources})

    # Source IDs (format: "PREFIX|ID")
    source_ids: dict[str, str] = {}
    for s in el.findall(f"{{{VIAF_NS}}}sources/{{{VIAF_NS}}}source"):
        if s.text and "|" in s.text:
            prefix, sid = s.text.split("|", 1)
            source_ids[prefix] = sid.strip()

    # Variant headings (x400s)
    variants: list[str] = []
    for x400 in el.findall(f".//{{{VIAF_NS}}}x400s/{{{VIAF_NS}}}x400"):
        for df in x400.findall(f"{{{VIAF_NS}}}datafield"):
            subfields = []
            for sf in df.findall(f"{{{VIAF_NS}}}subfield"):
                subfields.append(sf.text or "")
            if subfields:
                variants.append(" ".join(subfields))
        normalized = x400.findtext(f".//{{{VIAF_NS}}}normalized")
        if normalized:
            variants.append(normalized)

    return VIAFCluster(
        viaf_id=viaf_id,
        main_headings=main_headings,
        source_ids=source_ids,
        variants=variants[:20],
    )


def cluster_matches(cluster: VIAFCluster, query_text: str) -> bool:
    """Check if a cluster matches a query by comparing headings and variants.

    Performs normalized (punctuation-stripped, case-insensitive) comparison.
    Returns True if the query text appears in any heading or variant, or if
    all significant words of the query appear in any single text field.
    """
    query_norm = _normalize(query_text)
    if not query_norm:
        return False

    all_texts: list[str] = []
    for h in cluster.main_headings:
        all_texts.append(h["text"])
    all_texts.extend(cluster.variants)

    for text in all_texts:
        t = _normalize(text)
        if not t:
            continue
        # Substring match in either direction
        if query_norm in t or t in query_norm:
            return True
        # All significant words present
        words = [w for w in query_norm.split() if len(w) > 1]
        if len(words) >= 2 and all(w in t for w in words):
            return True

    return False


def viaf_enrich(
    author_name: str,
    author_name_romanized: str | None = None,
    client: VIAFClient | None = None,
) -> VIAFCluster | None:
    """Search VIAF for an author and return the best matching cluster.

    Scores clusters by:
    - Presence of J9U (NLI) source ID (+2)
    - Presence of LC source ID (+2)
    - Author name appears in a heading (+5)

    Returns the best cluster if its score >= 2, otherwise None.
    """
    if not author_name and not author_name_romanized:
        return None

    if client is None:
        client = VIAFClient()

    clusters = client.search_by_author(author_name, author_name_romanized)
    if not clusters:
        return None

    best: VIAFCluster | None = None
    best_score = -1

    for cluster in clusters:
        score = 0
        if cluster.source_ids.get("J9U"):
            score += 2
        if cluster.source_ids.get("LC"):
            score += 2

        # Check if author name appears in any heading
        for heading in cluster.main_headings:
            heading_text = heading.get("text", "")
            if author_name and author_name in heading_text:
                score += 5
                break
            if (
                author_name_romanized
                and author_name_romanized.lower() in heading_text.lower()
            ):
                score += 5
                break

        if score > best_score:
            best_score = score
            best = cluster

    if best is not None and best_score >= 2:
        logger.info(
            "VIAF enrichment match: VIAF %s (score=%d)", best.viaf_id, best_score
        )
        return best

    return None
