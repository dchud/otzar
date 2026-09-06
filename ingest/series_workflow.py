"""Series detection and volume management workflow.

Provides helpers for identifying series information in parsed MARC data,
matching against existing Series records, and creating SeriesVolume entries
(including gap placeholders for volumes not yet held).

Volume designations are normalized to Arabic digits so that records
writing the same volume differently can be matched to each other.
"""

import logging
import re

from catalog.models import Record, Series, SeriesVolume
from catalog.utils import strip_marc_punctuation
from ingest.authority import normalize_for_comparison

logger = logging.getLogger(__name__)


def detect_series_from_marc(parsed_record: dict) -> dict | None:
    """Check parsed MARC data for series information.

    Expects the dict returned by ``sources.marc.parse_record``, which
    populates ``series_title`` and ``series_volume``.

    Returns a dict with ``series_title`` and ``series_volume`` keys, or
    None if no series information is present.
    """
    series_title = (parsed_record.get("series_title") or "").strip()
    series_volume = (parsed_record.get("series_volume") or "").strip()

    if not series_title:
        return None

    return {
        "series_title": series_title,
        "series_volume": series_volume,
    }


def find_matching_series(series_title: str) -> Series | None:
    """Find an existing Series matching *series_title*.

    Tries an exact title match first, then falls back to a normalized
    comparison across all Series records.
    """
    if not series_title:
        return None

    # Exact match
    exact = Series.objects.filter(title=series_title).first()
    if exact:
        return exact

    # Normalized comparison
    title_norm = normalize_for_comparison(series_title)
    for series in Series.objects.all():
        if normalize_for_comparison(series.title) == title_norm:
            return series

    return None


# Words that introduce a volume number rather than being part of it.
_VOLUME_PREFIXES = (
    "volume",
    "vol",
    "v",
    "part",
    "pt",
    "number",
    "num",
    "no",
    "חלק",
    "ספר",
    "כרך",
    "כתב",
    "מהדורה",
)

# A prefix counts only when a separator or a digit follows it, so the
# Roman numeral "VI" is read as six rather than as "v" plus "i".
_PREFIX_RE = re.compile(
    r"^(?:" + "|".join(_VOLUME_PREFIXES) + r")(?:\.\s*|\s+|(?=\d))",
    re.IGNORECASE,
)

_DIGITS_RE = re.compile(r"\d+")

# Well-formed Roman numerals only: "IIII" is rejected, "IV" is not.
_ROMAN_RE = re.compile(
    r"M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
)
_ROMAN_VALUES = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}

