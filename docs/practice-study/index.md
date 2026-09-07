# Cataloging practice: a study

Counting how often a field appears answers "how common is `773`". It
does not answer "what does a record carrying `773` also carry", and the
second question is the one that decides whether otzar can recognise a
bibliographic treatment rather than a field.

This study asks that second question of 5,252 MARC records from five
catalogs. It clusters records on the structure they carry, tests what
the clusters correspond to, measures how each catalog expresses the
relationship between a part and a whole, and closes with six items held
by more than one catalog, compared record by record.

## The question, stated precisely

otzar needs to decide whether two records describe one bibliographic
set. The reasoning behind its data model assumes a taxonomy of
treatments — series treatment, multipart monograph, uniform title,
analytic, set record with contents — drawn from format documentation.
That taxonomy has never been checked against records.

If the taxonomy is real, records should fall into groups whose
structure matches it, and each treatment should have a signature otzar
can test a record against. Three outcomes were possible, and all three
would be worth knowing:

1. The groups match the taxonomy, which confirms it and yields
   detectable signatures.
2. The groups cut across the taxonomy, which says the treatments are a
   cataloger's vocabulary rather than a property of records.
3. The groups correspond to the cataloging agency or the decade, which
   says variation is institutional, and that knowing where a record
   came from predicts more than reading it does.

All three hold, at different levels, and which one applies depends on
which fields are examined and which catalog answered. The first holds
more strongly than expected in the two catalogs that declare multipart
level in the leader, where the taxonomy is not imposed on the records
but stated in them.

## The corpus

136 SRU queries against five catalogs returned 5,252 unique records.

| Catalog | Records | Books | Endpoint |
|---|---|---|---|
| National Library of Israel | 1,432 | 794 | Alma SRU, `972NNL_INST` |
| K10plus (German union catalog) | 1,179 | 1,090 | `sru.k10plus.de/opac-de-627` |
| Library of Congress | 1,185 | 1,164 | `lx2.loc.gov:210/LCDB` |
| Deutsche Nationalbibliothek | 779 | 739 | `services.dnb.de/sru/dnb` |
| Bodleian Libraries, Oxford | 677 | 662 | Alma SRU, `44OXF_INST` |

"Books" counts records whose leader/06 is `a`, language material. That
column matters more than the first, for reasons the marker chapter
gives.

**No query names a work.** The draw axes are language of the material,
subject heading, publisher, and year of publication, crossed against
nine years spread from 1900 to 2022. A corpus reached by searching for
titles chosen in advance mostly recovers the shape of those searches;
these axes are chosen because they say nothing about which fields a
record carries. Query syntax differed per catalog — `alma.language`
and `alma.main_pub_date`, `pica.spr` and `pica.jah`, `dc.subject` and
`dc.date`, `SPR` and `JHR` — but the axis is the same in each.

Five strata fall outside Judaica entirely, 747 records in all: physics
and agriculture at the Library of Congress, physics at K10plus, general
monographs at DNB, English-language material at Oxford. They are a
control on whether any group that appears is a property of cataloging
or of the subject.

Two catalogs, NLI and Oxford, run the same Alma software on separate
installations. That pairing is deliberate, and the signatures chapter
turns on it. DNB and K10plus both run PICA, so the five catalogs
represent three systems rather than five.

## What a record is reduced to

Each record becomes a set of binary facts about its structure: which
fields it carries, which subfield codes appear within each field, the
value of each indicator, whether any field repeats, whether any
subfield `$6` links an alternate script, the `008` date type, and
whether the second `008` date is set, blank, or open. Facts holding for
under 2% or over 98% of records are dropped, leaving 725.

Seven facts are held out of that vector and used only to interpret the
result: which catalog answered, `040$a`, `040$e`, leader positions 06,
07 and 18, and the decade of the query that found the record. That
last one is the year asked for, not the `008` date the era chapter
uses. Leader/07 and `040$e` are the cataloger's own declaration of
treatment and convention. Putting them in the vector
would let the clustering recover them by definition instead of testing
whether the rest of the record predicts them.

Clustering is average-linkage hierarchical on Jaccard distance. Each
cut is scored by adjusted mutual information (AMI) against every
held-out label, with percentile intervals from 400 bootstrap
resamples. Proportions carry 95% Wilson intervals. Association between
a marker and a catalog is reported as Cramér's V with a chi-square
p-value. Partition stability is the mean best Jaccard recovery of each
cluster across 30 resamples at 80% of the corpus.

## What the study found

**MARC has a field for this, and where it is used it is exact.** Leader
position 19, multipart resource record level, separates a set record
from a part with its own title from a part whose title depends on the
set. The three values carry three separate mechanisms: dependent parts
take a `773` host link and `245 $n`/`$p` enumeration on 100% and 99% of
273 records across two catalogs; independent parts take `490` on all of
them and `830` on four in five, and never `773`; set records take
neither. Used as a test, `773` together with `245 $n`/`$p` predicts a
declared dependent part with precision 1.000 and recall 0.996.

**Two catalogs of five populate it.** K10plus on 24% of books, DNB on
14%, Oxford on one record, LC and NLI on none. Where it is blank the
distinction was not recorded, and the remaining evidence does not
reconstruct it — `773` alone conflates volumes of a set with articles
inside a host.

**Structure identifies the institution before the book.** With every
field included, clustering recovers which catalog answered at
AMI 0.803 (95% CI 0.795–0.812), on administrative fields that describe
a record's handling rather than its subject.

**The fingerprint is institutional, not the software.** NLI and Oxford
run the same Alma software on separate installations, and separate from
each other almost as sharply (0.790) as the five catalogs separate from
one another (0.803).

**With only standard fields, nothing dominates.** Catalog, record type
and bibliographic level all land near 0.33 with overlapping intervals.

**The clustering does not recover multipart level, and that does not
contradict the exact test.** Adjusted mutual information between the
partitions and leader/19 is 0.04 to 0.11 even within the catalogs that
declare it. The partitions do not isolate 273 records out of 1,829 as a
group; a two-field rule still identifies them without error. The two
measures answer different questions and both answers stand.

**Only `490`, `830` and `130`/`240` appear at comparable rates in every
catalog**, at 13–26%, 10–16% and 6–9%. Every other part-whole marker is
concentrated in one or two.

**The same item is catalogued as different things.** One printed
songbook is language material at NLI and notated music at LC and
K10plus, and LC's record carries a uniform title, a song-level contents
note and 18 name added entries that neither of the others has.

## How to read the rest

- [Institutional signatures](signatures.md) — the clustering results,
  the Alma comparison, and stability.
- [Part-whole markers](markers.md) — the material-type confound, the
  books-only prevalence table, and change over time.
- [Six items, side by side](cases.md) — the same book at up to four
  catalogs, with identifiers.
- [What follows for otzar](implications.md) — the design consequences,
  and the limits of the evidence.
- [The data](data.md) — the published corpus features, the query
  manifest, and the case records.
