# Cataloging practice: a study

otzar needs to decide whether two records describe one bibliographic
set. The reasoning behind its data model assumes a taxonomy of
treatments — series treatment, multipart monograph, uniform title,
analytic, set record with contents — drawn from format documentation
and never checked against records.

This study checks it, and finds that the answer is not one thing.
Several patterns are present at once. They are reported separately
below rather than reconciled, because they disagree with each other in
ways that matter: one says the unit of variation is a cataloging
tradition, another says it is the individual institution, and a third
says both are swamped by the type of material. All three are supported.

## Two bodies of evidence

**A stratified corpus of 5,252 records** drawn from five catalogs along
axes that say nothing about which fields a record carries — language,
subject heading, publisher and year of publication, crossed against
nine years from 1900 to 2022. No query names a work. Five strata, 747
records, fall outside Judaica as a control.

| Catalog | Records | Books | Endpoint |
|---|---|---|---|
| National Library of Israel | 1,432 | 794 | Alma SRU, `972NNL_INST` |
| K10plus (German union catalog) | 1,179 | 1,090 | `sru.k10plus.de/opac-de-627` |
| Library of Congress | 1,185 | 1,164 | `lx2.loc.gov:210/LCDB` |
| Deutsche Nationalbibliothek | 779 | 739 | `services.dnb.de/sru/dnb` |
| Bodleian Libraries, Oxford | 677 | 662 | Alma SRU, `44OXF_INST` |

**A targeted survey of 22 multi-volume works** — Talmud Bavli, Miqraot
Gedolot, Shulhan Arukh, Mishneh Torah, Zohar, Mishnah Berurah and
sixteen others — asked of all five catalogs by title. Every work is
held by at least three of them.

The two disagree, and the disagreement is one of the findings. A corpus
drawn on language and year contains almost no volumes of sets, because
they are a small fraction of any catalog and nothing in the draw sought
them out. Estimates of how catalogs handle sets, taken from that
corpus, are wrong in a measurable direction.

## The patterns

| | Pattern | Strength |
|---|---|---|
| 1 | [Two traditions handle part-whole differently](sets.md): one declares each volume and links it, the other describes the set as a whole | **Strong** one way, weaker the other |
| 2 | [House style is institutional](signatures.md), and survives holding the tradition constant | **Strong** |
| 3 | [Type of material overrides the part-whole markers](markers.md) entirely | **Strong** |
| 4 | [The vocabulary shifted across eras](markers.md#change-over-publication-era) | **Moderate** |
| 5 | [Records propagate between catalogs](cases.md), so agreement is not always independent | **Weak** |
| 6 | [A corpus drawn on non-title axes under-samples set volumes](markers.md#what-this-corpus-cannot-see) | **Strong** |
| 7 | [Script placement has four mechanisms](cases.md), not one | **Strong** on prevalence |
| 8 | [Name identifiers take four shapes](cases.md) | **Weak** |

Patterns 1 and 2 disagree about the unit of variation. Patterns 1 and 6
disagree about Oxford. Neither disagreement is resolved here; both are
described where they occur.

Each pattern ends with what follows for otzar, and the strength of the
pattern governs how firm that is. [What follows for
otzar](implications.md) collects them.

## Two kinds of claim, marked

Most of what follows is counted from the corpus or the survey and can
be recomputed from the published [data](data.md). Some of it cannot,
and those claims carry a footnote saying so. There are two kinds:

**Not verified here** — a fact taken from MARC documentation, a
cataloging rule, or an institution's stated terms, used to interpret the
counts but not checked against a source in this work. The footnote names
what would confirm it.

**Inference** — a reading that goes beyond what the counts show. The
footnote separates what the data establishes from what the reading adds.

A claim with no footnote is counted.

## How to read the rest

- [How catalogs describe a set](sets.md) — the 22-work survey, and the
  pattern that answers the question the study was written for.
- [Institutional signatures](signatures.md) — what clustering the
  corpus recovers, and what it does not.
- [Part-whole markers](markers.md) — prevalence across the corpus, the
  material-type confound, and change over time.
- [Items held in common](cases.md) — the same book at up to four
  catalogs, field by field, with identifiers.
- [What follows for otzar](implications.md) — the practices, each
  traced to the pattern it rests on.
- [Reading the numbers](reading-the-numbers.md) — what the intervals,
  Cramér's V, adjusted mutual information and the precision figures
  mean, in plain terms.
- [Related work and references](references.md) — prior studies that
  cover this ground, and the source for each statistical method.
- [The data](data.md) — what is published, and where the scripts live.
