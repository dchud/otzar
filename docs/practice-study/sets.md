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
NLI and romanized elsewhere, since that is how each indexes. Every work
is held by at least three of them.

Three filters, each of which moved the numbers:

- **Title.** A title query returns books *about* a work as well as
  editions of it, so each record's `245` is matched against the work,
  anchored at the start. An earlier pass counted 20 NLI records for
  *Sifre* of which none was the midrash: the Hebrew ספרי also begins
  ספרי ילדים, children's books.
- **Leader/07 `m`.** The responses carry archival subunits, journal
  articles and analytic entries. An earlier pass reported 116 NLI
  records linked with `773`, most of them folios within a codex,
  sections of anthologies, and — through a loose pattern — song tracks
  on albums.
- **Publisher records.** Counted separately. Oxford's 36 apparent
  per-tractate records for *Die Mischna* are one vendor's e-book
  series: every one carries `300 $a "1 online resource"` and a `776` to
  the print edition. They are not Oxford's cataloging of a set.

What remains is 1,018 records a library created, describing an edition
of the work asked for. Sixty-six of the 110 catalog-work cells returned
the fifty-record cap, so those are records examined rather than
exhaustive counts, and query forms differ per catalog, so totals are not
comparable holdings figures between catalogs.

## One work, one record or thirty

| Work | LC | Oxford | NLI | DNB | K10plus |
|---|---|---|---|---|---|
| Entsiḳlopedyah talmudit | **2** | 2 | 12 | — | **30** |
| Torah Shelemah | 1 | — | 3 | — | **35** |
| Encyclopaedia Judaica | 9 | 7 | 4 | **44** | **42** |
| Otsar ha-Geonim | 5 | 4 | 9 | — | **17** |
| Miqraot Gedolot | 28 | 12 | — | — | 14 |
| Talmud Bavli | 36 | 5 | 8 | 11 | 19 |

*Entsiḳlopedyah talmudit* is the clearest case. LC holds it as **two**
records — the Hebrew original with extent `v. <1-27, 29-53>` and the
English translation with `v.` — where K10plus holds **thirty**, one per
volume. Some fifty volumes described twice, against thirty volumes
described thirty times.

Nothing about the work changed. What changed is the level at which each
catalog chose to describe it.

## Each side says which it is doing

A catalog describing a whole set says so in the extent statement. A
catalog describing one volume of a set says so in the leader, and links
the volume to its parent.

| Catalog | Records | Set-level extent | `505` contents | `leader/19` coded | `773` | `245 $n`/`$p` |
|---|---|---|---|---|---|---|
| LC | 321 | **63%** | 24% | 0% | 0% | 5 |
| Oxford | 96 | **59%** | 32% | 0% | 7% | 2 |
| NLI | 187 | 24% | 32% | 0% | 10% | 4 |
| DNB | 119 | 0% | 8% | **67%** | 47% | 56 |
| K10plus | 295 | 0% | 3% | **79%** | 74% | 219 |

A set-level extent — `3 v.`, `9 Bände`, or the open-ended
`v. <1-27, 29-53>` — appears on 63% of LC records and on **one** record
in 414 across the two PICA catalogs. The leader coding runs the other
way. Neither side is describing less; they are describing at different
levels, and each records the level it chose.

![Markers by catalog](figures/fig6-set-mechanisms.svg)

For otzar the practical consequence is the extent statement, because it
is the signal available from the catalogs otzar actually queries.

## The sharpest measurement: leader/19

A multipart resource can be described comprehensively, one record for
the whole; analytically, a part standing alone; or as a whole together
with its linked parts — AACR2's **multilevel description**, RDA's
**hierarchical description**. MARC encodes the third in leader position
19: `a` set record, `b` part with an independent title, `c` part with a
dependent title.

**Across 22 works, leader/19 is coded on 0 of 604 records at LC, Oxford
and NLI**, and on two records in three at DNB and K10plus.

