# How catalogs describe a set

**Pattern 1. The same multi-volume work reaches a reader as one record
from some catalogs and as thirty from others. Which it will be is
predictable from the catalog, and each side signals what it is doing —
but not in the same field.**

This chapter is about the correspondence problem before it is about any
particular field. A rule that assumes one record per work will be wrong
on this material, and the wrongness is not random.

## The survey

Twenty-two multi-volume works a Torah-study collection is built from —
Talmud Bavli, Miqraot Gedolot, Shulhan Arukh, Mishneh Torah, Zohar and
seventeen others — asked of all five catalogs by title, in Hebrew at
NLI and romanized elsewhere, since that is how each indexes. Each query
returned at most fifty records.

Counting the responses takes the chain of filters described below, and
none of them has been scored against records a person has read and
labeled. How many editions they drop and how many other records they
admit is not known, and changing any one of them moves every count. The
survey's tables — records per work and catalog, and the rate of each
signal per catalog — are withheld until the filters are scored against
a hand-labeled sample of the responses, and the published
[`set-survey.csv`](data.md) is provisional.

What this chapter reports holds without the filters: the pattern, two
works checked record by record, and which catalogs use which signal.

## The filters, and where they fail

- **Title.** A title query returns books *about* a work as well as
  editions of it, so each record's `245` is matched against the work.
  The match is anchored at the start of the title proper, because a
  work name appearing mid-title usually belongs to a book about it; an
  edition prefix may precede the name, and the name is also sought in
  `245 $b`. The filter fails in both directions. Held too loosely, it
  admits other books: the Hebrew ספרי, for *Sifre*, also begins ספרי
  ילדים, children's books. Held too strictly, it drops editions: a
  stricter version reported no K10plus records for *Ein Yaakov* while
  the response held records titled *Sefer ʿEn Yaʿaḳov 5*, and none at
  NLI for *Miqraot Gedolot*, whose name sits in `245 $b` there. Each
  correction in one direction risks the other.
- **Leader/07 `m`.** The responses carry archival subunits, journal
  articles and analytic entries — folios within a codex, sections of
  anthologies, and, through a loose title pattern, song tracks on
  albums. Only monographs are kept.
- **Publisher records.** Oxford's apparent per-tractate records for
  *Die Mischna* are one vendor's e-book series: every one carries
  `300 $a "1 online resource"` and a `776` to the print edition. They
  are not a library's cataloging of a set. The filter sets aside
  records whose extent reads "online resource", which describes the
  carrier rather than who made the record, so it is a heuristic for
  publisher records and not a test for them.
- **The response cap.** Many work-and-catalog cells returned the full
  fifty records, so their counts are floors. Query forms differ per
  catalog, so totals are not comparable holdings figures between
  catalogs.

## One work, one record or thirty

*Entsiḳlopedyah talmudit* is the clearest case. LC holds two records
with an open-ended set-level extent — the Hebrew original at
`v. <1-27, 29-53>` and the English translation at `v.` — each
describing a whole multi-volume publication in one record. K10plus
answers with **thirty** records titled *Entsiḳlopedyah talmudit*, each
describing a single volume and every one coded as a dependent part and
linked to the set, in a response cut off at the fifty-record cap.

*Encyclopaedia Judaica* divides the same way. LC's records count a
whole edition in the extent — `10 v.`, `16 v.`, `22 v.` — and code
nothing in leader/19. DNB and K10plus between them describe the same
editions volume by volume, each volume record coded as a dependent part
and linked to its set with `773`.

Nothing about either work changed. What changed is the level at which
each catalog chose to describe it.

## Each side says which it is doing

A catalog describing a whole set says so in the extent statement. A
catalog describing one volume of a set says so in the leader, and links
the volume to its parent.

Leader/19 is coded only at the two PICA catalogs, DNB and K10plus. A
set-level extent — `3 v.`, `9 Bände`, or the open-ended
`v. <1-27, 29-53>` — is the signal of the three Anglo-American
catalogs, LC, Oxford and NLI, and is rare at the PICA pair. Neither
side is describing less; they are describing at different levels, and
each records the level it chose.

For otzar the practical consequence is the extent statement, because it
is the signal available from the catalogs otzar actually queries.

## Leader/19: the cleanest encoding

A multipart resource can be described comprehensively, one record for
the whole; analytically, a part standing alone; or as a whole together
with its linked parts — AACR2's **multilevel description**, RDA's
**hierarchical description**. MARC encodes the third in leader position
19: `a` set record, `b` part with an independent title, `c` part with a
dependent title.

