# Part-whole markers

The set work needs one question answered: when a record describes part
of something larger, how does it say so? This chapter measures eighteen
candidate markers across the five catalogs, across the six kinds of
material with at least 80 records, and across five publication eras.

## The material-type confound comes first

Measured across all 5,252 records, the markers vary widely. Measured
within a kind of material, most of that variation disappears. Prevalence by
leader/06:

| Marker | language | mixed | musical sound | notated music | 2-D image | manuscript |
|---|---|---|---|---|---|---|
| n | 4,449 | 292 | 199 | 103 | 82 | 26 |
| leader/07=d subunit | **0%** | **95%** | 0% | 0% | **93%** | 27% |
| 773 host item | 13% | **97%** | 40% | 20% | **100%** | 8% |
| 490 series statement | 21% | 0% | 8% | 21% | 0% | 0% |
| 830 series entry | 13% | 0% | 6% | 15% | 0% | 0% |
| 245 `$n`/`$p` | 7% | 7% | **41%** | 7% | 0% | 15% |
| 505 contents | 7% | 0% | **32%** | 21% | 0% | 0% |
| 130/240 uniform title | 7% | 0% | 2% | **22%** | 0% | 4% |
| 880 linked script | 19% | 0% | 1% | 1% | 0% | 8% |
| 020 ISBN | 44% | 0% | 1% | 12% | 0% | 0% |

![Marker prevalence by material type](figures/fig5-material-types.svg)

Two mechanisms are visible, and they do not overlap:

- **Archival and image material** uses subunit records and host-item
  links. Mixed material is 95% `leader/07=d` and 97% `773`; 2-D image
  material is 93% and 100%. Neither carries `490` or `830` at all.
- **Books** use series statements. Language material is 21% `490` and
  13% `830`, and under 1% `leader/07=d`.

Sound recordings sit apart again: `245$n`/`$p` at 41% and `505` at 32%,
both far above books. That is consistent with a recording being
described as a numbered part with an enumerated contents note, though
these are nearly all NLI sound-archive records, so the pattern may
belong to that collection rather than to the material.

MARC defines `leader/07=d` for a part of a collection described
collectively elsewhere, and the corpus shows it used exactly that way.
The confound is severe enough to invert a conclusion drawn without it:
measured across all material, `leader/07=d` looks like a heavy NLI
practice at 25% of NLI records. Restricted to books it falls to 4
records out of 794 at NLI and none at all in the other four catalogs.
The NLI subunit records are archival items reached by a language-based
query, not volumes of book sets. Every table below is
therefore restricted to language material.

## The field MARC defines for the job

MARC defines leader position 19, *multipart resource record level*, for
exactly the distinction the set work needs: `a` for a set record, `b`
for a part with an independent title, `c` for a part with a dependent
title. Two catalogs populate it. Three leave it blank.

| Catalog | Books | `a` set | `b` independent part | `c` dependent part | Populated |
|---|---|---|---|---|---|
| K10plus | 1,090 | 26 | 44 | 195 | 24% |
| DNB | 739 | 10 | 13 | 78 | 14% |
| Oxford | 662 | 0 | 1 | 0 | under 1% |
| LC | 1,164 | 0 | 0 | 0 | 0% |
| NLI | 794 | 0 | 0 | 0 | 0% |

The two catalogs that populate it are the two that run PICA. They are
not independent witnesses: whatever writes leader/19 in a PICA-to-MARC
export writes the accompanying fields as well, so the consistency below
is the consistency of one family of export software, not two cataloging
traditions agreeing.

Where it is populated, each value carries a distinct and nearly
exceptionless field pattern:

