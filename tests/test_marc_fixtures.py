"""Each stored SRU response still shows what it was kept for.

These fixtures are real catalog output, chosen because a hand-built
record encodes what its author expected rather than what the catalogs
send. A fixture that no longer carries its distinguishing treatment is
not a failing test of the application -- it is a fixture that has been
edited or replaced, and it should be noticed rather than trusted.
"""

import xml.etree.ElementTree as ET

import pytest

from sources.marc import extract_marc_records
from tests.marc_fixtures import DEMONSTRATES, FIXTURE_DIR, load

MARC = "{http://www.loc.gov/MARC21/slim}"


def fields(name, tag):
    """Return the datafield elements carrying *tag*."""
    root = ET.fromstring(load(name))
    return [df for df in root.iter(f"{MARC}datafield") if df.get("tag") == tag]


def has_subfield(datafields, code):
    return any(
        sf.get("code") == code
        for df in datafields
        for sf in df.findall(f"{MARC}subfield")
    )


def script_tagged(name):
    """True if any subfield carries NLI's $9 script marker."""
    root = ET.fromstring(load(name))
    return any(sf.get("code") == "9" for sf in root.iter(f"{MARC}subfield"))


def preferred_language_linked(name):
    root = ET.fromstring(load(name))
    return any(
        sf.get("code") == "8" and "Preferred" in (sf.text or "")
        for sf in root.iter(f"{MARC}subfield")
    )


class TestTheSetIsCoherent:
    def test_every_file_is_described(self):
        on_disk = {p.stem for p in FIXTURE_DIR.glob("*.xml")}
        assert on_disk == set(DEMONSTRATES)

    @pytest.mark.parametrize("name", sorted(DEMONSTRATES))
    def test_each_holds_exactly_one_record(self, name):
        count, records = extract_marc_records(load(name))
        assert count == 1
        assert len(records) == 1