The rule behind its absence from the Anglo-American catalogs is old and
blunt. LCRI 13.6: *do not employ the technique of multilevel
description in any case*.[^lcri136] The RDA-era guidance continues not
to create hierarchical descriptions.[^lcpcc]

Where it is coded, the value predicts the rest of the record almost
without exception. This table is from the corpus rather than the
survey, because only there are enough coded records of each value to
tabulate:

| leader/19 | n | `773` | `245 $n`/`$p` | `490` | `830` |
|---|---|---|---|---|---|
| `c` part with dependent title | 273 | **100%** | **100%** | 13% | 9% |
| `b` part with independent title | 57 | 0% | 0% | **100%** | 81% |
| `a` set record | 36 | 0% | 0% | 19% | 6% |

A part whose title does not stand alone is linked to its set and
enumerated. A part with its own title is not linked at all — it is a
book that belongs to a series. The set record is the thing pointed at.
That is the rule the cataloging manuals give, visible in the records.

![What each leader/19 value carries](figures/fig8-leader19-mechanisms.svg)

This is the cleanest *encoding* in the study, and its reach is narrow.
Of the three sources otzar queries today, only DNB codes the position,
and DNB is reached only by ISBN lookup, not by the title cascade.
K10plus, where the coding is strongest, is not yet a source.

## How good is this evidence

**Strong for the absence.** The three Anglo-American catalogs do not
code leader/19 on these works, in agreement with a published rule
interpretation. They are not three independent systems: Oxford and NLI
both run Alma, LC answers through an unrelated Z39.50 gateway, and
records demonstrably move between these catalogs through shared
cataloging.[^shared]

**Weaker for the presence.** DNB and K10plus both run PICA, and
leader/19 is reportedly system-generated rather than keyed by a
cataloger.[^gen] Their agreement may be one export routine rather than
two institutions choosing the same thing. If so, the absence on the
other side may also be a fact about software rather than about
cataloging. The rule interpretation explains why LC creates no
dependent-part records; it does not explain why LC's set-level records
carry no `a`.

**One thing this survey does not show.** LC's own rule interpretation
says LC analyzes and classes dependent-titled parts separately, giving
each a record with the comprehensive title as common title — `245 $a`
plus `$n`/`$p` in MARC.[^lcri] Few such records appear in LC's
responses. Either this material falls under the stated exceptions, or
those records lie outside the responses this survey saw. Unresolved,
and the first thing to check before relying on the
comprehensive-description reading.

## What follows for otzar

**Expect one-to-many correspondence.** The same encyclopedia is two
records from LC and thirty from K10plus. An identity rule assuming
records correspond one-to-one across sources will be wrong on the
material otzar exists to catalogue. This is a data-model consequence,
not a parsing rule.

**Read the extent statement, including its open-ended forms.** It is
the signal available from the catalogs otzar queries today. Open-ended
forms — `v.`, `v. <1-27>` — count: a test that requires a leading digit
misses them, including LC's record for *Entsiḳlopedyah talmudit*.

**Parse `505` for volume lists.** Where these catalogs describe a set
comprehensively, a list of the parts, when there is one, is in the
contents note.

**Read leader/19 where it arrives**, which today means from DNB by ISBN
lookup, and from K10plus if it is added. It distinguishes a volume of a
set from an article inside a host, which `773` alone does not.

**Set publisher e-records aside first.** They imitate per-volume
cataloging and are not it.

[^lcri136]: **Not verified here.** The rule interpretation was read
    through a vendor mirror rather than from the Library of Congress
    directly. Confirming means reading LCRI 13.6 in Cataloger's Desktop
    or LC's free rule interpretation files.

[^lcpcc]: **Not verified here.** That LC and PCC practice does not
    create hierarchical descriptions comes from LC-PCC guidance reached
    through search. It is the explanation this chapter's finding fits,
    which is reason to check it rather than accept it.

[^shared]: **Inference.** Records moving between catalogs is
    established for one item in the [case chapter](cases.md), where LC
    and Oxford hold the same record, and by 41 NLI rows carrying
    `040 $aDLC`. How much of the agreement is shared records rather
    than shared practice is not measured.

[^gen]: **Not verified here.** That leader/19 is usually system
    generated comes from vendor MARC documentation, not from the MARC
    21 specification or from the two catalogs. Confirming it means
    asking DNB and K10plus how their export populates the position.

[^lcri]: **Not verified here.** The rule interpretation on analysis of
    monographic series and multipart monographs was read through a
    vendor mirror, and the exception categories it names were not
    checked against this material.
