"""Utility functions for catalog data cleaning."""

import re

# Abbreviations where a trailing period should be preserved.
_ABBREVIATIONS = frozenset(
    {
        "Jr",
        "Sr",
        "Inc",
        "Ltd",
        "ed",
        "Rev",
        "Dr",
        "Mr",
        "Mrs",
        "Ms",
        "Prof",
        "Vol",
        "vol",
        "No",
        "no",
        "Dept",
        "dept",
        "Assn",
        "Bros",
        "Co",
        "Corp",
        "Dist",
        "Div",
        "Est",
        "Gen",
        "Gov",
        "Sgt",
        "St",
        "Univ",
        "etc",
    }
)

# Pattern for trailing MARC delimiters: " :", " ;", " /", trailing ","
_TRAILING_DELIMITERS_RE = re.compile(r"\s+[;:/]$|,$")


def strip_marc_punctuation(value: str | None) -> str:
    """Strip common trailing MARC punctuation from a field value.

    Removes:
    - Leading/trailing whitespace
    - Trailing ` :`, ` ;`, ` /`, `,`
    - Trailing `.` unless it follows:
      - A single uppercase letter (initial, e.g. "John A.")
      - A known abbreviation (Jr., Sr., Inc., etc.)
      - An ellipsis (...)

    Returns an empty string for None or empty input.
    """
    if not value:
        return ""

    text = value.strip()
    if not text:
        return ""

    # Strip trailing MARC delimiters (may need multiple passes for edge cases
    # like "value , :" though that's unlikely in practice).
    text = _TRAILING_DELIMITERS_RE.sub("", text).rstrip()

    # Handle trailing period, but preserve when it's meaningful.
    if text.endswith(".") and not text.endswith("..."):
        without_dot = text[:-1]
        last_word = without_dot.rsplit(None, 1)[-1] if without_dot else ""

        # Single uppercase letter = initial (e.g. "J.")
        if len(last_word) == 1 and last_word.isupper():
            return text

        # Known abbreviation
        if last_word in _ABBREVIATIONS:
            return text

        # Otherwise strip the trailing period
        text = without_dot.rstrip()

    return text
