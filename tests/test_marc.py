"""Tests for sources.marc -- MARC record parsing from SRU responses."""

import json

import mrrc
import pytest

from sources.marc import (
    extract_marc_records,
    get_field_value,
    has_hebrew,
    parse_record,
    record_to_marcjson,
    strip_control_characters,
)

# ---------------------------------------------------------------------------
# Fixtures: minimal SRU XML envelopes with embedded MARCXML
# ---------------------------------------------------------------------------

# LC-style record: romanised primary fields with 880 alternate-script
# linkage (Hebrew title and author in 880 fields).
LC_SRU_XML = """\
<?xml version="1.0"?>
<zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/">
<zs:version>1.1</zs:version>
<zs:numberOfRecords>42</zs:numberOfRecords>
<zs:records>
<zs:record>
<zs:recordSchema>marcxml</zs:recordSchema>
<zs:recordPacking>xml</zs:recordPacking>
<zs:recordData>
<record xmlns="http://www.loc.gov/MARC21/slim">
  <leader>01500cam a2200300 a 4500</leader>
  <controlfield tag="001">12345678</controlfield>
  <controlfield tag="008">090213s2007    is       b    000 0 heb  </controlfield>
  <datafield tag="020" ind1=" " ind2=" ">
    <subfield code="a">9789650716745</subfield>
  </datafield>
  <datafield tag="100" ind1="1" ind2=" ">
    <subfield code="6">880-02</subfield>
    <subfield code="a">Soloveitchik, Joseph Dov,</subfield>
  </datafield>
  <datafield tag="245" ind1="1" ind2="0">
    <subfield code="6">880-01</subfield>
    <subfield code="a">Halakhic man /</subfield>
    <subfield code="b">a philosophical essay.</subfield>
  </datafield>
  <datafield tag="260" ind1=" " ind2=" ">
    <subfield code="a">Jerusalem :</subfield>
    <subfield code="b">Sefer Press,</subfield>
    <subfield code="c">2007.</subfield>
  </datafield>
  <datafield tag="490" ind1="1" ind2=" ">
    <subfield code="a">Library of Jewish thought ;</subfield>
    <subfield code="v">vol. 3</subfield>
  </datafield>
  <datafield tag="650" ind1=" " ind2="0">
    <subfield code="a">Jewish law.</subfield>
  </datafield>
  <datafield tag="650" ind1=" " ind2="0">
    <subfield code="a">Jewish philosophy.</subfield>
  </datafield>
  <datafield tag="880" ind1="1" ind2="0">
    <subfield code="6">245-01/(2</subfield>
    <subfield code="a">\u05d0\u05d9\u05e9 \u05d4\u05d4\u05dc\u05db\u05d4 /</subfield>
    <subfield code="b">\u05de\u05e1\u05d4 \u05e4\u05d9\u05dc\u05d5\u05e1\u05d5\u05e4\u05d9.</subfield>
  </datafield>
  <datafield tag="880" ind1="1" ind2=" ">
    <subfield code="6">100-02/(2</subfield>
    <subfield code="a">\u05e1\u05d5\u05dc\u05d5\u05d1\u05d9\u05d9\u05e6'\u05d9\u05e7, \u05d9\u05d5\u05e1\u05e3 \u05d3\u05d1,</subfield>
  </datafield>
</record>
</zs:recordData>
<zs:recordPosition>1</zs:recordPosition>
</zs:record>
</zs:records>
</zs:searchRetrieveResponse>
"""

# NLI-style record: Hebrew directly in primary 245 and 100 fields,
# no 880 linkage needed.
NLI_SRU_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <version>1.2</version>
  <numberOfRecords>1</numberOfRecords>
  <records>
    <record>
      <recordSchema>marcxml</recordSchema>
      <recordPacking>xml</recordPacking>
      <recordData>
        <record xmlns="http://www.loc.gov/MARC21/slim">
          <leader>02232nam a2200313 i 4500</leader>
          <controlfield tag="001">990012230280205171</controlfield>
          <controlfield tag="008">191104s1887    un            000 0 heb d</controlfield>
          <datafield ind1="1" ind2=" " tag="100">
            <subfield code="a">\u05d4\u05d5\u05e8\u05d5\u05d5\u05d9\u05e5, \u05d9\u05e6\u05d7\u05e7,</subfield>
          </datafield>
          <datafield ind1="1" ind2="4" tag="245">
            <subfield code="a">\u05e1\u05e4\u05e8 \u05de\u05d0\u05d4 \u05e9\u05e2\u05e8\u05d9\u05dd :</subfield>
            <subfield code="b">\u05db\u05d5\u05dc\u05dc \u05de\u05d0\u05d4 \u05e1\u05d5\u05d2\u05d9\u05d5\u05ea /</subfield>
          </datafield>
          <datafield ind1=" " ind2=" " tag="260">
            <subfield code="a">\u05dc\u05e2\u05de\u05d1\u05e2\u05e8\u05d2 :</subfield>
            <subfield code="b">\u05d3\u05e4\u05d5\u05e1 \u05d0.\u05d6. \u05d5\u05d5. \u05e1\u05d0\u05dc\u05d0\u05d8,</subfield>
            <subfield code="c">\u05ea\u05e8\u05de"\u05d6.</subfield>
          </datafield>
        </record>
      </recordData>
      <recordIdentifier>990012230280205171</recordIdentifier>
      <recordPosition>1</recordPosition>
    </record>
  </records>
