"""VIAF (Virtual International Authority File) client for authority lookups.

Searches VIAF via SRU, parses cluster records, and decides which cluster,
if any, is the person an author heading names. A cluster carries the
identifiers the contributing authority files hold for the person -- NLI's
J9U number, LC's LCCN -- and the name forms each of them files the person
under.
"""

import logging
import os
import re
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from itertools import zip_longest

import httpx

from catalog.utils import strip_marc_punctuation
from sources.cache import ResponseCache, ttl_for_response

logger = logging.getLogger(__name__)

# Shared with every client instance; entries are keyed on endpoint plus
# parameters. See the note in sources/sru.py.
_response_cache = ResponseCache()

SRW_NS = "http://www.loc.gov/zing/srw/"
VIAF_NS = "http://viaf.org/viaf/terms#"

DEFAULT_VIAF_URL = "https://viaf.org/viaf/search"
DEFAULT_REQUEST_DELAY = 3

# The authority files this catalog's own headings come from. Records
# arrive from the National Library of Israel, whose authority file VIAF
# labels J9U, and from the Library of Congress. A heading on an Author
# row was issued by one of the two, so the cluster that file put the
# heading in is the person the heading names; a cluster neither file
# contributed to got the same string from somewhere else, and is not.
CATALOG_AUTHORITY_SOURCES = frozenset({"J9U", "LC"})

# Datafield tags under a cluster's x400s that carry a personal name: 400
# is a see-from tracing, 700 an equivalent heading in another file. The
# rest (410 corporate, 411 meeting, 430 title, 451 geographic) name
# something other than the person.
_NAME_TAGS = frozenset({"400", "700"})

# Subfields that are part of the name. Of the others, $5 names the
# institution applying a tracing, $e is a relator term, $t a work title
# and $0 a control number.
_NAME_SUBFIELDS = frozenset({"a", "b", "c", "d", "f", "q"})

# Words a heading's date qualifier is built from, once digits are gone.
_DATE_WORDS = frozenset(
    {"ca", "approximately", "active", "fl", "born", "died"}
)

# Hebrew maqaf joins words the way a hyphen does; split on it.
_MAQAF = "־"

# Tiers of match between a catalog form and a cluster, strongest first.
HEADING = "heading"
VARIANT = "variant"

# Outcomes of choosing a cluster for a set of forms.
MATCHED = "matched"
NO_MATCH = "no_match"
VARIANT_ONLY = "variant_only"
AMBIGUOUS = "ambiguous"
INCOMPLETE = "incomplete"
UNSUPPORTED = "unsupported"


def _has_hebrew(text: str) -> bool:
    """Return True if text contains Hebrew characters."""
    return bool(re.search(r"[֐-׿]", text))


def _normalize(text: str) -> str:
    """Normalize text for comparison: strip punctuation, lowercase."""
    if not text:
        return ""
    return re.sub(r'["\-,.:;/\\\'()|׳״]', "", text).strip().lower()


def _clean(text: str | None) -> str:
    """Drop control and format characters and collapse whitespace.

    Headings arrive carrying the C1 non-sorting delimiters some files
    wrap a leading article in, and right-to-left marks appended to
    Hebrew-script forms. Neither is part of the name.
    """
    if not text:
        return ""
    kept = "".join(
        ch
        for ch in unicodedata.normalize("NFC", text)
        if unicodedata.category(ch) not in ("Cc", "Cf")
    )
    return " ".join(kept.split())


def name_tokens(text: str) -> tuple[str, ...]:
    """Return the words of a heading that name the person, sorted.

    Punctuation, case, word order and dates are what files disagree on
    when they establish the same person: ``Shneur Zalman, of Lyady,
    1745-1812`` at LC, ``Shneur Zalman 1745-1813 of Lyady`` at ISNI,
    ``Shneur Zalman, of Lyady`` at BIBSYS. All of that is set aside. The
    words themselves are kept whole, so ``ben Baruch`` and ``of Lyady``
    stay distinct forms.
    """
    words = _normalize(_clean(text).replace(_MAQAF, " ")).split()
    return tuple(
        sorted(
            word
            for word in words
            if word not in _DATE_WORDS and not any(ch.isdigit() for ch in word)
        )
    )


