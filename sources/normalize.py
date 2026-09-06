"""Normalization of bibliographic values for catalog matching.

Pure string functions with no network or database access. They take a
value as it arrives from OCR or from a MARC field and return the form
used to build a query or to compare against a catalog record.
"""

import re
import unicodedata

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


# --- Tokens ---

# Marks that sit inside a word and are removed without splitting it:
# ASCII and typographic apostrophes and quotation marks, and the Hebrew
# geresh and gershayim, which title pages and catalogs write with
# either set. A gershayim marks an abbreviation (רש"י) or a year
# (תשע"ד) and a geresh a foreign sound (סולובייצ'יק); dropping the mark
# keeps the word whole, where splitting on it would leave fragments
# that match nothing on the other side.
_INNER_MARKS = frozenset("'\"‘’“”׳״")

# Character categories dropped after NFKD decomposition: nonspacing
# marks (niqqud, cantillation, the dot under ḥ) and modifier letters
# (the ʻ and ʼ that ALA-LC romanization uses for ayin and alef).
_DROPPED_CATEGORIES = frozenset({"Mn", "Lm"})


def match_tokens(value: str | None) -> frozenset[str]:
    """Return the words of *value* in the form two sources can share.

    Decomposes to NFKD and drops combining marks and modifier letters,
    so pointed Hebrew matches unpointed and "ḥayim" matches "hayim";
    removes apostrophe-like marks inside words; casefolds; and splits
    on everything else, which takes care of MARC display punctuation,
    brackets, the maqaf, and Latin hyphens alike. Tokens of one
    character are dropped: they are initials and abbreviation
    fragments ("N.Y.", "A.Z.") and match nothing useful.

    Returns an empty set for None, empty, or all-punctuation input.
    """
    if not value:
        return frozenset()
    chars = []
    for char in unicodedata.normalize("NFKD", value):
        if char in _INNER_MARKS:
            continue
        if unicodedata.category(char) in _DROPPED_CATEGORIES:
            continue
        chars.append(char if char.isalnum() else " ")
    words = "".join(chars).casefold().split()
    return frozenset(word for word in words if len(word) > 1)


# --- Years ---

# A four-digit Gregorian year, wherever it sits in a catalog date:
# "[1999]", "c1999", "©1999", "1994-2003". The range excludes a Hebrew
# year written in digits ("5759 [1999]").
_GREGORIAN_YEAR_RE = re.compile(r"(?<!\d)(1[4-9]\d\d|20\d\d)(?!\d)")

_HEBREW_LETTERS = "א-ת"
_GEMATRIA_MARKS = "'\"‘’“”׳״"

# A year in gematria: a run of Hebrew letters carrying at least one
# geresh or gershayim (תרמ"ז, ה'תשפ"ה). The mark is what separates a
# year from a word -- שנת, "year", sums to 750 and carries none.
_HEBREW_YEAR_RE = re.compile(
    rf"[{_HEBREW_LETTERS}]+(?:[{_GEMATRIA_MARKS}][{_HEBREW_LETTERS}]*)+"
)

# Final forms count at their base value, as they do in years: תש"ן is
# 5750, not 6450.
_GEMATRIA = {
    "א": 1,
    "ב": 2,
    "ג": 3,
    "ד": 4,
    "ה": 5,
    "ו": 6,
    "ז": 7,
    "ח": 8,
    "ט": 9,
    "י": 10,
    "כ": 20,
    "ך": 20,
    "ל": 30,
    "מ": 40,
    "ם": 40,
    "נ": 50,
    "ן": 50,
    "ס": 60,
    "ע": 70,
    "פ": 80,
    "ף": 80,
    "צ": 90,
    "ץ": 90,
    "ק": 100,
    "ר": 200,
    "ש": 300,
    "ת": 400,
}

# Hebrew printing begins in the 1470s, so no title page carries an
# earlier year; the upper bound leaves room without admitting nonsense.
_HEBREW_YEAR_MIN = 5230
_HEBREW_YEAR_MAX = 6000

# The Hebrew year beginning in the autumn of Gregorian year N runs
# mostly through N+1, and that is the year the catalogs record.
_HEBREW_GREGORIAN_OFFSET = 3760


def hebrew_year_to_gregorian(value: str | None) -> int | None:
    """Return the Gregorian year a gematria year names, or None.

    Reads תרמ"ז as 5647 and returns 1887; ה'תשפ"ה carries its
    thousands and returns 2025. A leading ה with more letters after it
    is always the thousands marker, because the letters of a year run
    from high to low and ה, worth five, could only come last. Without
    the marker the fifth millennium is assumed, as it is on the page.

    The straddle -- the last months of 5647 fall in 1886 -- is left to
    the caller; a date comparison allows a year's slack for it.

    Returns None for anything that is not a year: a word without a
    geresh or gershayim, a sum outside the range of Hebrew printing
    (לפ"ק, the "small count" tag that follows a year, sums to 210), or
    empty input.
    """
    if not value:
        return None
    token = value.strip()
    if not _HEBREW_YEAR_RE.fullmatch(token):
        return None
    letters = [char for char in token if char in _GEMATRIA]
    thousands = 0
    if len(letters) > 1 and letters[0] == "ה":
        thousands = 5000
        letters = letters[1:]
    year = sum(_GEMATRIA[char] for char in letters)
    if thousands:
        year += thousands
    elif year < 1000:
        year += 5000
    if not _HEBREW_YEAR_MIN <= year <= _HEBREW_YEAR_MAX:
        return None
    return year - _HEBREW_GREGORIAN_OFFSET


def extract_years(value: str | None) -> frozenset[int]:
    """Return every year named in *value*, Gregorian and gematria alike.

    A catalog date arrives as "[1999]", "c1999", or "1994-2003", and an
    NLI record may carry the year only as it was printed, "תרמ"ז.";
    a title-page reading may carry either form, or both. Each year
    found is returned once, so "תשע"ד (2014)" is {2014}.

    Returns an empty set when no year can be read.
    """
    if not value:
        return frozenset()
    text = str(value)
    years = {int(match) for match in _GREGORIAN_YEAR_RE.findall(text)}
    for token in _HEBREW_YEAR_RE.findall(text):
        year = hebrew_year_to_gregorian(token)
        if year is not None:
            years.add(year)
    return frozenset(years)