</searchRetrieveResponse>
"""

# SRU response with zero records.
EMPTY_SRU_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <version>1.2</version>
  <numberOfRecords>0</numberOfRecords>
  <records/>
</searchRetrieveResponse>
"""

# LC record with 264 instead of 260 (RDA cataloging).
LC_264_SRU_XML = """\
<?xml version="1.0"?>
<zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/">
<zs:version>1.1</zs:version>
<zs:numberOfRecords>1</zs:numberOfRecords>
<zs:records>
<zs:record>
<zs:recordSchema>marcxml</zs:recordSchema>
<zs:recordPacking>xml</zs:recordPacking>
<zs:recordData>
<record xmlns="http://www.loc.gov/MARC21/slim">
  <leader>00900cam a2200200 i 4500</leader>
  <controlfield tag="001">99999999</controlfield>
  <controlfield tag="008">200101s2020    nyu           000 0 eng  </controlfield>
  <datafield tag="245" ind1="0" ind2="0">
    <subfield code="a">Modern cataloging /</subfield>
    <subfield code="b">an introduction.</subfield>
  </datafield>
  <datafield tag="264" ind1=" " ind2="1">
    <subfield code="a">New York :</subfield>
    <subfield code="b">Library Press,</subfield>
    <subfield code="c">2020.</subfield>
  </datafield>
  <datafield tag="830" ind1=" " ind2="0">
    <subfield code="a">LIS foundations ;</subfield>
    <subfield code="v">no. 7</subfield>
  </datafield>
</record>
</zs:recordData>
<zs:recordPosition>1</zs:recordPosition>
</zs:record>
</zs:records>
</zs:searchRetrieveResponse>
"""

# German cataloging practice marks a leading article for non-filing with
# a delimiter pair around it -- NSB and NSE, which convert to U+0098 and
# U+009C -- and leaves the second indicator at 0, where LC and NLI
# instead count the characters to skip in that indicator. The delimiters
# turn up wherever a title-like string can start with an article: 245,
# the 490 series statement, and a topical subject heading.
DNB_SRU_XML = """\
<?xml version="1.0"?>
<zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/">
<zs:version>1.1</zs:version>
<zs:numberOfRecords>1</zs:numberOfRecords>
<zs:records>
<zs:record>
<zs:recordSchema>MARC21-xml</zs:recordSchema>
<zs:recordPacking>xml</zs:recordPacking>
<zs:recordData>
<record xmlns="http://www.loc.gov/MARC21/slim">
  <leader>01000cam a2200265 c 4500</leader>
  <controlfield tag="001">1043327834</controlfield>
  <controlfield tag="008">180101s2018    gw            000 0 ger  </controlfield>
  <datafield tag="100" ind1="1" ind2=" ">
    <subfield code="a">Hausen, Anna von,</subfield>
  </datafield>
  <datafield tag="245" ind1="1" ind2="0">
    <subfield code="a">\u0098The\u009c Complete Piano Etudes /</subfield>
    <subfield code="b">a performer's guide.</subfield>
  </datafield>
  <datafield tag="264" ind1=" " ind2="1">
    <subfield code="a">Leipzig :</subfield>
    <subfield code="b">Verlag Beispiel,</subfield>
    <subfield code="c">2018.</subfield>
  </datafield>
  <datafield tag="490" ind1="1" ind2=" ">
    <subfield code="a">\u0098Die\u009c Klavierbibliothek ;</subfield>
    <subfield code="v">Band 4</subfield>
  </datafield>
  <datafield tag="650" ind1=" " ind2="0">
    <subfield code="a">\u0098The\u009c piano</subfield>
    <subfield code="x">Studies and exercises.</subfield>
  </datafield>
</record>
</zs:recordData>
<zs:recordPosition>1</zs:recordPosition>
</zs:record>
</zs:records>
</zs:searchRetrieveResponse>
"""

