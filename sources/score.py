"""Score a catalog candidate against what was read off a title page.

Pure functions with no network, database, or Django state. The cascade
returns each catalog's records in that catalog's own relevance order,
which knows nothing about the photograph; :func:`rank_candidates` puts
the OCR reading to use by ordering the whole list, across catalogs, by
how well each record agrees with it.

A record is scored only on the fields both sides have, so a sparse
record is not punished for what it omits, and a field the two sides
carry in different scripts -- a Hebrew publisher on the page against a
romanized one in an LC record -- is left out rather than counted as a
disagreement. Each field's similarity is the overlap of its normalized
tokens (:func:`sources.normalize.match_tokens`), which suits Hebrew and
romanized forms sitting side by side better than a character ratio
over the whole string would.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from sources.normalize import extract_years, match_tokens, normalize_publisher

# Field weights, in the order the verdicts are reported. The title is
# what the query matched on and what the eye compares first; the author
# tells editions of one work apart; date, publisher and place refine
# from there. They sum to one, but the score is normalized over the
# fields actually compared, so the sum does not matter to it.
WEIGHTS = {
    "title": 0.40,
    "author": 0.25,
    "date": 0.15,
    "publisher": 0.12,
    "place": 0.08,
}

# Share of the score given over to how many fields agreed outright, so
# that of two records agreeing on everything they were compared on, the
# one compared on more comes first. Small enough that it never outranks
# a real difference in any field.
TIEBREAK = 0.05

# A token counts as found in the other side when some token there
# matches it this closely by difflib ratio. Catches a Hebrew prefix
# letter (שערים / השערים, 0.91) and a spelling variant (halakha /
# halakhah, 0.93) while keeping unrelated words apart.
NEAR_TOKEN_RATIO = 0.8

# Verdict thresholds on a field's similarity.
AGREED_AT = 0.8
PARTIAL_AT = 0.4

AGREED = "agreed"
PARTIAL = "partial"
DISAGREED = "disagreed"

# Words that introduce or decorate a name on a title page or in a
# heading and are not part of it: מאת (by), הרב (the rabbi), the
# blessings and honorifics abbreviated with gershayim (זצ"ל, שליט"א,
# reaching here with the marks removed), and their English equivalents
# as they appear in a statement of responsibility.
_AUTHOR_NOISE = frozenset(
    {
        "מאת",
        "מהרב",
        "חיברו",
        "חברו",
        "הרב",
        "רבי",
        "הגאון",
        "הגדול",
        "הרהג",
        "מוהרר",
        "כמוהרר",
        "מוה",
        "זצל",
        "זצוקל",
        "זל",
        "זיעא",
        "שליטא",
        "ני",
        "by",
        "rabbi",
        "rav",
        "dr",
        "prof",
        "ed",
        "eds",
        "edited",
        "editor",
        "translated",
        "translator",
        "compiled",
    }
)

# Generic publishing words, in Hebrew and in the languages of the
# catalogs, that one side carries and the other drops: הוצאת (published
# by), דפוס (press), "Publications". :func:`normalize_publisher` removes
# the legal suffixes; these are the trade words that survive it.
_PUBLISHER_NOISE = frozenset(
    {
        "הוצאת",
        "הוצאה",
        "בהוצאת",
        "הוצ",
        "דפוס",
        "בדפוס",
        "מדפיס",
        "ספרים",
        "ספרי",
        "יוצא",
        "לאור",
        "יל",
        "עי",
        "ושות",
        "publishing",
        "publishers",
        "publisher",
        "publications",
        "publication",
        "press",
        "books",
        "verlag",
        "editions",
        "edition",
        "co",
        "company",
        "house",
        "the",
        "and",
        "of",
    }
)


@dataclass(frozen=True)
class FieldVerdict:
    """How one field compared: its similarity and the verdict on it."""

    field: str
    similarity: float
    verdict: str


@dataclass(frozen=True)
class Match:
    """The score for one candidate and the per-field verdicts behind it.

    ``verdicts`` holds only the fields both sides could be compared on,
    in :data:`WEIGHTS` order. ``score`` is in 0..1; a candidate with
    nothing comparable scores 0 with no verdicts.
    """

    score: float
    verdicts: tuple[FieldVerdict, ...]

    @property
    def agreed(self) -> tuple[str, ...]:
        """Names of the fields that agreed outright."""
        return tuple(v.field for v in self.verdicts if v.verdict == AGREED)

    @property
    def percent(self) -> int:
        """The score as a whole-number percentage, for display."""
        return round(self.score * 100)


# --- Token comparison ---


def _is_hebrew(token: str) -> bool:
    return any("\u0590" <= char <= "\u05ff" for char in token)


def _by_script(tokens: frozenset[str]) -> dict[str, frozenset[str]]:
    """Split tokens into Hebrew and everything else.

    A page reading carries a Hebrew title and a romanized one, and an
    LC record a romanized 245 with the Hebrew in an 880. Only tokens in
    the same script are ever compared, so a record's romanization is
    never held against the Hebrew on the page.
    """
    hebrew = frozenset(token for token in tokens if _is_hebrew(token))
    return {"hebrew": hebrew, "other": tokens - hebrew}


def _without_noise(
    tokens: frozenset[str], noise: frozenset[str]
) -> frozenset[str]:
    """Drop *noise* words, unless that would leave nothing to compare."""
    return (tokens - noise) or tokens


def _containment(inner: frozenset[str], outer: frozenset[str]) -> float:
    """Fraction of *inner* found in *outer*.

    An exact token counts one; a near match by difflib ratio (at least
    :data:`NEAR_TOKEN_RATIO`) counts its ratio; anything else nothing.
    """
    found = 0.0
    for token in inner:
        if token in outer:
            found += 1.0
            continue
        best = max(
            (SequenceMatcher(None, token, other).ratio() for other in outer),
            default=0.0,
        )
        if best >= NEAR_TOKEN_RATIO:
            found += best
    return found / len(inner)


def _overlap(a: frozenset[str], b: frozenset[str]) -> float:
    """Overlap coefficient: how far the smaller side is inside the larger.

    Either side may carry more than the other and still name the same
    thing: a catalog title runs on into the subtitle the page reading
    kept separate, a record abbreviates a name the page spells out,
    "Brooklyn, N.Y." stands for "Brooklyn, New York". Taking the better
    direction means extra words on one side do not count against the
    words the two sides share.
    """
    return max(_containment(a, b), _containment(b, a))


def _agreement(
    page_forms: list[str | None],
    record_forms: list[str | None],
    noise: frozenset[str] = frozenset(),
) -> float | None:
    """Best overlap between any page form and any record form.

    Each side may offer several forms of the same field -- the Hebrew
    and romanized title, the main and added authors -- and agreement in
    any one of them is agreement. Returns None when no pair shares a
    script, which is the "not compared" outcome.
    """
    page_sets = [
        _by_script(_without_noise(tokens, noise))
        for tokens in map(match_tokens, page_forms)
        if tokens
    ]
    record_sets = [
        _by_script(_without_noise(tokens, noise))
        for tokens in map(match_tokens, record_forms)
        if tokens
    ]
    best = None
    for page in page_sets:
        for record in record_sets:
            for script in ("hebrew", "other"):
                a, b = page[script], record[script]
                if a and b:
                    value = _overlap(a, b)
                    best = value if best is None else max(best, value)
    return best


# --- Fields ---


def _title_forms(record: dict) -> list[str]:
    """The record's title in each script, with the part name appended.

    A set record names the photographed volume in 245 $p, outside the
    title proper; appending it lets a page that reads "Sefer Mishpatim"
    agree with the record for the set.
    """
    part = record.get("volume_part_title")
    forms = []
    for key in ("title", "title_alternate"):
        value = record.get(key)
        if value:
            forms.append(f"{value} {part}" if part else value)
    return forms


def _author_forms(record: dict) -> list[str | None]:
    """Every name the record offers, main entry and added entries alike.

    The name on the title page is often the translator's or editor's,
    which the catalog holds in a 700; and where the 700s carry no role,
    the statement of responsibility is the transcription of the page
    itself, so it is compared too.
    """
    return [
        record.get("author"),
        record.get("author_alternate"),
        *(record.get("additional_authors") or []),
        record.get("statement_of_responsibility"),
    ]


def _date_agreement(
    page_value: str | None, record_value: str | None
) -> float | None:
    """Compare the years on each side, allowing a year of slack.

    A record date that spans years ("1994-2003") is a set, and a volume
    printed within the span agrees with it. One year off counts half:
    a Hebrew year straddles two Gregorian ones, so a gematria date read
    off the page and the year the cataloger chose differ by one about
    as often as they agree.
    """
    page = extract_years(page_value)
    record = extract_years(record_value)
    if not page or not record:
        return None
    low, high = min(record), max(record)
    distance = min(
        0 if low <= year <= high else min(abs(year - low), abs(year - high))
        for year in page
    )
    return {0: 1.0, 1: 0.5}.get(distance, 0.0)


def _verdict(similarity: float) -> str:
    if similarity >= AGREED_AT:
        return AGREED
    if similarity >= PARTIAL_AT:
        return PARTIAL
    return DISAGREED


# --- Public API ---


def score_candidate(metadata: dict, record: dict) -> Match:
    """Score one catalog *record* against the title-page *metadata*.

    *metadata* is the OCR reading or the form built from it: ``title``,
    ``title_romanized``, ``author``, ``author_romanized``,
    ``publisher``, ``place``, ``date``, any of which may be missing,
    None, or blank. *record* is a candidate dict as
    :func:`sources.marc.parse_record` builds it.

    The score is the weighted mean of the compared fields' similarities,
    with a :data:`TIEBREAK` share reserved for the count of fields that
    agreed outright, and is 0 when nothing could be compared.
    """
    metadata = metadata or {}
    record = record or {}
    similarities = {
        "title": _agreement(
            [metadata.get("title"), metadata.get("title_romanized")],
            _title_forms(record),
        ),
        "author": _agreement(
            [metadata.get("author"), metadata.get("author_romanized")],
            _author_forms(record),
            _AUTHOR_NOISE,
        ),
        "date": _date_agreement(metadata.get("date"), record.get("date")),
        "publisher": _agreement(
            [normalize_publisher(metadata.get("publisher"))],
            [normalize_publisher(record.get("publisher"))],
            _PUBLISHER_NOISE,
        ),
        "place": _agreement([metadata.get("place")], [record.get("place")]),
    }

    verdicts = []
    for field in WEIGHTS:
        similarity = similarities[field]
        if similarity is not None:
            verdicts.append(
                FieldVerdict(field, similarity, _verdict(similarity))
            )
    if not verdicts:
        return Match(0.0, ())

    weight = sum(WEIGHTS[v.field] for v in verdicts)
    base = sum(WEIGHTS[v.field] * v.similarity for v in verdicts) / weight
    agreed = sum(1 for v in verdicts if v.verdict == AGREED)
    score = (1 - TIEBREAK) * base + TIEBREAK * agreed / len(WEIGHTS)
    return Match(round(score, 4), tuple(verdicts))


def rank_candidates(
    metadata: dict, candidates: list[dict]
) -> list[tuple[dict, Match]]:
    """Pair each candidate with its match, best first.

    The sort is stable, so candidates that score the same keep the
    order they arrived in -- by catalog, then by the catalog's own
    relevance -- and the ordering across catalogs is by score alone.
    """
    scored = [(c, score_candidate(metadata, c)) for c in candidates]
    scored.sort(key=lambda pair: pair[1].score, reverse=True)
    return scored
