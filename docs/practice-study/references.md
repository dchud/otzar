# Related work and references

## Related work

The corpus half of this study — counting which fields each catalog
uses — is well-trodden ground, and by larger studies than this one.

**Király's QA Catalogue** is the closest contemporary work. It is a
metadata quality assessment toolset for MARC21, PICA and UNIMARC
catalogues, and has been applied to the validation of 14 MARC21
library catalogues, examining structural features of records across
institutions. Anyone extending this study should start there rather
than from these scripts: it is a maintained tool that does at scale
what `featurize.py` does by hand.

**The MCDU project** (Moen and colleagues) analysed content designation
use across roughly 56 million WorldCat records, comparing observed
field and subfield use against national, core and minimal level record
standards. It is the definitive statement of which parts of MARC
catalogers actually use.

**Mayernik (2010)** showed that MARC field use follows a power law: in
a sample of 1,500 Library of Congress records, ten fields appeared in
over 99% of records while 144 fields were observed overall with highly
skewed incidence. The long tail of rarely-used fields in the marker
chapter is the same phenomenon.

**OCLC Research (2010)** examined the implications of MARC tag usage
for metadata practice.

Against that background, the corpus half of this study is a small
replication on a Judaica-focused sample, with the addition that it
compares five catalogs directly rather than pooling them.

### What appears less covered

**Empirical use of leader/19.** Searching for measurements of how the
multipart resource record level is populated in practice turned up MARC
documentation and cataloging examples but no usage study. That is a
negative result from one search rather than a claim that none
exists.[^lit]

**Record-count asymmetry for a named work.** The practitioner
literature documents the decision — see below — but this study did not
find a published count of how many records different catalogs produce
for the same multi-volume work.

### Cataloging policy on levels of description

A multipart resource may be described at three levels:
**comprehensive** description of the whole in one record,
**analytical** description of a part standing alone, and a description
of the whole together with its linked parts — **multilevel description**
under AACR2, **hierarchical description** under RDA. MARC encodes the
third in leader/19.

The rule that explains this study's central finding is old and blunt.
LCRI 13.6 instructs: *do not employ the technique of multilevel
description in any case*. The LC-PCC guidance under RDA continues not
to create hierarchical descriptions.

Dating matters here. RDA was implemented in 2013 and most records
examined predate it, so RDA alone could not explain a practice visible
in pre-1970 imprints. The AACR2-era prohibition and its RDA successor
together bracket the period the records cover, and the
[set chapter](sets.md) shows the coding rates are stable across it.

The rule interpretation on analysis of monographic series and multipart
monographs states that LC analyzes and classes parts separately, giving
a dependent-titled part its own record with the comprehensive title as
common title, subject to listed exceptions. The survey finds few such
records, which the set chapter records as unresolved.

**These are policies about bibliographic description.** The separate
body of policy governing series authority records — the authorized form
of a series heading, and whether a series is traced — is what bears on
this study's `490` and `830` findings, and is not the same thing. The
NACO series documentation belongs to that second body, and nothing in
this study rests on it. Anyone extending the series half of the marker
chapter should start there rather than from the description policies
above.

### The practitioner literature explains the volume-title split

Cataloging manuals give the rule this study measures the effect of.
Guidance from Yale, the CCS Cataloging Manual, PINES and others
converges on the same decision: use a single record when each part is
numbered but lacks its own title and the parts form one unit; use
separate records when each volume has a distinctive title, in which
case each is classed and described separately.

That maps onto the leader/19 split directly. A part with a dependent
title is `c`; a part with an independent title is `b`. The survey finds
`b` on works whose volumes carry their own names and `c` on works whose
volumes are numbered ranges — which is the documented rule, visible in
the records.

One further documentation note bears on an inference this study
footnotes.
MARC reference documentation states that users typically do not have
access to leader/19 and that the entry is usually system generated. If
that is generally true, the presence of leader/19 at the two PICA
catalogs and its absence at the other three is partly a fact about
systems rather than about cataloger decisions — which is the reading
the [set chapter](sets.md) footnotes as unresolved.[^gen]

## Statistical methods

Each method used, with the source that defines it.

**Adjusted mutual information.** Vinh, N. X., Epps, J., and Bailey, J.
(2010). "Information Theoretic Measures for Clusterings Comparison:
Variants, Properties, Normalization and Correction for Chance."
*Journal of Machine Learning Research* 11: 2837–2854. The correction
for chance is what makes scores at different numbers of clusters
comparable. Computed here with scikit-learn's
`adjusted_mutual_info_score`.

**Chance correction for partition comparison, generally.** Hubert, L.
and Arabie, P. (1985). "Comparing partitions." *Journal of
Classification* 2: 193–218.

**Wilson score interval.** Wilson, E. B. (1927). "Probable Inference,
the Law of Succession, and Statistical Inference." *Journal of the
American Statistical Association* 22(158): 209–212. Preferred over the
normal-approximation interval for the small counts and proportions near
0 or 1 that occur throughout this study; see Brown, L. D., Cai, T. T.
and DasGupta, A. (2001), "Interval Estimation for a Binomial
Proportion," *Statistical Science* 16(2): 101–133.

**Cramér's V.** Cramér, H. (1946). *Mathematical Methods of
Statistics*. Princeton University Press. Reported instead of a bare
chi-square because with thousands of records a negligible difference
still produces a very small p-value.

**Chi-square test of independence.** Pearson, K. (1900). "On the
criterion that a given system of deviations from the probable in the
case of a correlated system of variables is such that it can be
reasonably supposed to have arisen from random sampling."
*Philosophical Magazine* 50(302): 157–175.

**Jaccard coefficient.** Jaccard, P. (1912). "The distribution of the
flora in the alpine zone." *New Phytologist* 11(2): 37–50. Used as the
distance between records' binary feature vectors, and again as the
measure of cluster recovery under resampling.

**Average-linkage hierarchical clustering.** Sokal, R. R. and Michener,
C. D. (1958). "A statistical method for evaluating systematic
relationships." *University of Kansas Science Bulletin* 38: 1409–1438.

**Cluster stability by resampling.** Hennig, C. (2007). "Cluster-wise
assessment of cluster stability." *Computational Statistics and Data
Analysis* 52(1): 258–271. The convention this study reports against:
mean bootstrap Jaccard below 0.75 indicates an unstable cluster, and
0.85 or above a highly stable one.

**The bootstrap.** Efron, B. (1979). "Bootstrap Methods: Another Look
at the Jackknife." *Annals of Statistics* 7(1): 1–26.

### Software

Analysis in Python 3.13 with **scikit-learn** (Pedregosa et al., 2011,
*JMLR* 12: 2825–2830), **SciPy** (Virtanen et al., 2020, *Nature
Methods* 17: 261–272), **NumPy** and **matplotlib** (Hunter, 2007,
*Computing in Science & Engineering* 9(3): 90–95). MARC parsing with
`xml.etree.ElementTree`; SRU requests with `httpx`.

[^lit]: **Not verified here.** The literature search behind this
    chapter was a small number of web searches, not a systematic
    review. Absence of a result is weak evidence of absence, and the
    Judaica and Hebraica cataloging literature in particular was not
    searched.

[^gen]: **Not verified here.** The statement that leader/19 is usually
    system generated comes from vendor MARC reference documentation,
    not from the MARC 21 specification or from the two catalogs
    concerned. Confirming it means asking DNB and K10plus how the
    position is populated in their export.