_BIRTH_YEAR_RE = re.compile(r"(?:\b(d\.?|died)\s*)?(\d{4})", re.IGNORECASE)


def birth_year(text: str) -> str | None:
    """Return the first four-digit year in a heading, unless it is a death.

    Two headings whose words agree and whose birth years differ name two
    people. Death years vary between files for one person (LC has Shneur
    Zalman as 1745-1812, NLA as 1745-1813), so only the birth year is
    compared, and a lone ``d. 1105`` is left out rather than read as one.
    """
    match = _BIRTH_YEAR_RE.search(_clean(text))
    if match is None or match.group(1):
        return None
    return match.group(2)


@dataclass
class VIAFCluster:
    """A single VIAF authority cluster.

    ``main_headings`` and ``x400s`` are lists of ``{"text", "sources"}``
    dicts: the heading or tracing, and the authority files asserting it.
    """

    viaf_id: str
    main_headings: list[dict] = field(default_factory=list)
    source_ids: dict[str, str] = field(default_factory=dict)
    x400s: list[dict] = field(default_factory=list)

    @property
    def variants(self) -> list[str]:
        """The tracings' text alone, for callers that only compare it."""
        return [x400["text"] for x400 in self.x400s]

    @property
    def preferred_heading(self) -> str:
        """The first heading, which VIAF lists from its preferred source."""
        return self.main_headings[0]["text"] if self.main_headings else ""

    def has_source(self, sources) -> bool:
        """Whether any of *sources* contributed to this cluster."""
        return bool(set(self.source_ids) & set(sources))


@dataclass
class VIAFSearchResult:
    """What one query returned: the hit count and the clusters fetched."""

    query: str
    total: int | None
    clusters: list[VIAFCluster]
    max_records: int

    @property
    def complete(self) -> bool:
        """Whether every cluster VIAF holds for the query was fetched."""
        return self.total is not None and self.total <= self.max_records


@dataclass
class ClusterMatch:
    """How a catalog form matched a cluster."""

    tier: str
    form: str
    text: str
    sources: list[str]


@dataclass
class ClusterChoice:
    """The outcome of :func:`choose_cluster`.

    ``matches`` lists every cluster any form matched, with how, whatever
    the outcome, so a caller that could not take one unasked can offer
    them.
    """

    outcome: str
    detail: str
    cluster: VIAFCluster | None = None
    matches: list[tuple[VIAFCluster, ClusterMatch]] = field(
        default_factory=list
    )


