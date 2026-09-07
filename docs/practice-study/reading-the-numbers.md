# Reading the numbers

Five kinds of measurement appear in this study. This chapter says what
each one means in plain terms, what it can and cannot tell you, and
what the values here actually indicate.

## Percentages with an interval

Most tables give a percentage — 26% of DNB books carry a `490` — and
sometimes a bracketed range beside it, like `[23-30]`. That range is a
**95% Wilson interval**.

The percentage is what this sample showed. The interval is the range of
true values that would plausibly produce a sample like this one. A small
sample gives a wide interval: 3 records out of 8 is 38%, but the
interval runs from 14% to 69%, which is another way of saying eight
records tell you very little.

The practical use is comparison. When two intervals do not overlap, the
difference between them is unlikely to be an accident of sampling. When
they overlap, it may be, and the study tries not to build an argument
on that.

## Cramér's V

`V` appears beside the marker tables. It answers one question: **how
much does knowing the catalog tell you about whether a record carries
this field?**

It runs from 0 to 1. Near 0 means the field appears at about the same
rate everywhere, so the catalog tells you nothing. Near 1 means the
field is essentially a signature of one catalog.

In this study `V=0.04` for uniform titles — every catalog uses them at
6-9%, so the catalog is uninformative. `V=0.51` for `880` linked script
and `V=0.57` for `300 $c` dimensions — those two are almost pure house
style, at 62% versus 1% and 90% versus 19%.

A chi-square p-value sits beside it. That answers only whether a
difference exists at all, not whether it is large. With thousands of
records, tiny differences produce very small p-values, so `V` is the
number worth reading and `p` is close to useless here.

## Adjusted mutual information

**AMI** scores how well the clustering recovers a fact you already
know. Tell me which cluster a record fell into: how much does that
narrow down which catalog it came from?

It runs 0 to 1. **0 means the clustering tells you nothing** beyond
chance. **1 means the clustering recovers the fact exactly.**

The "adjusted" part matters. The unadjusted version drifts upward as
you cut a corpus into more clusters, purely by luck, so scores at four
clusters and twelve clusters could not otherwise be compared. AMI
subtracts the amount chance alone would produce.

In this study 0.80 means the clusters essentially are the five
catalogs. Values near 0.33 mean a real but loose relationship. 0.00 for
leader/19 within the two catalogs that declare it means the clustering
carries no information about it at all.

**Three values near 0.33 with overlapping intervals cannot be ranked.**
Where the study says nothing dominates, that is what the overlap means,
not caution about a real ordering.

### What AMI does not measure

This is the most important caveat in the study, because two of its
findings look contradictory until you see it.

AMI scores whether records **clump together**. It does not score
whether you can **pick them out**.

The 273 records declaring a dependent part score AMI 0.000 against the
clustering: they are scattered inside one large cluster rather than
forming a cluster of their own. The same records are identified by a
two-field test with **no errors**. Both statements are true. A rule does
not need its targets grouped, only distinguishable.

So AMI answered the question the study opened with — do records fall
into groups matching a taxonomy? No — and answered it honestly. But
every practice otzar can act on came from counts and from precision,
not from AMI.

## Precision and recall

When a rule is proposed — "`773` present and `245 $n` or `$p` present
means a declared dependent part" — two numbers describe how it does.

**Precision** is how often the rule is right when it fires. Precision
1.000 means every record it flagged really was a dependent part: no
false alarms.

**Recall** is how much it finds. Recall 0.996 means it caught all but
one of the records it should have.

Both matter and they trade off. A rule that fires on everything has
perfect recall and terrible precision. Here `773` alone has precision
0.581 — it fires on articles inside a host as well as volumes inside a
set — and adding the second field removes that error.

One caution the study repeats: this rule was **read from the same
records it was scored on**. There is no held-out set, so 1.000
describes this corpus rather than predicting the next one.

## Bootstrap intervals and cluster stability

Two questions about whether a result is solid.

**Bootstrap intervals** ask how much a number would move if the sample
had come out slightly differently. The corpus is resampled with
replacement several hundred times and the statistic recomputed; the
middle 95% of those values is the interval. The intervals in this study
hold the clustering fixed while resampling records, so they describe
the stability of the score and not of the clustering itself — which
makes them slightly narrower than the truth.

**Cluster stability** asks whether the groups themselves are real or an
accident of where the algorithm cut. Eighty percent of the corpus is
drawn at random, the clustering is run again, and each original cluster
is checked for how much of it comes back together. A recovery near 1.0
means the group reappears; below about 0.5 means it dissolves.

Every cluster here recovers between 0.92 and 1.00, so the groups are
reproducible. That is worth stating alongside its limit: **a group can
be perfectly reproducible and still mean nothing.** The most stable
clusters in this study are stable because accession-number formats are
consistent within an institution.
