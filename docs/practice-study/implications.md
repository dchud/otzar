# What follows for otzar

## No single field test identifies a volume within a set

Every candidate marker is either concentrated in one or two catalogs or
thin across all of them. Restricted to books:

- `leader/07=d` reaches **4 records out of 4,449**, all at NLI. A rule
  that reads the leader to find set volumes matches essentially
  nothing. Its apparent strength at NLI is archival material.
- `773` is 35% at K10plus, 12-14% at DNB and NLI, and effectively
  absent at LC (0 of 1,164) and Oxford (6 of 662).
- `800`/`810`/`811` is at or below 3% everywhere.
- `245$n`/`$p` is 18% at K10plus and 1% at LC and NLI.

The only markers that behave consistently across institutions are `490`
(13-26%, V=0.10), `830` (10-16%, V=0.08) and `130`/`240` (6-9%,
V=0.04, not distinguishable from independence). Those are the ones a
catalog-independent rule can rest on — and `490` is the weakest kind of
evidence, since a transcribed series statement claims only that words
appeared on a piece.

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

NLI expresses the same information a fourth way, with `$9` carrying a
language code and `$8 PreferredLanguageHeading` on the heading itself.
Anything treating `880` as *the* mechanism for vernacular script will
read NLI records as having no Hebrew.

## Series identity: the evidence is unevenly recorded

For one series across four records, the ISSN appeared once, `$w`
authority links appeared twice pointing at four different authority
files, one catalog did not trace the series at all, and the series
title differed by a typo between two of them.

Consequences for matching two records to one set:

- **An ISSN match is strong but rare.** Treat its presence as decisive
  and its absence as uninformative.
- **`$w` links are per-authority-file.** `(DE-627)` and `(DE-101)`
  identifiers are not comparable; `(DE-600)` appeared in both German
  records and is the only cross-walkable one seen.
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
relevance-ranked results, so each stratum is the first fifty records a
server chose for that query. Sizes differ across catalogs by a factor
of nearly two.

**The era axis conflates two things.** The `008` date is when the book
was published, not when the record was made. Retrospective cataloging
puts modern records in early bins, and the study cannot separate a
change in convention from a change in the material.

**Judaica dominates.** Control strata are 447 of 5,252 records, so the
finding that clusters do not track subject domain rests on much less
evidence than the findings about catalogs.

**The matched items are illustrations, not a sample.** Thirty-five
ISBNs appear in more than one catalog. The six shown demonstrate
mechanisms the aggregate tables measure; they do not independently
estimate anything.

**Two catalogs are absent for avoidable reasons.** A UK union catalog
refused every request from this network, and one large research
library's Alma institution code could not be resolved. Their inclusion
would test the copy-cataloging finding directly.

**Interval estimates assume independent records.** Records reached
through one query are not fully independent — a catalog may return
several volumes of one work — so the Wilson and bootstrap intervals are
somewhat narrower than the truth.

## Reproducing this

The corpus is regenerable: the query axes are language, subject,
publisher and year, run against the five endpoints named in the
[overview](index.md), 50 records per query, deduplicated on `003`
plus `001`. Requests were spaced at least four seconds per host.