class VIAFClient:
    """HTTP client for VIAF SRU searches."""

    def __init__(
        self, base_url: str | None = None, delay: float | None = None
    ):
        self.base_url = base_url or os.environ.get(
            "SRU_VIAF_URL", DEFAULT_VIAF_URL
        )
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
        """Execute an SRU search against VIAF, returning raw XML or None.

        A response already cached for these parameters is returned without
        contacting VIAF, and without waiting out the throttle: the wait is
        owed to VIAF for the load a request puts on it, and a cache hit
        puts none there. ``_last_request_time`` is deliberately left alone
        on a hit, so the next real request still spaces itself against the
        last real one.

        Only successful responses are stored. This method turns every
        failure into ``None``, and ``None`` is never cached, so an outage
        is retried rather than remembered.
        """
        params = {
            "query": query,
            "maximumRecords": str(max_records),
            "recordSchema": "VIAF",
        }
        cached = _response_cache.get(self.base_url, params)
        if cached is not None:
            return cached

        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/xml",
            "User-Agent": "otzar-viaf-client/0.1 (library-catalog; gentle)",
        }
        self._throttle()
        try:
            resp = httpx.get(
                url, headers=headers, follow_redirects=True, timeout=30
            )
            resp.raise_for_status()
            text = resp.text
            self._last_request_time = time.monotonic()
        except Exception:
            logger.exception("VIAF search failed for query: %s", query)
            self._last_request_time = time.monotonic()
            return None

        _response_cache.set(
            self.base_url, params, text, ttl=ttl_for_response(text)
        )
        return text

    def search_author_clusters(
        self,
        name: str,
        name_romanized: str | None = None,
        max_records: int = 10,
    ) -> VIAFSearchResult | None:
        """Search VIAF for an author using a cascade of query strategies.

        Tries in order:
        1. Exact Hebrew heading (if name has Hebrew)
        2. Romanized name in personalNames (if provided)
        3. Broad Hebrew keyword search
        4. Multi-word AND query on longest Hebrew words

        Returns the result of the first strategy that yields clusters.
        When every strategy answers with none, the first strategy's empty
        result is returned. When a strategy fails and none yields
        clusters, ``None`` is returned instead: VIAF not answering is not
        VIAF saying nobody, and a caller must not remember it as one.

        The throttle lives on the client, so a loop over many authors has
        to share one instance; a fresh client waits for nothing before
        its first request.
        """
        empty: VIAFSearchResult | None = None
        failed = False
        for query in _build_author_queries(name, name_romanized):
            logger.debug("VIAF author search: %s", query)
            xml_text = self.search(query, max_records=max_records)
            if xml_text is None:
                failed = True
                continue
            total, clusters = parse_response(xml_text)
            result = VIAFSearchResult(query, total, clusters, max_records)
            if clusters:
                return result
            if empty is None:
                empty = result
        if failed:
            return None
        if empty is None:
            return VIAFSearchResult("", 0, [], max_records)
        return empty

    def search_by_author(
        self,
        name: str,
        name_romanized: str | None = None,
    ) -> list[VIAFCluster]:
        """Return the clusters of :meth:`search_author_clusters`, if any."""
        result = self.search_author_clusters(name, name_romanized)
        return result.clusters if result is not None else []


def _build_author_queries(
    name: str, name_romanized: str | None = None
) -> list[str]:
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


def _parse_root(xml_text: str) -> ET.Element | None:
    """Parse an SRU response, tolerating the HTML VIAF sometimes appends."""
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError:
        end = xml_text.find("</searchRetrieveResponse>")
        if end > 0:
            xml_text = xml_text[: end + len("</searchRetrieveResponse>")]
            try:
                return ET.fromstring(xml_text)
            except ET.ParseError:
                logger.warning(
                    "Failed to parse VIAF XML even after truncation"
                )
                return None
        logger.warning("Failed to parse VIAF XML response")
        return None


def parse_response(xml_text: str) -> tuple[int | None, list[VIAFCluster]]:
    """Parse an SRU response into its hit count and its clusters.

    The count is what VIAF holds for the query, which can exceed the
    clusters returned; ``None`` when the response does not carry one.
    """
    root = _parse_root(xml_text)
    if root is None:
        return None, []

    total: int | None
    try:
        total = int(
            (root.findtext(f"{{{SRW_NS}}}numberOfRecords") or "").strip()
        )
    except ValueError:
        total = None

    clusters = []
    for record_data in root.findall(f".//{{{SRW_NS}}}recordData"):
        for child in record_data:
            if "VIAFCluster" not in child.tag:
                continue
            cluster = _parse_single_cluster(child)
            if cluster:
                clusters.append(cluster)
    return total, clusters


def parse_clusters(xml_text: str) -> list[VIAFCluster]:
    """Parse an SRU XML response into a list of VIAFCluster objects."""
    return parse_response(xml_text)[1]


