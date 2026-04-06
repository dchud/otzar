"""Authority matching for author name resolution against the catalog.

Checks incoming author names against existing Author records using exact,
romanized, and variant name matching strategies.
"""

import re

from catalog.models import Author


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
        for author in Author.objects.filter(name_romanized=name_romanized).exclude(
            pk__in=seen_ids
        ):
            matches.append((author, "romanized"))
            seen_ids.add(author.pk)

    # 3. Variant name match (normalized comparison against variant_names JSON)
    query_norm = normalize_for_comparison(name)
    query_rom_norm = normalize_for_comparison(name_romanized)

    if query_norm or query_rom_norm:
        for author in Author.objects.exclude(pk__in=seen_ids).exclude(variant_names=[]):
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
