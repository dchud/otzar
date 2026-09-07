# What follows for otzar

## A set arrives as one record or as many, depending on the catalog

The largest practical finding is not which field marks a volume. It is
that the same eight-volume commentary reaches otzar as **nine records
from K10plus and one record from LC**.[^onemany]

The two PICA catalogs, K10plus and DNB, create a record per volume and
declare it in leader/19, multipart resource record level: `a` for the
set, `b` for a part with its own title, `c` for a part whose title
depends on the set. LC, NLI and Oxford create one comprehensive record
for the set, with the extent in `300 $a` and the parts listed in `505`.
Books carrying a volume count in `300 $a` run 3.3-6.2% at the three
Anglo-American catalogs against 0-0.5% at the two PICA ones.

Anything in otzar that reconciles records across catalogs has to handle
a one-to-many correspondence, not a one-to-one one. That is a data-model
consequence, not a parsing one, and it is worth settling before the
identity rules are written.

## Where leader/19 is present, it is decisive

Where a catalog populates leader/19 the three values carry three
separate mechanisms: dependent parts take `773` plus `245 $n`/`$p`,
parts with independent titles take `490` and usually `830` and never
`773`, and set records take neither, though they may carry a `490` or
`830` of their own since a set can belong to a series.

Used as a test, "`773` present and `245 $n` or `$p` present" identifies
a declared dependent part with 272 true positives, no false positives
and one false negative. Two cautions come with that figure. The rule was
read from and scored against the same records, so it describes this
corpus rather than predicting the next. And the two catalogs are the two
running PICA — the fields are written together by one family of export
software, so this measures internal consistency of that output, not two
traditions agreeing.[^pica]

In practice the test adds nothing where leader/19 is present, since it
matches exactly the records that declare it, and it matches nothing
where leader/19 is absent. Its use is as a cross-check, and as a
fallback for PICA-derived records that reach otzar with the leader
position stripped.

## Elsewhere the distinction is expressed, but differently

It is not true that the other catalogs fail to record the relationship.
They record it in at least two other idioms:

- **A set-level record**, at LC, NLI and Oxford, with the volume count
  in `300 $a` and the parts in `505`. There is no per-volume record to
  find because none was made.
- **A monograph-level link at NLI.** Of its 108 language-material
  records carrying `773`, 25 are `leader/07=m` records using Alma's
  related-record form — `$w` pointing at a parent on 19 of them, `$4
  ANA` on 8, `$4 UP` on 6, `$g` part numbering on 10 — with some
  carrying `490`/`830` numbering for the same volume.

So a rule keyed to any one of these misses the other two. `773` alone
conflates set volumes with articles and runs from none at all at LC to
35% at K10plus. `leader/07=d` reaches 4 records out of 4,449, all at
NLI, and MARC defines it for archival units described collectively
elsewhere,[^l07d] which is what those four are. `800`/`810`/`811` is at or
below 3% everywhere.

The only markers that appear at comparable rates in every catalog are
`490` (13-26%, V=0.10), `830` (10-16%, V=0.08) and `130`/`240` (6-9%,
V=0.04, the one row where the chi-square test does not reject
independence). Those are what a catalog-independent rule can rest on —
and `490` is the weakest kind of evidence, since a transcribed series
statement claims only that words appeared on a piece.

## Condition on the catalog, because it is free

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

The same physical item is language material at one catalog and notated
music at two others. Any logic keyed to leader/06 takes different paths
for one object depending on which record it reads.

The markers themselves are material-specific in ways worth encoding:
`245$n`/`$p` reaches 41% in sound recordings against 7% in books;
`505` reaches 32%; `130`/`240` reaches 22% in notated music. Archival
and image material uses `leader/07=d` and `773` almost universally and
`490`/`830` not at all.

## Do not classify records into named treatment types

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
estimate anything.

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

[^onemany]: **Inference.** The counts behind it are real: books with a
    volume count in `300 $a` run 3.3-6.2% at LC, NLI and Oxford against
    0-0.5% at DNB and K10plus, and only the latter two declare
    per-volume records. The nine-versus-one figure is illustrative
    arithmetic, not an observed pair — the corpus holds no single set
    with its records counted on both sides. Confirming it means picking
    a known multi-volume work and counting the records each catalog
    returns for it.

[^l07d]: **Not verified here.** The MARC definition of `leader/07=d`
    comes from format documentation. Confirming it means reading the
    MARC 21 Bibliographic leader specification.

[^pica]: **Inference.** See the [marker chapter](markers.md). The
    corpus shows the two catalogs populating leader/19 are the two
    running PICA and that their records agree; the shared export
    routine is a reading of that, not a measurement. No K10plus record
    here carries `DE-101` in `040 $d`, so record ingestion is not
    evidenced either. Confirming it means reading the CBS
    PICA-to-MARC 21 export documentation or asking the agencies.