def parse_record_count(xml_text: str) -> int | None:
    """Return the hit count an SRU response reports, or None."""
    return parse_response(xml_text)[0]


def _sources_of(el: ET.Element) -> list[str]:
    """The authority file codes listed under *el*'s ``sources``."""
    return [
        s.text
        for s in el.findall(f".//{{{VIAF_NS}}}sources/{{{VIAF_NS}}}s")
        if s.text
    ]


def _parse_single_cluster(el: ET.Element) -> VIAFCluster | None:
    """Parse a single VIAFCluster XML element into a VIAFCluster."""
    viaf_id = el.findtext(f"{{{VIAF_NS}}}viafID")
    if not viaf_id:
        return None

    main_headings = []
    for data in el.findall(f".//{{{VIAF_NS}}}mainHeadings/{{{VIAF_NS}}}data"):
        text = _clean(data.findtext(f"{{{VIAF_NS}}}text"))
        if text:
            main_headings.append({"text": text, "sources": _sources_of(data)})

    # Source IDs (format: "PREFIX|ID")
    source_ids: dict[str, str] = {}
    for s in el.findall(f"{{{VIAF_NS}}}sources/{{{VIAF_NS}}}source"):
        if s.text and "|" in s.text:
            prefix, sid = s.text.split("|", 1)
            source_ids[prefix] = sid.strip()

    # Tracings. Each x400 holds a datafield and the files asserting it.
    # A datafield without a tag is read as a personal name; the
    # ``normalized`` key VIAF nests inside it is a derived comparison
    # string, not a heading, and is left alone. A tracing with no
    # letters in it is a broken record, not a name.
    x400s: list[dict] = []
    for x400 in el.findall(f".//{{{VIAF_NS}}}x400s/{{{VIAF_NS}}}x400"):
        sources = _sources_of(x400)
        for df in x400.findall(f"{{{VIAF_NS}}}datafield"):
            if df.get("tag", "400") not in _NAME_TAGS:
                continue
            text = _clean(
                " ".join(
                    sf.text or ""
                    for sf in df.findall(f"{{{VIAF_NS}}}subfield")
                    if sf.get("code", "a") in _NAME_SUBFIELDS
                )
            )
            if not any(ch.isalpha() for ch in text):
                continue
            x400s.append({"text": text, "sources": sources})

    return VIAFCluster(
        viaf_id=viaf_id,
        main_headings=main_headings,
        source_ids=source_ids,
        x400s=x400s,
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


def _same_name(tokens: tuple[str, ...], year: str | None, text: str) -> bool:
    """Whether *text* names the person a form's tokens and year do."""
    if name_tokens(text) != tokens:
        return False
    other = birth_year(text)
    return not (year and other and year != other)


def match_cluster(
    cluster: VIAFCluster, forms: list[str | None]
) -> ClusterMatch | None:
    """Return the strongest way any of *forms* matches *cluster*.

    A form matches at the ``heading`` tier when its words are exactly
    those of a heading some file established for the person, and at the
    ``variant`` tier when they are those of a see-from tracing. Word
    order, punctuation and dates do not count, except that a birth year
    present on both sides has to agree.

    Anything looser -- a form whose words are a subset of a heading's --
    is deliberately not a match. Hebrew headings carry patronymics, so a
    father's full heading sits inside his children's: every word of
    ``שניאור זלמן בן ברוך`` appears in ``פריידא בת שניאור זלמן בן ברוך``.
    """
    keyed = []
    for form in forms:
        if not form:
            continue
        tokens = name_tokens(form)
        if tokens:
            keyed.append((form, tokens, birth_year(form)))

    for form, tokens, year in keyed:
        for heading in cluster.main_headings:
            if _same_name(tokens, year, heading["text"]):
                return ClusterMatch(
                    HEADING, form, heading["text"], heading["sources"]
                )
    for form, tokens, year in keyed:
        for x400 in cluster.x400s:
            if _same_name(tokens, year, x400["text"]):
                return ClusterMatch(
                    VARIANT, form, x400["text"], x400["sources"]
                )
    return None


def _label(sources: list[str]) -> str:
    return ", ".join(sources) if sources else "no source"


def choose_cluster(
    result: VIAFSearchResult, forms: list[str | None]
) -> ClusterChoice:
    """Decide which cluster, if any, is the person *forms* name.

    A VIAF ID on an Author row asserts an identity that everything
    reading the row believes, so a wrong one costs more than none. The
    bar is therefore:

    - Every cluster VIAF holds for the query was seen. Ten of three
      hundred ``Cohen, David`` clusters say nothing about the other two
      hundred and ninety, so the answer is ``incomplete`` rather than a
      guess from the first page.
    - Exactly one cluster matches at the ``heading`` tier. A tracing
      alone is a cross-reference somebody asserted, not the person's
      established name, so a ``variant`` hit on its own is reported
      (``variant_only``) but not taken. Two heading hits are two people,
      or one person VIAF has not merged; either way, ``ambiguous``.
    - One of the files this catalog's headings come from contributed to
      that cluster (``CATALOG_AUTHORITY_SOURCES``). Otherwise the string
      matched by coincidence, or in a split VIAF has not folded into the
      main cluster; ``unsupported``.
    - No other cluster carries a tracing, asserted by one of those same
      files, equal to a form on the row. That is the file itself saying
      the string names someone else too; ``ambiguous``. A tracing from
      any other file does not block: a split cluster at a third library
      listing our heading as a see-from is the common case, not a rival.
    """
    matches = []
    for cluster in result.clusters:
        match = match_cluster(cluster, forms)
        if match is not None:
            matches.append((cluster, match))

    if not result.complete:
        seen = len(result.clusters)
        if result.total is None:
            detail = "VIAF did not report how many clusters the query holds"
        else:
            detail = (
                f"VIAF holds {result.total} clusters for the query and "
                f"{seen} were seen"
            )
        return ClusterChoice(INCOMPLETE, detail, matches=matches)

    if not matches:
        return ClusterChoice(
            NO_MATCH, "no heading or tracing equals a form on the row"
        )

    heading_hits = [(c, m) for c, m in matches if m.tier == HEADING]
    if not heading_hits:
        cluster, match = matches[0]
        detail = (
            f"only a tracing equals a form on the row: VIAF {cluster.viaf_id} "
            f'"{match.text}" ({_label(match.sources)})'
        )
        return ClusterChoice(VARIANT_ONLY, detail, matches=matches)

    if len(heading_hits) > 1:
        ids = ", ".join(f"VIAF {c.viaf_id}" for c, _ in heading_hits)
        return ClusterChoice(
            AMBIGUOUS,
            f"{len(heading_hits)} clusters carry the heading: {ids}",
            matches=matches,
        )

    winner, match = heading_hits[0]
    if not winner.has_source(CATALOG_AUTHORITY_SOURCES):
        detail = (
            f"VIAF {winner.viaf_id} carries the heading but none of "
            f"{_label(sorted(CATALOG_AUTHORITY_SOURCES))} contributed to it"
        )
        return ClusterChoice(UNSUPPORTED, detail, matches=matches)

    for other, other_match in matches:
        if other is winner:
            continue
        asserting = set(other_match.sources) & CATALOG_AUTHORITY_SOURCES
        if asserting:
            detail = (
                f"VIAF {winner.viaf_id} carries the heading but "
                f'{_label(sorted(asserting))} traces "{other_match.text}" '
                f"to VIAF {other.viaf_id}"
            )
            return ClusterChoice(AMBIGUOUS, detail, matches=matches)

    detail = f'by heading "{match.text}" ({_label(match.sources)})'
    return ClusterChoice(MATCHED, detail, cluster=winner, matches=matches)


def _hebrew_or_latin(text: str) -> bool:
    """Whether every letter in *text* is Hebrew or Latin.

    Combining marks and modifier letters -- Hebrew points, the ayin and
    alef of LC romanization -- belong to whatever letter they follow and
    are not judged on their own.
    """
    for ch in text:
        if unicodedata.category(ch) in ("Lu", "Ll", "Lo", "Lt"):
            name = unicodedata.name(ch, "")
            if not name.startswith(("LATIN ", "HEBREW ")):
                return False
    return True


def _alternate_scripts(forms: list[str]) -> list[str]:
    """Interleave Hebrew-script forms with the rest, each side in order.

    VIAF lists tracings alphabetically, which puts every Latin one before
    the first Hebrew one. A cap applied to that order keeps a well
    documented person's romanized epithets and none of the Hebrew forms
    a title page carries.
    """
    hebrew = [form for form in forms if _has_hebrew(form)]
    other = [form for form in forms if not _has_hebrew(form)]
    merged: list[str] = []
    for pair in zip_longest(hebrew, other):
        merged.extend(form for form in pair if form is not None)
    return merged


def storable_forms(cluster: VIAFCluster) -> list[str]:
    """Return the name forms of *cluster* worth keeping on a row, best first.

    Three groups, in order:

    1. Headings established by the files this catalog draws on (see
       ``CATALOG_AUTHORITY_SOURCES``). The next record from either
       catalog carries one of these in its 100, so they are what a later
       match turns on.
    2. See-from tracings those same files hold, when they have at least
       two name words, Hebrew and Latin forms alternating so a cap falls
       on both scripts alike. One-word tracings are surnames and
       honorifics several people share.
    3. Headings established by every other file.

    Tracings from other files are left out. A well-known person has
    hundreds, most of them transliterations into scripts nothing here is
    filed under. Only Hebrew- and Latin-script forms are kept at all, for
    the same reason. Trailing MARC punctuation is stripped, as it is from
    every name a catalog record supplies, and one form is kept per set of
    name words, the first seen.
    """

    def keep(texts):
        forms = (strip_marc_punctuation(text) for text in texts)
        return [form for form in forms if form and _hebrew_or_latin(form)]

    ours = CATALOG_AUTHORITY_SOURCES
    established = keep(
        h["text"] for h in cluster.main_headings if set(h["sources"]) & ours
    )
    tracings = keep(
        x["text"]
        for x in cluster.x400s
        if set(x["sources"]) & ours and len(name_tokens(x["text"])) >= 2
    )
    others = keep(
        h["text"]
        for h in cluster.main_headings
        if not set(h["sources"]) & ours
    )

    seen: set[tuple[str, ...]] = set()

    def unique(candidates):
        kept = []
        for form in candidates:
            key = name_tokens(form)
            if key and key not in seen:
                seen.add(key)
                kept.append(form)
        return kept

    forms = unique(established)
    forms += _alternate_scripts(unique(tracings))
    forms += unique(others)
    return forms


def viaf_enrich(
    author_name: str,
    author_name_romanized: str | None = None,
    client: VIAFClient | None = None,
) -> VIAFCluster | None:
    """Search VIAF for an author and return the one cluster that is them.

    Applies :func:`choose_cluster` to the two forms; returns the cluster
    on a ``matched`` outcome and ``None`` on every other, including VIAF
    not answering.
    """
    if not author_name and not author_name_romanized:
        return None

    if client is None:
        client = VIAFClient()

    result = client.search_author_clusters(author_name, author_name_romanized)
    if result is None:
        return None

    choice = choose_cluster(result, [author_name, author_name_romanized])
    if choice.cluster is not None:
        logger.info(
            "VIAF enrichment match: VIAF %s %s",
            choice.cluster.viaf_id,
            choice.detail,
        )
    else:
        logger.info("VIAF enrichment %s: %s", choice.outcome, choice.detail)
    return choice.cluster