# LC record whose subject access shows both ways a 650 list goes wrong
# when only the first $a survives: headings that differ solely in their
# subdivisions, and one heading carried in two vocabularies at once
# (LCSH with terminal punctuation, FAST without).
LC_SUBJECTS_SRU_XML = """\
<?xml version="1.0"?>
<zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/">
<zs:version>1.1</zs:version>
<zs:numberOfRecords>1</zs:numberOfRecords>
<zs:records>
<zs:record>
<zs:recordSchema>marcxml</zs:recordSchema>
<zs:recordPacking>xml</zs:recordPacking>
<zs:recordData>
<record xmlns="http://www.loc.gov/MARC21/slim">
  <leader>01100cam a2200289 i 4500</leader>
  <controlfield tag="001">2019012345</controlfield>
  <controlfield tag="008">190101s2019    nyu           000 0 eng  </controlfield>
  <datafield tag="245" ind1="1" ind2="0">
    <subfield code="a">Jewish life in Israel /</subfield>
    <subfield code="b">an introduction.</subfield>
  </datafield>
  <datafield tag="650" ind1=" " ind2="0">
    <subfield code="a">Jews</subfield>
    <subfield code="z">Israel</subfield>
    <subfield code="x">History.</subfield>
  </datafield>
  <datafield tag="650" ind1=" " ind2="0">
    <subfield code="a">Jews</subfield>
    <subfield code="x">Social life and customs.</subfield>
  </datafield>
  <datafield tag="650" ind1=" " ind2="0">
    <subfield code="a">Judaism.</subfield>
  </datafield>
  <datafield tag="650" ind1=" " ind2="7">
    <subfield code="a">Judaism</subfield>
    <subfield code="2">fast</subfield>
    <subfield code="0">(OCoLC)fst00984378</subfield>
  </datafield>
  <datafield tag="650" ind1=" " ind2="7">
    <subfield code="a">Jews</subfield>
    <subfield code="2">fast</subfield>
  </datafield>
  <datafield tag="650" ind1=" " ind2="0">
    <subfield code="a">Passover</subfield>
    <subfield code="v">Juvenile literature.</subfield>
  </datafield>
</record>
</zs:recordData>
<zs:recordPosition>1</zs:recordPosition>
</zs:record>
</zs:records>
</zs:searchRetrieveResponse>
"""


# ---------------------------------------------------------------------------
# Tests: extract_marc_records
# ---------------------------------------------------------------------------


class TestExtractMarcRecords:
    def test_lc_envelope(self):
        count, records = extract_marc_records(LC_SRU_XML)
        assert count == 42
        assert len(records) == 1
        assert isinstance(records[0], mrrc.Record)

    def test_nli_envelope(self):
        count, records = extract_marc_records(NLI_SRU_XML)
        assert count == 1
        assert len(records) == 1

    def test_empty_response(self):
        count, records = extract_marc_records(EMPTY_SRU_XML)
        assert count == 0
        assert records == []


# ---------------------------------------------------------------------------
# Tests: has_hebrew
# ---------------------------------------------------------------------------


class TestHasHebrew:
    def test_hebrew_text(self):
        assert has_hebrew("\u05e9\u05dc\u05d5\u05dd") is True

    def test_latin_text(self):
        assert has_hebrew("Hello world") is False

    def test_mixed_text(self):
        assert has_hebrew("Title: \u05e9\u05dc\u05d5\u05dd") is True

    def test_empty_string(self):
        assert has_hebrew("") is False

    def test_none(self):
        assert has_hebrew(None) is False


# ---------------------------------------------------------------------------
# Tests: get_field_value
# ---------------------------------------------------------------------------


class TestGetFieldValue:
    @pytest.fixture()
    def lc_record(self):
        _, records = extract_marc_records(LC_SRU_XML)
        return records[0]

    def test_control_field(self, lc_record):
        val = get_field_value(lc_record, "008")
        assert val is not None
        assert "heb" in val

    def test_subfield_extraction(self, lc_record):
        val = get_field_value(lc_record, "245", ["a", "b"])
        assert "Halakhic man" in val
        assert "philosophical essay" in val

    def test_missing_field(self, lc_record):
        val = get_field_value(lc_record, "999", ["a"])
        assert val is None

    def test_no_subfield_codes(self, lc_record):
        val = get_field_value(lc_record, "245")
        assert val is not None


