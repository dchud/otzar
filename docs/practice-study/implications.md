# What follows for otzar

Each practice names the pattern it rests on and how strong that pattern
is. A weak pattern earns a cautious practice.

## Expect a set as two records or as thirty

*From [pattern 1](sets.md). Strong.*

The [set survey](sets.md) asked five catalogs for 22 multi-volume works.
LC describes *Entsiḳlopedyah talmudit* in two records carrying
open-ended set-level extents, one per publication; K10plus holds
**thirty-one**, each coded. *Encyclopaedia Judaica* is 41 coded
records at DNB and 42 at K10plus, against 10 at LC.

Any identity rule assuming records correspond one-to-one across sources
will be wrong on precisely the material otzar exists to catalogue. That
is a data-model consequence and it belongs in the design before the
matching rules are written.

## Read leader/19 where it arrives, which is not most places

*From [pattern 1](sets.md). Strong for its absence, weaker for its
presence, and narrow in reach.*

Of the three sources otzar queries today, only DNB codes leader/19, and
DNB is reached by ISBN lookup rather than by the title cascade. K10plus,
where coding is strongest, is not yet a source. This is the study's
cleanest measurement and its least immediately actionable one.

Leader/19 records the level at which a multipart resource is described:
`a` set, `b` part with an independent title, `c` part with a dependent
title. Coded, it predicts the rest of the record — `c` comes with `773`
and `245 $n`/`$p` on 272 of 273 such records in the corpus, `b` with
`490` always and `830` usually and `773` never.

It will arrive from K10plus and DNB. Across 22 works held by LC, Oxford
and NLI it is coded on **0 of 604** records, which is what LC and PCC
practice of not creating hierarchical descriptions predicts.

## Absence of a link is not absence of a set

*From [pattern 1](sets.md). Strong.*

A record from LC, Oxford or NLI with no `773` and no leader/19 may still
describe a whole multi-volume set. The signal is the extent: 61% of LC
records and 50% of Oxford's carry a set-level extent, and the
open-ended forms matter as much as the numbered ones — `v.`,
`v. <1-27, 29-53>`. An earlier version of this study missed 168 LC
records by requiring a leading digit.

Where those catalogs describe a set comprehensively, the volume list is
in `505`: 78 records at LC, 61 at NLI, 31 at Oxford.

## `773` is not one kind of evidence

*From [pattern 1](sets.md) and [pattern 3](markers.md). Strong.*

`773` carries several meanings in this material:

- At K10plus and DNB, on a record coding `leader/19=c`, it links a
  volume to its set. That is 263 and 62 records in the survey.
- At K10plus it also appears on `leader/07=a` component parts —
  articles inside a host, not volumes inside a set. The leader tells
  them apart; the field alone does not.
- At NLI it appears on analytic entries: folios within a codex,
  sections of anthologies, tracks on recordings.
- On archival and image material it is near-universal, 97% of mixed
  material, and means a component of a collection.

Read alone it will over-match. Read with `leader/06`, `leader/07` and
`leader/19` it is precise.

## Set publisher e-records aside

*From [pattern 1](sets.md). Strong.*

Thirty-one Oxford records for one work looked like per-volume
cataloging and were a vendor's e-book series: `300 $a "1 online
resource"`, a `776` to the print edition, one record per tractate. They
imitate the pattern a set-detection rule looks for without being
produced by the practice that rule is trying to detect.

## Condition on the catalog, because it is free

*From [pattern 2](signatures.md). Strong.*

Which catalog answered is known at the moment a record arrives: it is
which client returned it. Conditioning costs nothing and changes the
reading substantially. `773` is real evidence at K10plus and next to none
at Oxford. `440` is worth reading at LC and nowhere else. In the one
four-way case examined, LC left a series untraced on a book it holds
while DNB and K10plus traced and linked it; one record does not
establish a policy, but it does mean absence of `830` cannot be read
the same way at every catalog.

This is the same conclusion the catalog-variation note already records,
now with sizes attached: build per-catalog evidence weights, not
fallback chains that try one field and move to the next.

## Read the Hebrew title from a different field per catalog

*From [pattern 7](cases.md). Strong on prevalence.*

`880` prevalence in books: Oxford 62%, K10plus 23%, LC 15%, NLI 2%,
DNB under 1%. At Oxford the romanized form is in `245` and the Hebrew is in
`880`; at NLI the Hebrew is in `245` and there is no `880`.

The `$6` linkage subfield takes at least three shapes across these
catalogs for the identical fact — `245-02//r`, `245-02/(2/r` and
`245-01/Hebr/r`. A parser has to accept the occurrence number, an
optional script-identification code that may be a name or a character-set
escape, and the `/r` orientation flag.

NLI carries no parallel representation at all. Its `$9` and
`$8 PreferredLanguageHeading` mark the script of the one heading
present, and the Hebrew sits in `245`. What a parser keyed to `880`
misses at NLI is not the Hebrew but the absence of any romanized
form.

## Series identity: the evidence is unevenly recorded

*From [pattern 8](cases.md). Weak: one worked example.*

For one series across four records, the ISSN appeared once, `$w`
bibliographic-record links appeared twice pointing at four different
databases, one catalog did not trace the series at all, and the series
title differed by a typo between two of them.

Consequences for matching two records to one set:

- **An ISSN match is strong but rare.** Treat its presence as strong
  evidence and its absence as uninformative. It identifies the series
  as a serial, and a subseries may carry its own.
