"""Authority matching for author name resolution against the catalog.

Checks incoming author names against existing Author records using exact,
romanized, and variant name matching strategies.
"""

import re
from dataclasses import dataclass, field

from catalog.models import Author
from catalog.utils import strip_marc_punctuation
from sources.marc import has_hebrew
from sources.viaf import (
    CATALOG_AUTHORITY_SOURCES,
    ClusterMatch,
    VIAFClient,
    VIAFCluster,
    choose_cluster,
    storable_forms,
)

# Match types in the order that makes a match trustworthy. An exact or
# romanized hit is a name the catalog already holds in full; a variant
# hit is a cross-reference someone or some source asserted, which is
# worth offering but not worth acting on unasked.
MATCH_PRIORITY = {"exact": 0, "romanized": 1, "variant": 2}
STRONG_MATCH_TYPES = frozenset({"exact", "romanized"})


def normalize_for_comparison(text: str) -> str:
    """Strip punctuation, lowercase, and collapse whitespace for comparison."""
    if not text:
        return ""
    # Remove common punctuation (Latin + Hebrew geresh/gershayim)
    cleaned = re.sub(r'["\-,.:;/\\\'()|\u05F3\u05F4]', "", text)
    return " ".join(cleaned.lower().split())


def find_author_matches(
    name: str, name_romanized: str = ""
) -> list[tuple[Author, str]]:
    """Find existing Authors matching the given name(s).

    Returns a list of (Author, match_type) tuples where match_type is one of:
    - "exact": the Author.name matches exactly
    - "romanized": the Author.name_romanized matches exactly
    - "variant": a normalized variant_names entry matches the normalized query

    Checks are run in priority order; an author appears at most once in the
    results, tagged with its highest-priority match type.
    """
    if not name and not name_romanized:
        return []

    matches: list[tuple[Author, str]] = []
    seen_ids: set[int] = set()

    # 1. Exact name match
    if name:
        for author in Author.objects.filter(name=name):
            if author.pk not in seen_ids:
                matches.append((author, "exact"))
                seen_ids.add(author.pk)

    # 2. Exact romanized match
    if name_romanized:
        for author in Author.objects.filter(
            name_romanized=name_romanized
        ).exclude(pk__in=seen_ids):
            matches.append((author, "romanized"))
            seen_ids.add(author.pk)

    # 3. Variant name match (normalized comparison against variant_names JSON)
    query_norm = normalize_for_comparison(name)
    query_rom_norm = normalize_for_comparison(name_romanized)

    if query_norm or query_rom_norm:
        for author in Author.objects.exclude(pk__in=seen_ids).exclude(
            variant_names=[]
        ):
            for variant in author.variant_names:
                variant_norm = normalize_for_comparison(str(variant))
                if not variant_norm:
                    continue
                if (query_norm and query_norm == variant_norm) or (
                    query_rom_norm and query_rom_norm == variant_norm
                ):
                    matches.append((author, "variant"))
                    seen_ids.add(author.pk)
                    break

    return matches


def candidate_author_forms(candidate: dict) -> tuple[str, str]:
    """Return a candidate's primary and alternate author headings.

    A candidate carries MARC 100 as ``author`` and the 880 linked to it
    as ``author_alternate``: one romanized form and one in the original
    script, in whichever order the source catalog put them. A record
    whose 100 is already in the original script has no 880 and repeats
    itself into the alternate, which is not a second form.

    Both are cleaned with ``strip_marc_punctuation``, the same way the
    names on Author rows were cleaned when those rows were built. The
    matcher compares stored names as exact strings, so a raw heading
    with its trailing MARC punctuation intact misses the row that an
    earlier confirm of the very same catalog record created.
    """
    primary = strip_marc_punctuation(candidate.get("author"))
    alternate = strip_marc_punctuation(candidate.get("author_alternate"))
    if alternate == primary:
        alternate = ""
    return primary, alternate