# ---------------------------------------------------------------------------
# Tests: parse_record (LC pattern with 880 linkage)
# ---------------------------------------------------------------------------


class TestParseRecordLC:
    @pytest.fixture()
    def parsed(self):
        _, records = extract_marc_records(LC_SRU_XML)
        return parse_record(records[0])

    def test_title(self, parsed):
        assert "Halakhic man" in parsed["title"]
        assert "philosophical essay" in parsed["title"]

    def test_title_alternate_hebrew(self, parsed):
        alt = parsed["title_alternate"]
        assert alt is not None
        assert has_hebrew(alt)

    def test_author(self, parsed):
        assert "Soloveitchik" in parsed["author"]

    def test_author_alternate_hebrew(self, parsed):
        alt = parsed["author_alternate"]
        assert alt is not None
        assert has_hebrew(alt)

    def test_publisher(self, parsed):
        assert "Sefer Press" in parsed["publisher"]

    def test_place(self, parsed):
        assert "Jerusalem" in parsed["place"]

    def test_date(self, parsed):
        assert "2007" in parsed["date"]

    def test_language(self, parsed):
        assert parsed["language"] == "heb"

    def test_isbn(self, parsed):
        assert parsed["isbn"] == "9789650716745"

    def test_subjects(self, parsed):
        assert "Jewish law." in parsed["subjects"]
        assert "Jewish philosophy." in parsed["subjects"]

    def test_series_title(self, parsed):
        assert "Library of Jewish thought" in parsed["series_title"]

    def test_series_volume(self, parsed):
        assert "vol. 3" in parsed["series_volume"]


# ---------------------------------------------------------------------------
# Tests: parse_record (NLI pattern -- Hebrew directly in primary fields)
# ---------------------------------------------------------------------------


class TestParseRecordNLI:
    @pytest.fixture()
    def parsed(self):
        _, records = extract_marc_records(NLI_SRU_XML)
        return parse_record(records[0])

    def test_title_is_hebrew(self, parsed):
        assert has_hebrew(parsed["title"])

    def test_title_alternate_equals_title(self, parsed):
        # NLI pattern: no separate 880, so alternate = primary.
        assert parsed["title_alternate"] == parsed["title"]

    def test_author_is_hebrew(self, parsed):
        assert has_hebrew(parsed["author"])

    def test_author_alternate_equals_author(self, parsed):
        assert parsed["author_alternate"] == parsed["author"]

    def test_publisher_hebrew(self, parsed):
        assert has_hebrew(parsed["publisher"])

    def test_place_hebrew(self, parsed):
        assert has_hebrew(parsed["place"])

    def test_language(self, parsed):
        assert parsed["language"] == "heb"


# ---------------------------------------------------------------------------
# Tests: parse_record with 264 (RDA) fields and 830 series
# ---------------------------------------------------------------------------


class TestParseRecord264:
    @pytest.fixture()
    def parsed(self):
        _, records = extract_marc_records(LC_264_SRU_XML)
        return parse_record(records[0])

    def test_publisher_from_264(self, parsed):
        assert "Library Press" in parsed["publisher"]

    def test_place_from_264(self, parsed):
        assert "New York" in parsed["place"]

    def test_date_from_264(self, parsed):
        assert "2020" in parsed["date"]

    def test_series_title_from_830(self, parsed):
        assert "LIS foundations" in parsed["series_title"]

    def test_series_volume_from_830(self, parsed):
        assert "no. 7" in parsed["series_volume"]


# ---------------------------------------------------------------------------
# Tests: record_to_marcjson round-trip
# ---------------------------------------------------------------------------


class TestRecordToMarcjson:
    def test_structure_and_content(self):
        _, records = extract_marc_records(LC_SRU_XML)
        rec = records[0]
        marcjson = record_to_marcjson(rec)

        # Basic structure: list of dicts, leader first.
        assert isinstance(marcjson, list)
        assert "leader" in marcjson[0]

        # Find 245 entry and verify subfield content.
        entries_245 = [e for e in marcjson if "245" in e]
        assert len(entries_245) == 1
        subfields = entries_245[0]["245"]["subfields"]
        subfield_a = [sf["a"] for sf in subfields if "a" in sf]
        assert any("Halakhic man" in v for v in subfield_a)

    def test_control_fields_preserved(self):
        _, records = extract_marc_records(LC_SRU_XML)
        marcjson = record_to_marcjson(records[0])

        # Find 008 in the JSON array.
        control_008 = [entry for entry in marcjson if "008" in entry]
        assert len(control_008) == 1
        assert "heb" in control_008[0]["008"]

    def test_nli_hebrew_preserved(self):
        _, records = extract_marc_records(NLI_SRU_XML)
        marcjson = record_to_marcjson(records[0])

        json_str = json.dumps(marcjson, ensure_ascii=False)
        assert has_hebrew(json_str)


