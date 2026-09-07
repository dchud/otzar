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

MARC reserves leader position 19, *multipart resource record level*, for
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
  in `245 $n` or `$p`. Both hold on every one of the 273 such records in
  the corpus, across two independent catalogs.
- **A part with an independent title** does the opposite: no `773` at
  all, a `490` on every record, and an `830` on roughly four in five. It
  is described as its own book that belongs to a series.
- **A set record** carries neither mechanism, as the thing being pointed
  at rather than the thing pointing.

This is the taxonomy the set work assumed, and in these two catalogs it
is not a vocabulary imposed on the records — it is declared in the
leader and expressed consistently in the fields.

The converse holds too, and separates the two distinct uses of `773`.
Of the 378 K10plus book records carrying `773`, 195 are dependent parts
of a multipart resource and 177 are `leader/07=a` monographic component
parts — articles within a host, not volumes within a set. The leader
tells the two apart; the presence of `773` alone does not.

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

The clustering does not reproduce this. Adjusted mutual information
between the structural partitions and leader/19 is 0.043 to 0.110,
including within the two catalogs that declare it. Both figures are
correct and they answer different questions. Adjusted mutual
information asks whether the partitions isolate multipart parts as a
group, and they do not — 273 records out of 1,829 are absorbed into
larger clusters. The precision figure asks whether a specific two-field
test identifies them, and it does, without error. A rule can be exact
while the same evidence fails to organise a corpus.

At LC, NLI and Oxford leader/19 is blank on essentially every record.
There the distinction is not merely harder to recover — it is not
recorded. NLI's 108 book records with `773` include 79 component parts
and no declared multipart volumes at all.

The two-field test finds nothing there either: **0 of 1,164 LC books,
0 of 794 NLI books and 0 of 662 Oxford books** match it. Those catalogs
do not leave the distinction undeclared while still expressing it in
the fields. They do not express it.

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
0% everywhere else — it was made obsolete in 2008, and only LC's
unconverted legacy records carry it here. `740` is 13% at NLI and
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

`020` reproduces the ISBN adoption curve, 6% to 72%, and is the
cleanest validation available that the era axis is measuring something
real.

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