The rule behind it is old and blunt. LCRI 13.6: *do not employ the
technique of multilevel description in any case*.[^lcri136] The RDA-era
guidance continues not to create hierarchical descriptions.[^lcpcc]

Where it is coded, the value predicts the rest of the record almost
without exception:

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

This is the cleanest result in the study, and its reach is narrow. Of
the three sources otzar queries today, only DNB codes the position, and
DNB is reached only by ISBN lookup, not by the title cascade. K10plus,
where the coding is strongest, is not yet a source.

![Records coding leader/19 by work](figures/fig7-declared-by-work.svg)

## The divide has not moved

RDA was implemented in 2013 and fewer than a third of corpus records
declare it, so a rule change is not what produced this. Two time axes
are available and they disagree.

| Book published | PICA | coded | Anglo | coded |
|---|---|---|---|---|
| before 1970 | 640 | 28% | 866 | **0** |
| 1970–89 | 124 | 31% | 250 | **0** |
| 1990–2004 | 371 | 13% | 428 | **0** |
| 2005–12 | 194 | 13% | 278 | **0** |
| 2013 onward | 498 | 14% | 786 | 1 |

| Record created | PICA | coded | Anglo | coded |
|---|---|---|---|---|
| before 1990 | 12 | 33% | 509 | **0** |
| 1990s | 212 | 12% | 316 | **0** |
| 2000s | 263 | 20% | 665 | **0** |
| 2010–13 | 60 | 25% | 96 | **0** |
| 2014 onward | 1,282 | 20% | 1,001 | 1 |

The first appears to show PICA coding halving after 1990. **The second
shows no such fall**, and the second is the one that speaks to
cataloging: a rate that moves with the age of the book and not with the
age of the record describes what a library acquired from each period.
The apparent change is not there.

Both axes agree on the other side, and neither shows anything: zero
across every bin, including 866 books published before 1970 and 509
records created before 1990.

Two limits. `008/00-05` records when a record entered *that* catalog, so
migration or union-catalogue transfer may overwrite it, which is the
likely reason only 12 PICA records date before 1990. And the most
recent bin holds half the corpus in both tables.

## How good is this evidence

**Strong for the absence.** Zero across 604 records, 22 works and three
institutions, agreeing with a published rule interpretation and stable
on two time axes. Oxford and NLI both run Alma, so they are not three
independent systems; LC answers through an unrelated Z39.50 gateway,
and records demonstrably move between these catalogs through shared
cataloging.[^shared]

**Weaker for the presence.** DNB and K10plus both run PICA, and
leader/19 is reportedly system-generated rather than keyed by a
cataloger.[^gen] Their agreement may be one export routine rather than
two institutions choosing the same thing — which would make the coded
side a fact about software and the uncoded side a fact about practice.

**One thing this survey does not show.** LC's own rule interpretation
says LC analyzes and classes dependent-titled parts separately, giving
each a record with the comprehensive title as common title — `245 $a`
plus `$n`/`$p` in MARC.[^lcri] Five such records appear among LC's 321.
Either this material falls under the stated exceptions, or those
records lie outside the responses this survey saw. Unresolved, and the
first thing to check before relying on the comprehensive-description
reading.

## What follows for otzar

**Expect one-to-many correspondence.** The same encyclopedia is two
records from LC and thirty from K10plus. An identity rule assuming
records correspond one-to-one across sources will be wrong on the
material otzar exists to catalogue. This is a data-model consequence,
not a parsing rule.

**Read the extent statement, including its open-ended forms.** It is
the signal available from the catalogs otzar queries today, on 63% of
LC records here. Open-ended forms — `v.`, `v. <1-27>` — count: an
earlier version of this study missed 168 LC records by requiring a
leading digit.

**Parse `505` for volume lists.** Where these catalogs describe a set
comprehensively the parts are in the contents note: 78 records at LC,
61 at NLI, 31 at Oxford.

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
