"""Real SRU responses, kept for what each one shows about practice.

Every file under ``fixtures/marc/`` is one record as a catalog actually
sent it, trimmed to a single-record SRU envelope and otherwise unedited.
They exist because multipart works arrive in incompatible MARC
treatments, and a hand-built fixture encodes what its author expected
rather than what the catalogs do.

``docs/marc-in-practice.md`` has the survey these were drawn from,
including how often each treatment appears.

``test_marc_fixtures.py`` asserts that each file still carries the thing
it was chosen for, so a fixture cannot quietly stop earning its place and
so none of them reads as redundant to somebody tidying up.
"""

import pathlib

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "marc"

# What each was kept for. The tags listed are the ones the fixture is
# responsible for; every file carries more than its entry claims.
DEMONSTRATES = {
    "artscroll_chumash_contents_enhanced_lc": (
        "The enhanced contents note, 505 with $t per volume -- the only "
        "one of its kind in a 122-record survey. Its $g designations read "
        "'Vol, 1.', 'vol 2.' and 'vol. 3' in one field, so it is also the "
        "case against expecting consistent enumeration. Carries an "
        "ArtScroll series statement, which is a publisher's imprint "
        "rather than a work whose volumes anyone completes."
    ),
    "mishnah_berurah_880_linkage_lc": (
        "880 linkage at its richest: alternate graphic representations "
        "for 100, 240, 260, 264, 700, 710, 505, 730 and 740. This is how "
        "LC carries Hebrew, and it is the mechanism NLI does not use."
    ),
    "commentators_bible_lc": (
        "One half of a matched pair. The same work as "
        "commentators_bible_nli, same ISBN, from the other catalog: no "
        "880 and no $9, but an 020 $q qualifying the ISBN by volume."
    ),
    "commentators_bible_nli": (
        "The other half. Same work, same ISBN, and the parallel scripts "
        "arrive as sibling fields marked $9 heb and $9 lat linked by $8 "
        "PreferredLanguageHeading, with no 880 anywhere and no 020 $q. "
        "The pair is the clearest statement that the two catalogs express "
        "the same facts in different shapes."
    ),
    "miqraot_gedolot_parallel_script_nli": (
        "NLI's parallel-script mechanism on a work-set: $9 and $8 across "
        "the record, a 130 whose $p names the part, an 830 naming a "
        "series that is a work rather than an imprint, and a contents "
        "note in the basic form that 39 of 40 surveyed records use."
    ),
    "bavli_analytic_entries_nli": (
        "Analytic added entries: 730 name-title entries for the works "
        "inside the volume, 740 uncontrolled titles beside them, and a "
        "773 pointing at a host item. 773 appeared only in NLI records "
        "in the survey."
    ),
    "vilna_shas_1895_nli": (
        "The Romm Vilna Talmud, 18 volumes, Vilna 1895-1909. A set with "
        "no ISBN, no series statement and no 505 in the enhanced form -- "
        "everything the modern reading depends on is absent. Its identity "
        "rests on a 130 uniform title and its extent on 300 $a alone. It "
        "is also the record showing NLI emitting both multiscript "
        "mechanisms at once, $9 and $8 alongside a $6 pointer to an 880, "
        "and carrying a third script: a Cyrillic 246/880 pair."
    ),
    "mishnah_leipzig_series_1910_nli": (
        "A numbered monographic series from 1910 -- Schriften des "
        "Institutum Judaicum in Berlin, Nr. 38 -- and one of the few "
        "pre-1945 records carrying a 490 and 830 at all. Shows the "
        "series-statement case where the number is real and the series "
        "is not a work. Its 773 links to the host by $w control number "
        "with no $t and no $g, which is how older analytics point."
    ),
    "sapirstein_rashi_obsolete_series_lc": (
        "The obsolete 440 series statement -- one occurrence in 122 "
        "records, against an expectation that older Judaica copy would be "
        "full of it. Also an 020 $q volume qualifier and a basic contents "
        "note."
    ),
}


def load(name: str) -> str:
    """Return the raw SRU response text for a fixture by name."""
    return (FIXTURE_DIR / f"{name}.xml").read_text(encoding="utf-8")