| leader/19 | n | 773 | 830 | 490 | 245 `$n`/`$p` | 800/810/811 |
|---|---|---|---|---|---|---|
| `c` dependent part (K10plus) | 195 | **100%** | 9% | 14% | **99%** | 1% |
| `c` dependent part (DNB) | 78 | **100%** | 8% | 8% | **100%** | 0% |
| `b` independent part (K10plus) | 44 | 0% | 81% | **100%** | 0% | 18% |
| `b` independent part (DNB) | 13 | 0% | 76% | **100%** | 0% | 38% |
| `a` set record (K10plus) | 26 | 0% | 0% | 11% | 0% | 0% |
| `a` set record (DNB) | 10 | 0% | 20% | 40% | 0% | 10% |
| blank (K10plus) | 825 | 22% | 7% | 22% | 0% | 3% |
| blank (DNB) | 638 | 2% | 13% | 26% | 0% | 1% |

The three values do not merely differ in degree. They use different
mechanisms and do not overlap:

- **A part with a dependent title** — volume 3 of a set, whose own title
  does not stand alone — is linked to its host with `773` and enumerated
  in `245 $n` or `$p`. Both hold on 272 of the 273 such records.
- **A part with an independent title** does the opposite: no `773` at
  all, a `490` on every record, and an `830` on roughly four in five. It
  is described as its own book that belongs to a series.
- **A set record** carries neither of those, as the thing being pointed
  at rather than the thing pointing. It may still carry `490` or `830`,
  on 12% and 0% of K10plus set records and 40% and 20% of DNB's, since
  a set can itself belong to a series.

This is the taxonomy the set work assumed, and in these two catalogs it
is declared in the leader rather than inferred from the fields. What it
is not is independent confirmation that the taxonomy describes
cataloging in general: two PICA catalogs agreeing about PICA output is
one observation, not two.

The converse holds too, and separates the two distinct uses of `773`.
Of the 378 K10plus language-material records carrying `773`, 195 are
dependent parts of a multipart resource, 177 are `leader/07=a`
monographic component parts — articles within a host, not volumes
within a set — and 6 are offprints and items in digitised collections.
The leader tells them apart; the presence of `773` alone does not.

### The two fields together are an exact test, where they occur

Treating "`773` present **and** `245 $n` or `$p` present" as a test for
a declared dependent part, scored against leader/19 in the two catalogs
that populate it:

| | |
|---|---|
| True positives | 272 |
| False positives | **0** |
| False negatives | 1 |
| Precision | **1.000** |
| Recall | **0.996** |

Neither field does this alone. `773` by itself has precision 0.581,
because it is equally the mechanism for an article inside a host.
`245 $n`/`$p` by itself reaches 0.996, and the pair removes its last
error.

The clustering does not reproduce this, and the figures are worth
stating precisely because they are easy to conflate.

| What was scored | AMI with leader/19 |
|---|---|
| Corpus-wide partitions, all 5,252 records | 0.043–0.089 |
| Corpus-wide partitions, restricted to K10plus and DNB | **0.000** |
| Fresh partitions of K10plus and DNB together | 0.033–0.100 |
| Fresh partitions of K10plus alone | 0.204–0.248 |

On the corpus-wide partitions all 287 dependent-part records — 273 books
and 14 others — fall inside the single largest cluster, at every cut and
under both feature sets. Within the two catalogs that declare the value,
those partitions carry no information about it at all.

Both that and the exact test are true, and they answer different
questions. A dependent-part record differs from an ordinary book on two
features out of 442, `tag:773` and `sub:245$n`/`$p`, and matches it on
everything else, so it does not move a Jaccard partition. Monographic
component parts differ on many features — no `020`, no `300 $c`, no
`490` — which is why a K10plus-only clustering scores 0.558 on
bibliographic level and 0.204 on multipart level at the same cut. A
two-field rule can be exact while the same two features fail to organise
a corpus.

The rule was also read from and scored against the same 1,829 records.
There is no held-out set, so 1.000 is a description of this corpus, not
an estimate of performance on the next one.

At LC, NLI and Oxford leader/19 is blank on essentially every record,
and the two-field test finds nothing there: 0 of 1,164 LC books, 0 of
794 NLI books, 0 of 662 Oxford books.

