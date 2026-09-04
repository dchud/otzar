"""Normalization of bibliographic values for catalog matching.

Pure string functions with no network or database access. They take a
value as it arrives from OCR or from a MARC field and return the form
used to build a query or to compare against a catalog record.
"""

import re

from catalog.utils import strip_marc_punctuation

# Corporate forms dropped from the end of a publisher name. Catalog
# publisher indexes hold the trade name, so an exact-phrase query that
# carries the legal suffix matches nothing: NLI returns two records for
# `alma.publisher="Mesorah Publications"` and none for
# `alma.publisher="Mesorah Publications, Ltd."`.
#
# The list is deliberately short. "Co." and "Corp." are left out
# because they are usually attached to the name by an ampersand
# ("W. W. Norton & Co."), and removing them leaves a dangling
# conjunction that matches worse than the full string. A single
# trailing period is matched separately, so entries carry no period of
# their own beyond the internal ones.
_CORPORATE_SUFFIXES = (
    "Incorporated",
    "Limited",
    "GmbH",
    "L.L.C",
    "Ltd",
    "LLC",
    "LLP",
    "PLC",
    "Pty",
    "Inc",
    "S.A",
    "N.V",
    "B.V",
)

# A trailing corporate form, with any comma or whitespace introducing
# it and an optional abbreviating period.
_CORPORATE_SUFFIX_RE = re.compile(
    r"[,\s]*\b(?:"
    + "|".join(re.escape(s) for s in _CORPORATE_SUFFIXES)
    + r")\.?\s*$",
    re.IGNORECASE,
)


def normalize_publisher(value: str | None) -> str:
    """Return the trade form of a publisher name.

    Strips trailing MARC display punctuation and trailing corporate
    suffixes (Ltd, Inc, LLC, GmbH and the like), repeating until
    neither applies, so a name carrying both -- "Mesorah Publications,
    Ltd. :" -- reduces to "Mesorah Publications".

    Names with no suffix and no display punctuation are returned
    unchanged, including non-Latin ones. Returns an empty string for
    None, empty, or whitespace-only input, and for a value that is
    nothing but a corporate suffix; callers treat that the same way
    they treat a missing value.
    """
    if not value:
        return ""

    text = strip_marc_punctuation(value)
    while True:
        reduced = strip_marc_punctuation(_CORPORATE_SUFFIX_RE.sub("", text))
        if reduced == text:
            return text
        text = reduced