- **`$w` is a bibliographic record link, not an authority link.** It
  carries the control number of the series' own record in a named
  database, so `(DE-627)` and `(DE-101)` identifiers are not
  comparable. `(DE-600)`, the ZDB, appeared in both German records and
  is the only shared one seen. The authority identifier is `$0`, which
  these records use on name headings with the GND prefix `(DE-588)`.
- **Series-title string matching needs to tolerate error.** Exact
  comparison fails on a single transposed letter in a real record held
  by two major catalogs.
- **Subfield structure varies for the same title.** A subseries appears
  as `$p Quellen` in one record and as part of `$a` after a comma in
  another. Comparison has to normalise across that.

## Branch on material type with care

*From [pattern 3](markers.md). Strong.*

The same physical item is language material at one catalog and notated
music at two others. Any logic keyed to leader/06 takes different paths
for one object depending on which record it reads.

The markers themselves are material-specific in ways worth encoding:
`245$n`/`$p` reaches 41% in sound recordings against 7% in books;
`505` reaches 32%; `130`/`240` reaches 22% in notated music. Archival
and image material uses `leader/07=d` and `773` almost universally and
`490`/`830` not at all.

## Do not classify records into named treatment types

*From [pattern 2](signatures.md), qualified by [pattern 1](sets.md).*

Structure predicts declared bibliographic level in two catalogs of five
and fails to in the other three, where it predicts the descriptive
cataloging form
or the material type instead. With standard fields only, catalog,
record type and bibliographic level all score near 0.33 with
overlapping intervals — no organising principle wins.

Treatment is better handled as evidence accumulated per record, with
weights conditioned on catalog and era, than as a type a record is
sorted into.

## Copy cataloging limits what "institutional practice" means

*From [pattern 5](cases.md). Weak: one observed pair.*

Two of the five catalogs were found holding literally the same record
for one item, acquired through a shared cataloging network and
distinguished only by the local fields each appended. The clusters that
separate institutions therefore measure a mixture of independent
practice and position in that network, and the study cannot separate
the two.

This does not weaken the practical conclusion — records from different
endpoints do differ, reliably and measurably — but it does mean the
differences should not be read as five independent cataloging
traditions.

## Limits of the evidence

**The sample is stratified convenience, not random.** SRU returns
results in a server-determined order, so each stratum is the first
fifty records a server chose for that query. Sizes differ across
catalogs by a factor of 2.1 for all records and 1.8 for books.

**The era axis conflates two things.** The `008` date is when the book
was published, not when the record was made. Retrospective cataloging
puts modern records in early bins, and the study cannot separate a
change in convention from a change in the material.

**Judaica dominates.** Control strata are 747 of 5,252 records, and
adjusted mutual information between the clusters and the Judaica or
control label never exceeds 0.07 at any cut. The finding that clusters
do not track subject domain rests on much less evidence than the
findings about catalogs.

**The matched items are illustrations, not a sample.** Thirty-five
ISBNs appear in more than one catalog. The six shown demonstrate
mechanisms the aggregate tables measure; they do not independently
estimate anything. All six are single-volume books, which is why the
[set survey](sets.md) exists.

**The set survey is a convenience sample of works, chosen by hand.**
The 22 works were picked as the multi-volume works a Torah-study
collection is built from. A different list would give different
figures. What the survey establishes is that the two treatments both
occur, widely, on works every catalog holds — not their prevalence in
any population.

**LC's own rule interpretation is not visible in the survey.** It says
LC analyzes and classes dependent-titled parts separately, giving each
a record with the comprehensive title as common title, which in MARC is
`245 $a` plus `$n`/`$p`. Five such records appear among LC's 321 here.
Either the material falls under the stated exceptions or those records
lie outside the responses this survey saw, and that is unresolved.

**Several survey cells hit the fifty-record response cap**, so those
counts are records examined rather than exhaustive. The zero for
`leader/19` across LC, Oxford and NLI is a zero among 1,180 records
examined, not a proof that no such record exists anywhere in those
catalogs.

**Two catalogs are absent for avoidable reasons.** A UK union catalog
refused every request from this network, and one large research
library's Alma institution code could not be resolved. Their inclusion
would test the copy-cataloging finding directly.

**The clustering choices are post hoc.** The number of clusters was
chosen after seeing the results, stability was assessed at one cut
only, and the per-catalog table reports the best cut for each catalog
rather than a single cut for all. Each of those inflates the figures
reported.

**The bootstrap holds the partition fixed.** Intervals on adjusted
mutual information resample the records against a clustering computed
once on the whole corpus, so they describe the stability of the score
and not the variability of the clustering itself.

**Only three systems underlie the five catalogs.** NLI and Oxford run
Alma, DNB and K10plus run PICA, and LC answers through a Z39.50
gateway. The comparison has five institutions but fewer independent
pieces of software than that.

**One control stratum is books by construction.** The DNB control was
drawn with `MAT=books`, which is why 739 of 779 DNB records are
language material.

**Interval estimates assume independent records.** Records reached
through one query are not fully independent — a catalog may return
several volumes of one work — so the Wilson and bootstrap intervals are
somewhat narrower than the truth.

## Reproducing this

The corpus is regenerable: the query axes are language, subject,
publisher and year, run against the five endpoints named in the
[overview](index.md), 50 records per query, deduplicated on `003`
plus `001`. Requests were spaced at least four seconds per host.