That is not the same as the distinction being absent. Those catalogs
describe a multipart monograph differently — as one comprehensive record
for the set, with the extent in `300` and the parts listed in `505`,
rather than as a set record plus one record per volume. Counting books
whose `300 $a` carries a volume count:

| Catalog | Books with a volume count in `300 $a` |
|---|---|
| Oxford | 41 of 662 (6.2%) |
| LC | 57 of 1,164 (4.9%) |
| NLI | 26 of 794 (3.3%) |
| K10plus | 5 of 1,090 (0.5%) |
| DNB | 0 of 739 (0%) |

The relationship is inverted. Where the PICA catalogs create a record
per volume and declare it, the Anglo-American catalogs create one record
for the whole set. The same eight-volume commentary arrives as nine
records from K10plus and as one from LC.

NLI also links at the monograph level, in a third idiom again. Of its
108 language-material records carrying `773`, 79 are component parts and
4 are archival subunits — and the remaining 25 are `leader/07=m`
records using Alma's related-record form, `773` with `$w` pointing at a
parent record on 19 of them, `$4 ANA` on 8 and `$4 UP` on 6, and `$g`
part numbering on 10. Some of those carry `490`/`830` numbering for the
same volume.

So the distinction is expressed in at least three ways across the five
catalogs, and only one of them is the leader/19 mechanism.

## Books only: prevalence by catalog

4,449 records: DNB 739, K10plus 1,090, LC 1,164, NLI 794, Oxford 662.
Percentages with 95% Wilson intervals; V is Cramér's V for the
association between the marker and the catalog.

| Marker | DNB | K10plus | LC | NLI | Oxford | V |
|---|---|---|---|---|---|---|
| leader/07=d subunit | 0% | 0% | 0% | 1% | 0% | 0.06 |
| leader/07=a component part | 2% | 16% | 0% | 10% | 0% | 0.28 |
| 773 host item | 12% | 35% | 0% | 14% | 1% | 0.40 |
| 490 series statement | 26% | 24% | 20% | 19% | 13% | **0.10** |
| 830 series entry | 14% | 11% | 10% | 16% | 15% | **0.08** |
| 490 ind1=1 traced | 16% | 14% | 10% | 16% | 13% | **0.07** |
| 130/240 uniform title | 6% | 6% | 7% | 9% | 7% | **0.04** |
| 800/810/811 name-title | 2% | 3% | 2% | 1% | 0% | 0.08 |
| 730 uniform added | 2% | 3% | 1% | 3% | 2% | 0.06 |
| 440 obsolete series | 0% | 0% | 10% | 0% | 0% | 0.28 |
| 245 `$n`/`$p` | 11% | 18% | 1% | 1% | 2% | 0.29 |
| 505 contents | 0% | 5% | 13% | 10% | 5% | 0.17 |
| 740 added title | 0% | 0% | 4% | 13% | 3% | 0.25 |
| 246 variant title | 16% | 27% | 12% | 41% | 37% | 0.26 |
| 880 linked script | 0% | 23% | 15% | 2% | 62% | 0.51 |
| 300 `$c` dimensions | 64% | 19% | 88% | 67% | 90% | 0.57 |
| 020 ISBN | 69% | 26% | 56% | 37% | 33% | 0.32 |

![Forest plot of marker prevalence](figures/fig2-forest.svg)

### The markers that travel

Three markers have a catalog effect small enough to rely on. `830`
(10-16%, V=0.08), traced `490` (10-16%, V=0.07), and `130`/`240`
uniform title (6-9%, V=0.04) vary by a few points across five
institutions. The uniform-title row is
the only one in the table where the chi-square test does not reject
independence (p=0.15). That is a failure to detect a difference, not a
demonstration that none exists.

`490` itself, at 13–26% and V=0.10, is the most widely used part-whole
marker and among the most consistent. It is also the weakest evidence:
a transcribed series statement asserts that words appeared on a piece,
not that a set exists.

### The markers that do not travel