def find_candidate_author_matches(
    candidate: dict,
) -> list[tuple[Author, str]]:
    """Find existing Authors that may be a candidate's author.

    Either of the candidate's two headings can be the form an existing
    Author was filed under -- the Library of Congress leads with the
    romanized name and the National Library of Israel with the Hebrew --
    so each is checked against both stored forms. An author found twice
    is reported once, under its strongest match, and the strongest
    matches come first.
    """
    primary, alternate = candidate_author_forms(candidate)
    if not primary and not alternate:
        return []

    passes = [(primary, alternate)]
    if alternate:
        passes.append((alternate, primary))

    best: dict[int, tuple[Author, str]] = {}
    for name, name_romanized in passes:
        for author, match_type in find_author_matches(name, name_romanized):
            held = best.get(author.pk)
            if held is None or (
                MATCH_PRIORITY[match_type] < MATCH_PRIORITY[held[1]]
            ):
                best[author.pk] = (author, match_type)

    return sorted(best.values(), key=lambda match: MATCH_PRIORITY[match[1]])


def single_strong_match(
    matches: list[tuple[Author, str]],
) -> Author | None:
    """Return the one Author safe to reuse without being asked.

    One hit on a full stored name is the same person often enough to act
    on. Several hits are a question only a cataloguer can settle, and a
    lone variant hit rests on a cross-reference rather than on the name
    itself, so neither is taken unasked.
    """
    if len(matches) != 1:
        return None
    author, match_type = matches[0]
    return author if match_type in STRONG_MATCH_TYPES else None


def record_author_forms(author: Author, *forms: str) -> list[str]:
    """Keep heading forms on *author* that it does not already carry.

    Filing a book under an author asserts that the headings it arrived
    with name that person, so the row keeps them and the next record
    from the other catalog matches on its own. A romanization of a
    heading in the original script belongs in ``name_romanized``, which
    the browse pages render; anything else is a variant name.

    Returns the names of the fields written, empty when nothing was.
    """
    known = {
        normalize_for_comparison(str(value))
        for value in [
            author.name,
            author.name_romanized,
            *author.variant_names,
        ]
        if value
    }
    variants = list(author.variant_names)
    changed = []

    for form in forms:
        normalized = normalize_for_comparison(form)
        if not normalized or normalized in known:
            continue
        known.add(normalized)
        if (
            not author.name_romanized
            and has_hebrew(author.name)
            and not has_hebrew(form)
        ):
            author.name_romanized = form
            changed.append("name_romanized")
        else:
            variants.append(form)

    if variants != author.variant_names:
        author.variant_names = variants
        changed.append("variant_names")
    if changed:
        author.save(update_fields=changed)
    return changed


def resolve_candidate_author(candidate: dict, choice=None) -> Author | None:
    """Return the Author a candidate's main heading belongs under.

    *choice* is what the confirm page's radio group posted: the id of an
    existing Author to reuse, ``"new"`` to insist on a row of its own,
    or nothing -- the review queue's inline confirm, which has no page
    to ask on. Absent a choice, a single strong match is reused and
    anything less certain gets its own row rather than a silent guess.
    A choice naming an Author that is gone falls back to the same rule.
    """
    primary, alternate = candidate_author_forms(candidate)
    if not primary and not alternate:
        return None

    author = None
    if choice and choice != "new":
        try:
            author = Author.objects.filter(pk=int(choice)).first()
        except (TypeError, ValueError):
            author = None

    if author is None and choice != "new":
        author = single_strong_match(find_candidate_author_matches(candidate))

    if author is None:
        author, _ = Author.objects.get_or_create(name=primary or alternate)

    record_author_forms(author, primary, alternate)
    return author


# ---------------------------------------------------------------------------
# Enrichment from VIAF
# ---------------------------------------------------------------------------

# How many forms one enrichment adds to a row: room for both catalogs'
# established headings and the tracings most likely to be typed at the
# manual-entry form, while the list ``find_author_matches`` walks on
# every row stays short.
VIAF_FORM_LIMIT = 10

# Outcomes of enriching an author, beyond those ``choose_cluster`` has.
LINKED = "linked"
CONFLICT = "conflict"
UNAVAILABLE = "unavailable"


