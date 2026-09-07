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

**A set arrives as one record or as many, depending on the catalog.**
The two PICA catalogs, K10plus and DNB, make a record per volume and
declare it in leader/19, multipart resource record level. LC, NLI and
Oxford make one record for the whole set, with the volume count in
`300 $a` and the parts in `505` — 3.3–6.2% of their books carry such a
count, against 0–0.5% at the two PICA catalogs. The same eight-volume
commentary reaches otzar as nine records or as one.

**Where leader/19 is used, the three values carry three separate
mechanisms.** Dependent parts take `773` and `245 $n`/`$p` on 272 of
273 records; parts with independent titles take `490` always and `830`
usually and `773` never; set records take neither, though they may
carry a series statement of their own. Two cautions: the two catalogs
that populate it are the two running PICA, so this is one family of
export software being internally consistent rather than two traditions
agreeing, and the rule was read from and scored against the same
records.

**The relationship is expressed in at least three idioms.** The
leader/19 mechanism at the PICA catalogs; a set-level record at LC,
NLI and Oxford; and a monograph-level link at NLI, where 25 records use
Alma's `773 $w`/`$4 ANA`/`$4 UP` form. A rule keyed to one misses the
other two.

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

**The clustering does not recover multipart level at all.** Scored
against the corpus-wide partitions and restricted to the two catalogs
that declare it, adjusted mutual information is **0.000**: all 287
dependent-part records fall inside the single largest cluster. Fresh
partitions of K10plus alone reach 0.20–0.25. That does not contradict
the exact test — a dependent part differs from an ordinary book on two
features out of 442, which is not enough to move a partition — but the
records do not sort on it.

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
