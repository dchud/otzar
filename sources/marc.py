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

# The C1 control range. MARC-8 brackets a leading article that sorting
# should skip between a non-sorting begin and end character, and those
# convert to U+0098 and U+009C. Browsers render the range as nothing, so
# a heading that carries it reads as though it had stray whitespace.
_C1_CONTROL_RE = re.compile(r"[\u0080-\u009F]")

# Subfields that make up a subject heading: the topical term ($a) and
# the form ($v), general ($x), chronological ($y) and geographic ($z)
# subdivisions.
_HEADING_CODES = frozenset("avxyz")

# How a subdivided heading reads once assembled, per LCSH display
# practice: "Jews -- Israel -- History".
_SUBDIVISION_SEPARATOR = " -- "

# Trailing MARC punctuation, disregarded when comparing two headings.
_TRAILING_PUNCTUATION_RE = re.compile(r"[\s.,;:/]+$")


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


def strip_control_characters(text: str | None) -> str | None:
    """Remove C1 control characters (U+0080--U+009F) from *text*.

    The pair that shows up in catalog data is U+0098 and U+009C, the
    non-sorting delimiters wrapped around a leading article. They carry
    no meaning once a heading is out of its sort context, and no
    renderer displays them, so they are dropped on the way in.

    *text* is returned unchanged when it is None or empty.
    """
    if not text:
        return text
    return _C1_CONTROL_RE.sub("", text)


def has_hebrew(text: str | None) -> bool:
    """Return True if *text* contains any Hebrew characters (U+0590--U+05FF)."""
    if not text:
        return False
    return bool(_HEBREW_RE.search(text))


def _subfield_values(field: mrrc.Field, codes: list[str]) -> list[str]:
    """Return *field*'s values for *codes*, cleaned, in the order of *codes*.

    Every path that pulls text out of a data field goes through here, so
    a source that carries non-sorting delimiters is handled the same way
    whichever field it puts them in.
    """
    values: list[str] = []
    for code in codes:
        values.extend(
            strip_control_characters(value)
            for value in field.get_subfields(code)
        )
    return values


def get_field_value(
    record: mrrc.Record,
    tag: str,
    subfield_codes: list[str] | None = None,
) -> str | None:
    """Extract concatenated subfield values from a MARC field.

    For control fields (tags 001--009) the raw value is returned and
    *subfield_codes* is ignored: those fields are read by character
    position, so removing anything from them would shift the rest.  For
    data fields the requested subfield values are cleaned of control
    characters and joined with a single space.
    """
    if tag.startswith("00"):
        val = record.control_field(tag)
        return val if val else None

    field = record.get_field(tag)
    if field is None:
        return None

    if subfield_codes:
        parts = _subfield_values(field, subfield_codes)
        return " ".join(parts) if parts else None

    return strip_control_characters(str(field))


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
            parts = _subfield_values(f880, subfield_codes)
            if parts:
                return " ".join(parts)
    return None


def _subject_heading(field: mrrc.Field) -> str | None:
    """Assemble one full subject heading from a 650 field.

    A heading is its topical term ($a) followed by whatever
    subdivisions the cataloger applied, in the order the field carries
    them.  Everything else in the field describes the heading rather
    than forming part of it: $2 names the vocabulary, $0 and $1 hold
    control numbers, $6 and $8 hold linkages.
    """
    parts = [
        strip_control_characters(subfield.value).strip()
        for subfield in field.subfields()
        if subfield.code in _HEADING_CODES
    ]
    parts = [part for part in parts if part]
    if not parts:
        return None
    return _SUBDIVISION_SEPARATOR.join(parts)


def _heading_key(heading: str) -> str:
    """Normalized form deciding whether two headings are the same heading.

    Whitespace and the punctuation a cataloger puts at the end of a
    field vary between vocabularies -- LCSH ends a heading with a
    period, FAST does not -- and neither difference makes a second
    heading.
    """
    return _TRAILING_PUNCTUATION_RE.sub("", " ".join(heading.split()))


def _subject_headings(record: mrrc.Record) -> list[str]:
    """Return the record's 650 headings, subdivisions kept, duplicates out.

    A record catalogued in two vocabularies at once carries the same
    heading twice, once per 650, and only $2 tells them apart.  The
    first form encountered is the one kept.
    """
    headings: list[str] = []
    seen: set[str] = set()
    for field in record.get_fields("650"):
        heading = _subject_heading(field)
        if heading is None:
            continue
        key = _heading_key(heading)
        if key in seen:
            continue
        seen.add(key)
        headings.append(heading)
    return headings


