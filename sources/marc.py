"""MARC record parser for SRU responses.

Extracts bibliographic metadata from MARCXML embedded in SRU envelopes,
handling both LC's 880-field pattern (alternate script in linked fields)
and NLI's pattern (Hebrew directly in primary fields like 245, 100).
"""

import json
import re
import xml.etree.ElementTree as ET

import mrrc

# --- Namespace handling ---

SRU_NS = "http://www.loc.gov/zing/srw/"
MARC_NS = "http://www.loc.gov/MARC21/slim"

# Register the MARC namespace so ET.tostring() uses the default namespace
# instead of ns0: prefix -- required for mrrc.xml_to_record() to parse correctly.
ET.register_namespace("", MARC_NS)

# Hebrew Unicode block range.
_HEBREW_RE = re.compile(r"[\u0590-\u05FF]")


# --- Public API ---


def extract_marc_records(xml_text: str) -> tuple[int, list[mrrc.Record]]:
    """Parse an SRU response envelope and yield mrrc Record objects.

    Returns a tuple of (total_hit_count, list_of_parsed_records).
    The hit count comes from ``<numberOfRecords>`` in the SRU envelope
    and may be larger than the number of records returned in one page.

    Diagnostics in the SRU response are silently ignored; callers that
    need them should parse the XML themselves.
    """
    root = ET.fromstring(xml_text)

    ns_sru = f"{{{SRU_NS}}}"
    ns_marc = f"{{{MARC_NS}}}"

    num_elem = root.find(f".//{ns_sru}numberOfRecords")
    num_records = int(num_elem.text) if num_elem is not None else 0

    records: list[mrrc.Record] = []
    for record_data in root.findall(f".//{ns_sru}recordData"):
        marc_elem = record_data.find(f"{ns_marc}record")
        if marc_elem is None:
            continue

        marc_xml_str = ET.tostring(marc_elem, encoding="unicode")
        try:
            parsed = mrrc.xml_to_record(marc_xml_str)
            records.append(parsed)
        except Exception:
            # Skip records that mrrc cannot parse.
            continue

    return num_records, records


def has_hebrew(text: str | None) -> bool:
    """Return True if *text* contains any Hebrew characters (U+0590--U+05FF)."""
    if not text:
        return False
    return bool(_HEBREW_RE.search(text))


def get_field_value(
    record: mrrc.Record,
    tag: str,
    subfield_codes: list[str] | None = None,
) -> str | None:
    """Extract concatenated subfield values from a MARC field.

    For control fields (tags 001--009) the raw value is returned and
    *subfield_codes* is ignored.  For data fields the requested subfield
    values are joined with a single space.
    """
    if tag.startswith("00"):
        val = record.control_field(tag)
        return val if val else None

    field = record.get_field(tag)
    if field is None:
        return None

    if subfield_codes:
        parts: list[str] = []
        for code in subfield_codes:
            parts.extend(field.get_subfields(code))
        return " ".join(parts) if parts else None

    return str(field)


def _linked_880_value(
    record: mrrc.Record,
    tag: str,
    subfield_codes: list[str],
) -> str | None:
    """Get the alternate-script (880) value linked to *tag*.

    LC cataloging stores vernacular script in 880 fields with ``$6``
    linkage back to the original tag (e.g. ``245-01``).  This helper
    walks all 880 fields looking for one whose ``$6`` starts with the
    target tag.
    """
    fields_880 = record.get_fields("880")
    if not fields_880:
        return None

    for f880 in fields_880:
        linkage = f880.get_subfields("6")
        if not linkage:
            continue
        # Linkage format: "TAG-OCCURRENCE/(script)" e.g. "245-01/(2"
        if linkage[0].startswith(f"{tag}-"):
            parts = []
            for code in subfield_codes:
                parts.extend(f880.get_subfields(code))
            if parts:
                return " ".join(parts)
    return None


