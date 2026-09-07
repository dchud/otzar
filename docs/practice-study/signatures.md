# Institutional signatures

## Every field included: the clusters are the catalogs

Clustering all 5,252 records on all 725 structural features recovers
which catalog answered, and little else.

| Cut | catalog | `040$a` | leader/18 | leader/06 | leader/07 | decade |
|---|---|---|---|---|---|---|
| k=4 | **0.655** | 0.403 | 0.286 | 0.190 | 0.139 | 0.042 |
| k=8 | **0.803** | 0.558 | 0.516 | 0.237 | 0.204 | 0.068 |
| k=12 | **0.788** | 0.552 | 0.519 | 0.235 | 0.237 | 0.073 |

Adjusted mutual information. At k=8 the interval on the catalog figure
is 0.795–0.812, and on the next-best label, `040$a`, it is 0.559–0.579.
The two do not overlap; the separation is not sampling noise.

The features carrying that separation are administrative. NLI's
clusters are marked by `903`, `939`, `919`, `964` and Alma's
non-numeric `AVE`; LC's by `906` with its `$b` through `$g`; DNB's by
`044` and `850`. These fields describe how a record is handled, funded
and held. None of them describes a book.

This is the third of the three possible outcomes, and it arrives
first and strongest.

## The fingerprint is institutional, not the software

NLI and Oxford run the same Alma software, exchange the same record
format, and answer the same SRU version and query syntax. If the
signature above were an artifact of export tooling, these two should
be hard to tell apart. Clustering only those 2,109 records:

| Cut | best label | AMI |
|---|---|---|
| k=2 | `040$a` agency | 0.158 |
| k=4 | **catalog** | **0.790** |
| k=6 | catalog | 0.609 |

A cut of two Alma institutions separates them almost as sharply as a
cut of five different platforms separates those (0.790 against 0.803).
Whatever produces the fingerprint is the practice of the institution,
not the shape its export software imposes.

The [case studies](cases.md) show the mechanism directly: for one item
held by both, NLI and Oxford produce near-identical `245`, `264` and
`300`, and diverge entirely in the local block.

## Standard fields alone: no signal dominates

MARC reserves `09X`, `59X`, `69X` and `9XX` for local definition.
Dropping those, together with the administrative `0XX` and `85X` fields
that name the agency, its record number or its holdings, leaves 442
features.

| Cut | catalog | leader/06 | leader/07 | `040$a` | leader/18 | decade |
|---|---|---|---|---|---|---|
| k=4 | 0.355 | 0.192 | 0.246 | 0.280 | 0.241 | 0.059 |
| k=8 | 0.353 | 0.285 | 0.312 | 0.281 | 0.246 | 0.077 |
| k=12 | 0.346 | 0.336 | 0.330 | 0.274 | 0.255 | 0.090 |

At k=12 the intervals are catalog 0.334–0.358, leader/06 0.319–0.358,
leader/07 0.311–0.352. All three overlap. Bibliographic structure is
present and strengthens as the cut gets finer, but it never separates
from the institutional signal, and no organising principle wins.

That is the second possible outcome sitting alongside the third: the
treatments are real enough to show up, and not sharp enough to sort
records by.

## Within one catalog, the answer changes

Clustering inside a single catalog holds the institution constant.
The result is not consistent across catalogs.

| Catalog | Strongest label | AMI | leader/07 |
|---|---|---|---|
| K10plus | leader/07 bibliographic level | 0.558 | 0.558 |
| NLI | leader/07 bibliographic level | 0.548 | 0.548 |
| LC | leader/06 record type | 0.770 | -0.003 |
| Oxford | leader/18 description form | 0.587 | 0.043 |
| DNB | `040$a` agency | 0.268 | 0.106 |

At K10plus and NLI a record's structure predicts its declared
bibliographic level. At Oxford the same structure predicts which
cataloging rules were applied and in which decade, and says nothing
about bibliographic level. At LC it predicts the type of material. At
DNB it predicts very little; those records are structurally uniform,
and the best available label is which German library contributed them.

The LC and Oxford figures for leader/07 are near zero in part because
neither sample varies much on it. That is itself the finding: the
distinctions the taxonomy names are not distinctions those catalogs
draw in this material.

## The partitions are stable

Every cluster large enough to test recovers under resampling. Across 30
resamples at 80% of the corpus, mean best Jaccard recovery:

| Feature set | Cluster sizes | Recovery |
|---|---|---|
| All fields | 1959, 1249, 791, 621, 564, 43, 18 | 0.94–1.00 |
| Standard only | 3778, 554, 499, 297, 84, 24, 13 | 0.92–1.00 |

Nothing here is an artifact of where average linkage happened to cut. A
recovery below about 0.5 would mean the partition dissolves on a
resample; none of these come close to that.

The caveat is what stability does *not* establish. A partition can be
perfectly reproducible and still correspond to nothing of interest —
which is exactly the case for the all-fields clustering, whose stable
clusters are stable because accession-number formats are consistent
within an institution.

![Marker prevalence by catalog](figures/fig1-marker-heatmap.svg)
