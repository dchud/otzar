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

The answer is that all three hold, at different levels, and which one
applies depends on which fields are examined and which catalog
answered.

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

Four strata fall outside Judaica entirely: physics and agriculture at
the Library of Congress, general monographs at DNB, English-language
material at Oxford. They are a control on whether any group that
appears is a property of cataloging or of the subject.

Two catalogs, NLI and Oxford, run the same Alma software. That pairing
is deliberate, and the signatures chapter turns on it.

## What a record is reduced to

Each record becomes a set of binary facts about its structure: which
fields it carries, which subfield codes appear within each field, the
value of each indicator, whether any field repeats, whether any
subfield `$6` links an alternate script, the `008` date type, and
whether the second `008` date is set, blank, or open. Facts holding for
under 2% or over 98% of records are dropped, leaving 725.

Seven facts are held out of that vector and used only to interpret the
result: which catalog answered, `040$a`, `040$e`, and leader positions
06, 07 and 18. Leader/07 and `040$e` are the cataloger's own
declaration of treatment and convention. Putting them in the vector
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

**Structure identifies the institution, not the book.** With every
field included, clustering recovers which catalog answered at
AMI 0.803 (95% CI 0.795–0.812), on administrative fields that describe
a record's handling rather than its subject.

**The fingerprint is institutional, not the software.** NLI and Oxford
run the same Alma installation and separate from each other as sharply
as five different platforms separate from one another.

**With only standard fields, nothing dominates.** Catalog, record type
and bibliographic level all land near AMI 0.33 with overlapping
intervals. No single organising principle wins.

**The most-cited set marker barely exists in books.** `leader/07=d`,
the subunit value, appears on 4 of 4,449 language-material records
across all five catalogs. Its apparent prevalence at NLI comes almost
entirely from archival and image material.

**Only `490` and `830` are near-universal**, at 13–26% and 10–16%. Every
other part-whole marker is concentrated in one or two catalogs.

**The same item is catalogued as different things.** One sound-notation
item is language material at NLI and notated music at LC, with 19 added
name entries and a contents note at LC that NLI's record does not have.

## How to read the rest

- [Institutional signatures](signatures.md) — the clustering results,
  the Alma comparison, and stability.
- [Part-whole markers](markers.md) — the material-type confound, the
  books-only prevalence table, and change over time.
- [Six items, side by side](cases.md) — the same book at up to four
  catalogs, with identifiers.
- [What follows for otzar](implications.md) — the design consequences,
  and the limits of the evidence.
