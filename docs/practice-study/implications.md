# What follows for otzar

## Test leader/19 first, because it is decisive when it is there

MARC position 19 of the leader records multipart resource level: `a`
for a set, `b` for a part with its own title, `c` for a part whose
title depends on the set. Where a catalog populates it, the three
values carry three separate and nearly exceptionless field patterns:

| leader/19 | mechanism | in this corpus |
|---|---|---|
| `c` dependent part | `773` host link plus `245 $n`/`$p` enumeration | 273 records, both present on 100% and 99% |
| `b` independent part | `490` on every record, `830` on four in five, no `773` | 57 records, `773` on none |
| `a` set record | neither mechanism | 36 records, `773` on none |

Two of those fields together are an exact test. Scored against declared
leader/19 in the catalogs that populate it, "`773` present and
`245 $n` or `$p` present" gives 272 true positives, **zero** false
positives and one false negative — precision 1.000, recall 0.996.
Neither field works alone: `773` by itself has precision 0.581, since
it equally marks an article inside a host.

This is the distinction the set work needs, declared in the record
rather than inferred from it, and it is worth testing before anything
else. It also separates the two uses of `773`, which are otherwise
indistinguishable: of 378 K10plus book records carrying `773`, 195 are
dependent parts of a multipart resource and 177 are `leader/07=a`
component parts — articles inside a host, not volumes inside a set.

## Everywhere else, no single field test works

Leader/19 is populated on 24% of K10plus books and 14% of DNB's, on one
Oxford record, and on nothing at LC or NLI. Where it is blank the
distinction is not merely harder to recover — it was never recorded,
and the remaining markers do not substitute for it:

- `773` alone conflates set volumes with articles, and runs from none
  at all at LC to 35% at K10plus. The two-field test that is exact at
  K10plus and DNB matches **0 of 2,620** books at LC, NLI and Oxford.
  Those catalogs do not express the distinction in the fields either.
- `leader/07=d` reaches 4 records out of 4,449, all at NLI. MARC
  defines it for archival units described collectively elsewhere, and
  that is what those four are.
- `800`/`810`/`811` is at or below 3% everywhere.
- `245 $n`/`$p` is 18% at K10plus and 1% at LC and NLI.

The only markers that appear at comparable rates in every catalog are
`490` (13-26%, V=0.10), `830` (10-16%, V=0.08) and `130`/`240` (6-9%,
V=0.04, the one row where the chi-square test does not reject
independence). Those are what a catalog-independent rule can rest on —
and `490` is the weakest kind of evidence, since a transcribed series
statement claims only that words appeared on a piece.

## Condition on the catalog, because it is free

Which catalog answered is known at the moment a record arrives: it is
which client returned it. Conditioning costs nothing and changes the
reading substantially. `773` is real evidence at K10plus and next to none at
Oxford. `440` is worth reading at LC and nowhere else. Absence of `830`
means something different at LC, which leaves series untraced on a book
it holds, than at DNB, which traces and links them.

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
and fails to in the other three, where it predicts the cataloging rules
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