def parse_record(marc_record: mrrc.Record) -> dict:
    """Extract key bibliographic fields from an mrrc Record.

    Returns a dict with the following keys:

    - ``title`` -- from 245$a + 245$b
    - ``title_alternate`` -- from 880 linked to 245, or from 245 itself
      if the primary title already contains Hebrew (NLI pattern)
    - ``volume_part_number`` -- from 245$n, the designation of a part
      within the title ("Volume 2", "Bd. 4, T. 2")
    - ``volume_part_title`` -- from 245$p, the name of that part
      ("Sefer Mishpatim")
    - ``statement_of_responsibility`` -- from 245$c, transcribed as the
      cataloger wrote it
    - ``author`` -- from 100$a
    - ``author_alternate`` -- from 880 linked to 100, or from 100 itself
      if the primary author already contains Hebrew
    - ``publisher`` -- from 260$b or 264$b
    - ``place`` -- from 260$a or 264$a
    - ``date`` -- from 260$c or 264$c, falling back to 008 positions 7--10
    - ``language`` -- from 008 positions 35--37
    - ``isbn`` -- from 020$a
    - ``subjects`` -- list of 650 headings, each its $a followed by any
      subdivisions, deduplicated
    - ``series_title`` -- from 490$a or 830$a
    - ``series_volume`` -- from 490$v or 830$v
    - ``source_marc`` -- the whole record as MARC-in-JSON, uncleaned

    Every value above except ``source_marc`` is cleaned for display.
    ``source_marc`` is the archival copy of what the catalog sent, so it
    is carried through exactly as received: it is the only record of the
    source document, and anything that later needs to re-derive a value
    has nothing else to read.
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

    # The rest of the title statement. $n designates a part of this
    # title and $p names it; both are repeatable, so a nested part
    # ("Seder 1, Masekhet 2") arrives as several subfields and is joined
    # in the order the field carries them. They are kept out of ``title``
    # because a set's parts otherwise differ only in a buried numeral.
    result["volume_part_number"] = get_field_value(marc_record, "245", ["n"])
    result["volume_part_title"] = get_field_value(marc_record, "245", ["p"])

    # $c is the statement of responsibility, transcribed from the item.
    # Where the 700 fields carry no $e relator term and no $4 relator
    # code -- common in LC copy -- it is the only place the record says
    # which contributor did what, so it is kept whole and unparsed.
    result["statement_of_responsibility"] = get_field_value(
        marc_record, "245", ["c"]
    )

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
        vals = _subfield_values(field, ["a"])
        if vals:
            additional_authors.append(vals[0])
    result["additional_authors"] = additional_authors

    # --- Subjects ---
    result["subjects"] = _subject_headings(marc_record)

    # --- LCCN (010$a) ---
    result["lccn"] = get_field_value(marc_record, "010", ["a"])

    # --- OCLC (035$a) ---
    oclc = None
    for field in marc_record.get_fields("035"):
        vals = _subfield_values(field, ["a"])
        if vals and "OCoLC" in vals[0]:
            oclc = vals[0].replace("(OCoLC)", "").strip()
            break
    result["oclc"] = oclc

    # --- Classification ---
    # LC call number from 050$a + 050$b
    lc_call = get_field_value(marc_record, "050", ["a", "b"])
    result["lc_classification"] = lc_call

    # Dewey from 082$a
    dewey = get_field_value(marc_record, "082", ["a"])
    result["dewey_classification"] = dewey

    # --- Series ---
    series_title = get_field_value(marc_record, "490", ["a"])
    if series_title is None:
        series_title = get_field_value(marc_record, "830", ["a"])
    result["series_title"] = series_title

    series_volume = get_field_value(marc_record, "490", ["v"])
    if series_volume is None:
        series_volume = get_field_value(marc_record, "830", ["v"])
    result["series_volume"] = series_volume

    # --- Source record ---
    result["source_marc"] = record_to_marcjson(marc_record)

    return result


def record_to_marcjson(marc_record: mrrc.Record) -> dict:
    """Convert an mrrc Record to a MARC-in-JSON dict.

    MARC-in-JSON carries the whole record: the leader as a string, and
    every field as a single-key object in an ordered list, so a repeated
    tag stays repeated and field order survives.  Control fields hold
    their value directly; data fields hold their two indicators and an
    ordered list of subfields.

    The result is JSON-serializable and suitable for a JSONField.  mrrc
    reads the flat field list rather than the wrapper, so the way back
    to a Record is::

        entries = [{"leader": d["leader"]}, *d["fields"]]
        mrrc.marcjson_to_record(json.dumps(entries, ensure_ascii=False))

    Nothing is cleaned or normalized here.  This is the archival copy of
    what the catalog sent, and the cleaning that display needs happens
    on the extraction path instead.
    """
    leader = ""
    fields: list[dict] = []
    for entry in json.loads(marc_record.to_marcjson()):
        if "leader" in entry:
            leader = entry["leader"]
        else:
            fields.append(entry)
    return {"leader": leader, "fields": fields}