# ---------------------------------------------------------------------------
# Tests: strip_control_characters
# ---------------------------------------------------------------------------


class TestStripControlCharacters:
    def test_removes_non_sorting_delimiters(self):
        assert (
            strip_control_characters("\u0098The\u009c Complete Piano Etudes")
            == "The Complete Piano Etudes"
        )

    def test_removes_whole_c1_range(self):
        c1 = "".join(chr(code) for code in range(0x80, 0xA0))
        assert strip_control_characters(f"before{c1}after") == "beforeafter"

    def test_leaves_ordinary_text_alone(self):
        assert strip_control_characters("Halakhic man /") == "Halakhic man /"

    def test_leaves_hebrew_alone(self):
        hebrew = "\u05e1\u05e4\u05e8 \u05de\u05d0\u05d4"
        assert strip_control_characters(hebrew) == hebrew

    def test_empty_string(self):
        assert strip_control_characters("") == ""

    def test_none(self):
        assert strip_control_characters(None) is None


# ---------------------------------------------------------------------------
# Tests: parse_record with non-sorting delimiters (DNB pattern)
# ---------------------------------------------------------------------------


class TestParseRecordNonSorting:
    @pytest.fixture()
    def record(self):
        _, records = extract_marc_records(DNB_SRU_XML)
        return records[0]

    @pytest.fixture()
    def parsed(self, record):
        return parse_record(record)

    def test_get_field_value_strips_delimiters(self, record):
        val = get_field_value(record, "245", ["a"])
        assert val == "The Complete Piano Etudes /"

    def test_title(self, parsed):
        assert (
            parsed["title"]
            == "The Complete Piano Etudes / a performer's guide."
        )

    def test_series_title(self, parsed):
        assert parsed["series_title"] == "Die Klavierbibliothek ;"

    def test_subject(self, parsed):
        assert parsed["subjects"] == ["The piano -- Studies and exercises."]

    def test_no_c1_characters_survive(self, parsed):
        flattened = json.dumps(parsed, ensure_ascii=False)
        assert not any("\u0080" <= ch <= "\u009f" for ch in flattened)

    def test_control_field_positions_intact(self, parsed):
        # 008 is fixed-length and read by position, so it is left as-is.
        assert parsed["language"] == "ger"
        assert parsed["date"] == "2018."


# ---------------------------------------------------------------------------
# Tests: subject headings -- subdivisions and deduplication
# ---------------------------------------------------------------------------


class TestSubjectHeadings:
    @pytest.fixture()
    def parsed(self):
        _, records = extract_marc_records(LC_SUBJECTS_SRU_XML)
        return parse_record(records[0])

    def test_subdivisions_joined(self, parsed):
        assert "Jews -- Israel -- History." in parsed["subjects"]

    def test_subdivisions_follow_field_order(self, parsed):
        # $z precedes $x in the field, so it precedes it in the heading.
        assert "Jews -- History. -- Israel" not in parsed["subjects"]

    def test_headings_differing_only_by_subdivision_stay_apart(self, parsed):
        assert "Jews -- Social life and customs." in parsed["subjects"]
        assert "Jews -- Israel -- History." in parsed["subjects"]

    def test_form_subdivision_kept(self, parsed):
        assert "Passover -- Juvenile literature." in parsed["subjects"]

    def test_parallel_vocabulary_deduped(self, parsed):
        judaism = [h for h in parsed["subjects"] if h.startswith("Judaism")]
        assert judaism == ["Judaism."]

    def test_vocabulary_and_control_subfields_excluded(self, parsed):
        assert not any("fast" in h for h in parsed["subjects"])
        assert not any("OCoLC" in h for h in parsed["subjects"])

    def test_full_heading_list(self, parsed):
        assert parsed["subjects"] == [
            "Jews -- Israel -- History.",
            "Jews -- Social life and customs.",
            "Judaism.",
            "Jews",
            "Passover -- Juvenile literature.",
        ]