@dataclass
class AuthorEnrichment:
    """What VIAF holds for an Author, and what of it is worth keeping.

    ``outcome`` is ``linked`` when one cluster is the person and its ID
    belongs on the row (or is there already); ``conflict`` when the row
    carries a different ID; ``unavailable`` when VIAF did not answer;
    otherwise one of the ``choose_cluster`` outcomes, with ``matches``
    listing what did match so a caller can offer it. ``forms`` are the
    name forms to record, best first, already reduced to those the row
    lacks. ``also_linked`` are other rows carrying the same VIAF ID: the
    same person filed twice.
    """

    author: Author
    outcome: str
    detail: str = ""
    cluster: VIAFCluster | None = None
    matches: list[tuple[VIAFCluster, ClusterMatch]] = field(
        default_factory=list
    )
    forms: list[str] = field(default_factory=list)
    also_linked: list[Author] = field(default_factory=list)

    @property
    def viaf_id(self) -> str:
        return self.cluster.viaf_id if self.cluster is not None else ""

    @property
    def source_ids(self) -> dict[str, str]:
        """The cluster's identifiers in the files this catalog draws on."""
        if self.cluster is None:
            return {}
        return {
            code: value
            for code, value in self.cluster.source_ids.items()
            if code in CATALOG_AUTHORITY_SOURCES
        }


def author_forms(author: Author) -> list[str]:
    """Every name form the row holds: name, romanization, variants."""
    return [
        str(form)
        for form in [author.name, author.name_romanized, *author.variant_names]
        if form
    ]


def enrich_author_from_viaf(
    author: Author, client: VIAFClient | None = None
) -> AuthorEnrichment:
    """Look *author* up in VIAF and return what it holds for them.

    Nothing is written; :func:`apply_author_enrichment` does that. The
    row's name and romanization drive the search, and every form on the
    row is matched against what comes back, under the bar
    ``choose_cluster`` sets. A row holding both the Hebrew heading and
    the romanized one is matched on each against the heading in its own
    script, which is how one person established in two files is
    recognized across them.

    Where this runs from. Not the confirm path: the first lookup of a
    new author is one to four VIAF requests, each spaced by the client's
    delay, and only a repeat is answered from the cache, so it would
    hold the user's request for that long. The ``enrich_authors``
    management command is the caller, run by hand or on a schedule over
    the rows without a VIAF ID. The point a confirm could hand off from
    is right after ``resolve_candidate_author`` creates a row, through a
    task backend that runs outside the request; Django's built-in
    immediate backend runs a task inside it, which costs the same as
    calling directly.

    A caller looping over authors passes one *client* for the whole
    loop, because the wait between requests lives on the instance.
    """
    if client is None:
        client = VIAFClient()

    result = client.search_author_clusters(
        author.name, author.name_romanized or None
    )
    if result is None:
        return AuthorEnrichment(author, UNAVAILABLE, "VIAF did not answer")

    choice = choose_cluster(result, author_forms(author))
    if choice.cluster is None:
        return AuthorEnrichment(
            author, choice.outcome, choice.detail, matches=choice.matches
        )

    cluster = choice.cluster
    if author.viaf_id and author.viaf_id != cluster.viaf_id:
        detail = (
            f"row carries VIAF {author.viaf_id}; the search found "
            f"VIAF {cluster.viaf_id} {choice.detail}"
        )
        return AuthorEnrichment(
            author, CONFLICT, detail, cluster, choice.matches
        )

    known = {normalize_for_comparison(form) for form in author_forms(author)}
    forms: list[str] = []
    for form in storable_forms(cluster):
        key = normalize_for_comparison(form)
        if key in known:
            continue
        known.add(key)
        forms.append(form)
        if len(forms) == VIAF_FORM_LIMIT:
            break

    also_linked = list(
        Author.objects.filter(viaf_id=cluster.viaf_id).exclude(pk=author.pk)
    )
    return AuthorEnrichment(
        author,
        LINKED,
        choice.detail,
        cluster,
        choice.matches,
        forms,
        also_linked,
    )


def apply_author_enrichment(enrichment: AuthorEnrichment) -> list[str]:
    """Write a ``linked`` enrichment onto its row; return the fields written.

    Sets ``viaf_id`` when the row has none and records the forms through
    ``record_author_forms``, which files a romanization of a Hebrew name
    in ``name_romanized`` and everything else in ``variant_names``. Any
    other outcome writes nothing.
    """
    if enrichment.outcome != LINKED:
        return []
    author = enrichment.author
    changed: list[str] = []
    if not author.viaf_id:
        author.viaf_id = enrichment.viaf_id
        author.save(update_fields=["viaf_id"])
        changed.append("viaf_id")
    changed.extend(record_author_forms(author, *enrichment.forms))
    return changed