def parse_record(marc_record: mrrc.Record) -> dict:
    """Extract key bibliographic fields from an mrrc Record.

    Returns a dict with the following keys:

    - ``title`` -- from 245$a + 245$b
    - ``title_alternate`` -- from 880 linked to 245, or from 245 itself
      if the primary title already contains Hebrew (NLI pattern)
    - ``author`` -- from 100$a
    - ``author_alternate`` -- from 880 linked to 100, or from 100 itself
      if the primary author already contains Hebrew
    - ``publisher`` -- from 260$b or 264$b
    - ``place`` -- from 260$a or 264$a
    - ``date`` -- from 260$c or 264$c, falling back to 008 positions 7--10
    - ``language`` -- from 008 positions 35--37
    - ``isbn`` -- from 020$a
    - ``subjects`` -- list of strings from 650$a
    - ``series_title`` -- from 490$a or 830$a
    - ``series_volume`` -- from 490$v or 830$v
    """
    result: dict = {}

    # --- Title ---
    title = get_field_value(marc_record, "245", ["a", "b"])
    result["title"] = title

    # Alternate title: try 880 linkage first (LC pattern), then check
    # whether the primary title itself is in Hebrew (NLI pattern).
    alt_title = _linked_880_value(marc_record, "245", ["a", "b"])
    if alt_title is None and has_hebrew(title):
        # NLI pattern: Hebrew is already in the primary field;
        # there is no separate alternate.
        alt_title = title
    result["title_alternate"] = alt_title

    # --- Author ---
    author = get_field_value(marc_record, "100", ["a"])
    result["author"] = author

    alt_author = _linked_880_value(marc_record, "100", ["a"])
    if alt_author is None and has_hebrew(author):
        alt_author = author
    result["author_alternate"] = alt_author

    # --- Publisher / Place / Date ---
    # Try 260 first, fall back to 264.
    publisher = get_field_value(marc_record, "260", ["b"])
    if publisher is None:
        publisher = get_field_value(marc_record, "264", ["b"])
    result["publisher"] = publisher

    place = get_field_value(marc_record, "260", ["a"])
    if place is None:
        place = get_field_value(marc_record, "264", ["a"])
    result["place"] = place

    date = get_field_value(marc_record, "260", ["c"])
    if date is None:
        date = get_field_value(marc_record, "264", ["c"])
    if date is None:
        f008 = get_field_value(marc_record, "008")
        if f008 and len(f008) >= 11:
            date = f008[7:11]
    result["date"] = date

    # --- Language ---
    f008 = get_field_value(marc_record, "008")
    result["language"] = f008[35:38] if f008 and len(f008) >= 38 else None

    # --- ISBN ---
    result["isbn"] = get_field_value(marc_record, "020", ["a"])

    # --- Additional authors (700 fields) ---
    additional_authors: list[str] = []
    for field in marc_record.get_fields("700"):
        vals = field.get_subfields("a")
        if vals:
            additional_authors.append(vals[0])
    result["additional_authors"] = additional_authors

    # --- Subjects ---
    subjects: list[str] = []
    for field in marc_record.get_fields("650"):
        vals = field.get_subfields("a")
        if vals:
            subjects.append(vals[0])
    result["subjects"] = subjects

    # --- LCCN (010$a) ---
    result["lccn"] = get_field_value(marc_record, "010", ["a"])

    # --- OCLC (035$a) ---
    oclc = None
    for field in marc_record.get_fields("035"):
        vals = field.get_subfields("a")
        if vals and "OCoLC" in vals[0]:
            oclc = vals[0].replace("(OCoLC)", "").strip()
            break
    result["oclc"] = oclc

    # --- Series ---
    series_title = get_field_value(marc_record, "490", ["a"])
    if series_title is None:
        series_title = get_field_value(marc_record, "830", ["a"])
    result["series_title"] = series_title

    series_volume = get_field_value(marc_record, "490", ["v"])
    if series_volume is None:
        series_volume = get_field_value(marc_record, "830", ["v"])
    result["series_volume"] = series_volume

    return result


def record_to_marcjson(marc_record: mrrc.Record) -> dict:
    """Convert an mrrc Record to a MARCJSON dict.

    MARCJSON is the JSON serialization of MARC defined by the Library of
    Congress.  The returned dict is suitable for storage in a JSONField
    and can be round-tripped back to an mrrc Record via
    ``mrrc.json_to_record(json.dumps(d))``.
    """
    return json.loads(marc_record.to_marcjson())