`773` runs from none at all at LC (0 of 1,164) and 6 records at Oxford
to 35% at K10plus. `245$n`/`$p` runs from 1% at LC and NLI to 18% at
K10plus. `440` is 10% at LC and
0% everywhere else. It was made obsolete in 2008 and only LC's
unconverted legacy records carry it here; the German catalogs never
emitted it, since their MARC output postdates the change, so their zero
is format history rather than a cataloging choice. `740` is 13% at NLI and
essentially absent at DNB and K10plus.

`880` is the sharpest division among the part-whole and script markers
(V=0.51), and it is not about sets at all: 62% at Oxford, 23% at
K10plus, 15% at LC, 2% at NLI, and 2 records out of 739 at DNB. Oxford
romanizes into the main fields and links the Hebrew in `880`. NLI
catalogs in Hebrew directly and has nothing to link. The same book has
its Hebrew title in a different MARC field depending on which catalog
answered.

`300$c` is sharper still (V=0.57), and is house style: K10plus
records dimensions on 19% of books where LC and Oxford record them on
88% and 90%.

`800`/`810`/`811`, the traced name-title series added entry, is at or
below 3% everywhere. Whatever otzar does about sets, this is not the
field the material uses.

## Change over publication era

Restricted to books, binned on the first `008` date.

| Marker | before 1940 | 1940-69 | 1970-89 | 1990-2004 | 2005-25 |
|---|---|---|---|---|---|
| n | 537 | 969 | 374 | 799 | 1,756 |
| 490 series statement | 10% | 15% | 17% | 19% | **29%** |
| 830 series entry | 7% | 7% | 12% | 13% | **17%** |
| 773 host item | 14% | 11% | 26% | 12% | 12% |
| 440 obsolete series | 0% | 1% | **9%** | 6% | 1% |
| 505 contents | 3% | 4% | 3% | 4% | **13%** |
| 246 variant title | 19% | 17% | 14% | 24% | **34%** |
| 245 `$n`/`$p` | 9% | 8% | 8% | 6% | 5% |
| 740 added title | 5% | 6% | 10% | 5% | 1% |
| 880 linked script | 23% | 24% | 21% | 12% | 18% |
| 020 ISBN | 6% | 8% | 30% | 59% | **72%** |

![Marker prevalence over time](figures/fig3-time-trends.svg)

Series statements rise steadily, and the rise is not sampling noise:
`490` moves from
10% (Wilson 8–13) to 29% (27–31), intervals nowhere near overlapping,
and `830` from 7% (5–10) to 17% (15–19).

`440` rises and falls: absent before 1940, 9% for material published
1970-89, back to 1% in the most recent bin. The field was made
obsolete in 2008, though the caveat below applies — this axis is the
era of the book, not of the record.

`020` reproduces the ISBN adoption curve, 6% to 72%, which is the
closest thing here to a check that the era axis measures something
real. The 6% on imprints published before 1940 is a reminder of that
axis's limit rather than a contradiction: ISBNs did not exist before
1967, and those rows are reprints, facsimiles and records whose `008`
date refers to an original the item reproduces.

One apparent trend is absent. `773` does not decline; it is flat
except for a bump in the 1970-89 bin. Pooled across all material it
looks like a steep fall, and that is an artifact of the changing
material mix across bins. `880` moves within a narrow band in both
views and shows no trend either way.

![Per-catalog trends](figures/fig4-time-by-catalog.svg)

The per-catalog view shows the rise is not shared evenly. K10plus
carries `490` on roughly a quarter of books from 1940 onward. DNB
climbs from 3% before 1940 to 33% in the most recent bin, and LC from
9% to 36%. Oxford falls to nothing in the middle bins before reaching
28%.

One caveat governs this whole section. The `008` date is when the
*book* was published, not when the *record* was made. A 1905 imprint
catalogued in 1998 under then-current rules appears in the first bin.
The era axis therefore mixes a genuine change in cataloging convention
with the era of the material, and cannot separate them.