class TestEachStillShowsWhatItWasKeptFor:
    def test_the_enhanced_contents_note_lists_volumes_in_subfield_t(self):
        assert has_subfield(
            fields("artscroll_chumash_contents_enhanced_lc", "505"), "t"
        )

    def test_the_enhanced_note_designates_volumes_inconsistently(self):
        # The case against expecting parseable enumeration: one field,
        # three spellings of the same word.
        note = fields("artscroll_chumash_contents_enhanced_lc", "505")[0]
        designations = [
            (sf.text or "")
            for sf in note.findall(f"{MARC}subfield")
            if sf.get("code") == "g"
        ]
        assert len({d.strip().lower() for d in designations}) > 1

    def test_880_linkage_reaches_many_fields(self):
        linked = {
            (sf.text or "").split("-")[0]
            for df in fields("mishnah_berurah_880_linkage_lc", "880")
            for sf in df.findall(f"{MARC}subfield")
            if sf.get("code") == "6"
        }
        assert len(linked) >= 5

    def test_the_lc_half_of_the_pair_qualifies_its_isbn_by_volume(self):
        assert has_subfield(fields("commentators_bible_lc", "020"), "q")

    def test_the_lc_half_uses_neither_of_nlis_script_markers(self):
        assert not script_tagged("commentators_bible_lc")
        assert not preferred_language_linked("commentators_bible_lc")

    def test_the_nli_half_marks_script_without_any_880(self):
        assert script_tagged("commentators_bible_nli")
        assert preferred_language_linked("commentators_bible_nli")
        assert fields("commentators_bible_nli", "880") == []

    def test_the_pair_disagrees_about_where_a_volume_qualifier_goes(self):
        """One book, one ISBN, and two places to put the volume.

        LC writes ``020 $a 9780827609426 $q v. 1``. NLI writes
        ``020 $a 9780827609426 (v. [1])``, qualifier and all, in the
        subfield reserved for the number. The fixtures are kept as a
        pair because that difference is the point; the assertions below
        are on the markup, not on what the parser makes of it.
        """
        assert has_subfield(fields("commentators_bible_lc", "020"), "q")
        assert not has_subfield(fields("commentators_bible_nli", "020"), "q")

    def test_the_parser_reconciles_the_pair(self):
        """Both halves yield the same ISBNs and keep both qualifiers."""
        from sources.marc import parse_record

        lc, nli = (
            parse_record(
                extract_marc_records(load(f"commentators_bible_{c}"))[1][0]
            )
            for c in ("lc", "nli")
        )

        assert lc["isbn"] == nli["isbn"] == "9780827609426"
        assert lc["isbns"][0]["qualifier"] == "v. 1"
        # Square brackets mark a value the cataloger supplied rather
        # than transcribed, so they are kept.
        assert nli["isbns"][0]["qualifier"] == "v. [1]"
        assert nli["invalid_isbns"] == ["0827608979"]

    def test_one_record_can_carry_the_isbn_of_every_volume(self):
        # A single bibliographic record standing for a whole set: six
        # 020s, one per volume, which is where the enumeration lives
        # when no series field carries it.
        assert len(fields("commentators_bible_nli", "020")) >= 5

    def test_the_work_set_names_its_part_in_a_uniform_title(self):
        name = "miqraot_gedolot_parallel_script_nli"
        assert has_subfield(fields(name, "130"), "p")
        assert script_tagged(name)
        assert fields(name, "830")

    def test_the_basic_contents_note_has_no_per_volume_subfields(self):
        name = "miqraot_gedolot_parallel_script_nli"
        assert not has_subfield(fields(name, "505"), "t")

    def test_analytic_entries_name_contained_works(self):
        name = "bavli_analytic_entries_nli"
        assert fields(name, "730")
        assert fields(name, "740")
        assert fields(name, "773")

    def test_one_set_is_punctuated_two_ways_in_one_record(self):
        """Why the authorized form has to win.

        This record states its series twice: transcribed in 490 with a
        spaced hyphen, and authorized in 830 with a double hyphen. The
        strings differ, the set does not. Reading 490 first would let
        two records of one set disagree about which set they are in.
        """
        from sources.marc import parse_record

        name = "miqraot_gedolot_parallel_script_nli"
        parsed = parse_record(extract_marc_records(load(name))[1][0])

        assert parsed["series_title"] != parsed["series_title_transcribed"]
        assert "--" in parsed["series_title"]
        assert " - " in parsed["series_title_transcribed"]
        assert parsed["series_traced"] is True

    def test_the_obsolete_series_statement_survives(self):
        assert fields("sapirstein_rashi_obsolete_series_lc", "440")

    def test_the_vintage_set_states_its_extent_and_nothing_else(self):
        """No ISBN, no series field: 130 and 300 are all there is."""
        name = "vilna_shas_1895_nli"
        assert fields(name, "020") == []
        assert fields(name, "490") == []
        assert fields(name, "830") == []
        assert fields(name, "130")
        assert has_subfield(fields(name, "300"), "a")

    def test_the_vintage_set_uses_both_multiscript_mechanisms(self):
        name = "vilna_shas_1895_nli"
        assert script_tagged(name)
        assert preferred_language_linked(name)
        assert fields(name, "880")
        linked = {
            (sf.text or "").split("-")[0]
            for df in fields(name, "130")
            for sf in df.findall(f"{MARC}subfield")
            if sf.get("code") == "6"
        }
        assert linked == {"880"}

    def test_the_vintage_series_is_numbered_and_links_by_control_number(
        self,
    ):
        name = "mishnah_leipzig_series_1910_nli"
        assert has_subfield(fields(name, "490"), "v")
        assert has_subfield(fields(name, "830"), "v")
        host = fields(name, "773")
        assert host
        assert has_subfield(host, "w")
        assert not has_subfield(host, "t")
        assert not has_subfield(host, "g")