_GEMATRIA_UNITS = ("", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט")
_GEMATRIA_TENS = ("", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ")
_GEMATRIA_HUNDREDS = ("", "ק", "ר")

# Final letter forms carry the same numeric value as their plain forms.
_HEBREW_FINAL_FORMS = str.maketrans(
    {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}
)

# Geresh and gershayim mark a letter sequence as a numeral. Keyed data
# often substitutes the ASCII apostrophe and quotation mark.
_NUMERAL_MARKS = "׳״'\""

# Roman numerals and gematria are read no higher than this. Volume
# designations stay well below it, and a longer match is more likely a
# year or an ordinary word made of numeral letters.
_MAX_LETTER_VOLUME = 200


def _hebrew_numeral(value: int) -> str:
    """Spell *value* (1 through 200) the way gematria is written.

    Fifteen and sixteen are spelled 9+6 and 9+7 rather than 10+5 and
    10+6, whose letters spell a divine name. The same substitution
    applies within the hundreds, so 115 is 100+9+6.
    """
    tail = value % 100
    if tail == 15:
        letters = "טו"
    elif tail == 16:
        letters = "טז"
    else:
        letters = _GEMATRIA_TENS[tail // 10] + _GEMATRIA_UNITS[tail % 10]
    return _GEMATRIA_HUNDREDS[value // 100] + letters


# Built from the spelling rule so the exceptional forms live in one
# place. Sequences outside this table, including the divine-name
# spellings of fifteen and sixteen, are not read as numerals.
_GEMATRIA_VALUES = {
    _hebrew_numeral(value): value for value in range(1, _MAX_LETTER_VOLUME + 1)
}


def _roman_to_int(numeral: str) -> int:
    """Convert an uppercase, well-formed Roman numeral to an integer."""
    total = 0
    highest = 0
    for char in reversed(numeral):
        value = _ROMAN_VALUES[char]
        if value < highest:
            total -= value
        else:
            total += value
            highest = value
    return total


def _volume_token_value(token: str) -> int | None:
    """Read *token* as a volume number, or return None if it is not one.

    Arabic digits are tried first, then Roman numerals, then gematria.
    """
    token = token.strip(".,;:()[]{}<>-–—/\\")
    if not token:
        return None

    if _DIGITS_RE.fullmatch(token):
        value = int(token)
        return value if value > 0 else None

    upper = token.upper()
    if _ROMAN_RE.fullmatch(upper):
        value = _roman_to_int(upper)
        if 1 <= value <= _MAX_LETTER_VOLUME:
            return value
        return None

    letters = "".join(c for c in token if c not in _NUMERAL_MARKS)
    letters = letters.translate(_HEBREW_FINAL_FORMS)
    return _GEMATRIA_VALUES.get(letters)


def normalize_volume_number(raw: str | None) -> str:
    """Return the volume number in *raw* written as Arabic digits.

    Covers the three ways volume designations reach the catalog:
    Arabic digits ("v. 3"), Roman numerals ("vol. III"), and Hebrew
    gematria ("חלק ג"). A leading word such as "vol." or "כרך" is
    dropped, as is any part title after a colon, so "ספר ג: משפטים" is
    volume 3. The first token that reads as a number wins.

    Returns "" when *raw* is empty or holds no volume number; the caller
    gets no volume rather than a zero to mistake for one. A non-empty
    result is a positive integer with no leading zeros.
    """
    if not raw:
        return ""

    text = str(raw).split(":", 1)[0].strip()

    match = _PREFIX_RE.match(text)
    while match:
        text = text[match.end() :].strip()
        match = _PREFIX_RE.match(text)

    for token in text.split():
        value = _volume_token_value(token)
        if value is not None:
            return str(value)

    return ""


def _parse_volume_spec(volume_specs: str | list) -> list[str]:
    """Parse a volume specification into a sorted list of volume number strings.

    Accepts:
    - A list of volume numbers (ints or strings): ``[1, 2, 5]``
    - A range string: ``"1-13"``
    - An "all N" string: ``"all 8"`` (creates volumes 1..8)
    """
    if isinstance(volume_specs, list):
        return [str(v) for v in volume_specs]

    spec = str(volume_specs).strip()

    # "all N" pattern
    all_match = re.match(r"^all\s+(\d+)$", spec, re.IGNORECASE)
    if all_match:
        total = int(all_match.group(1))
        return [str(i) for i in range(1, total + 1)]

    # "N-M" range pattern
    range_match = re.match(r"^(\d+)\s*-\s*(\d+)$", spec)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        return [str(i) for i in range(start, end + 1)]

    # Single number or comma-separated
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    return parts


def create_series_volumes(
    series: Series,
    volume_specs: str | list,
    records: dict[str, Record] | None = None,
) -> list[SeriesVolume]:
    """Create SeriesVolume entries for *series*.

    *volume_specs* is parsed by ``_parse_volume_spec`` (accepts a list,
    range string like ``"1-13"``, or ``"all 8"``).

    *records* is an optional mapping of volume number string to Record.
    Volumes with a matching record are created with ``held=True``; volumes
    without are created with ``held=False`` (gap placeholders).

    Existing volumes for the same series/volume_number are skipped (not
    duplicated).

    Returns the list of newly created SeriesVolume objects.
    """
    records = records or {}
    volume_numbers = _parse_volume_spec(volume_specs)

    created: list[SeriesVolume] = []
    for vol_num in volume_numbers:
        record = records.get(vol_num)
        held = record is not None

        sv, was_created = SeriesVolume.objects.get_or_create(
            series=series,
            volume_number=vol_num,
            defaults={"record": record, "held": held},
        )
        if was_created:
            created.append(sv)

    return created


def link_record_to_series(
    record: Record,
    series_title: str | None,
    series_volume: str | None = "",
) -> SeriesVolume | None:
    """Place *record* in the series its 490/830 names.

    Finds or creates the Series, then gives the record a position in it.
    Returns the SeriesVolume, or None when there is nothing to link:
    no series title, or a position already taken by another record.

    A series is identified by its title alone, normalized. The title is
    the only thing every volume of a set agrees on -- author, publisher,
    date and extent all vary volume by volume, and an edited set has a
    different author on every one -- so keying on anything else would
    produce a Series per record, which is the failure this avoids.
    Titles are compared with punctuation and case removed, because the
    punctuation belongs to the cataloger rather than to the set: one
    catalog writes "ArtScroll series ;" where another writes "ArtScroll
    series." The cost of title-only identity is that two unrelated sets
    sharing a generic name merge into one. That is visible on the series
    page and can be undone by editing; the opposite mistake, one set
    split across two rows, shows up nowhere.

    The stored title carries no transcribed punctuation, the same way
    the record's own fields do not. The volume designation is
    canonicalized to Arabic digits, so "v. 3", "vol. III" and "חלק ג"
    all name position 3 of the set rather than three positions.
    """
    title = strip_marc_punctuation(series_title)
    if not title:
        return None

    series = find_matching_series(title)
    if series is None:
        series = Series.objects.create(title=title)

    # A record holds one position in a series. Re-confirming the same
    # candidate, or confirming it under a differently written volume
    # designation, must not add a second.
    existing = SeriesVolume.objects.filter(
        series=series, record=record
    ).first()
    if existing is not None:
        return existing

    volume_number = normalize_volume_number(series_volume)

    occupant = SeriesVolume.objects.filter(
        series=series, volume_number=volume_number
    ).first()
    if occupant is not None:
        if occupant.record_id is not None:
            # (series, volume_number) is unique, so the position cannot
            # hold both. The record stays in the catalog without a
            # series position, which is the honest answer when two
            # records claim one place in a set.
            logger.warning(
                "Series %s volume %r already held by record %s; "
                "leaving record %s unplaced",
                series.pk,
                volume_number,
                occupant.record_id,
                record.pk,
            )
            return None
        # A gap placeholder for a volume not yet held. Fill it.
        occupant.record = record
        occupant.held = True
        occupant.save(update_fields=["record", "held"])
        return occupant

    return SeriesVolume.objects.create(
        series=series,
        record=record,
        volume_number=volume_number,
        held=True,
    )
