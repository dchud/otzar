# How catalogs describe a set

**Pattern 1. Two traditions handle the part-whole relationship
differently. One creates a record per volume and declares it in the
leader. The other describes the set as a whole and enumerates its parts
in a note.**

This is the pattern the study was written to find, and the corpus could
not show it. A sample drawn on language and year contains almost no
volumes of sets. So this chapter asks the question directly: take works
that are unambiguously multi-volume, ask every catalog for them by
title, and look at what comes back.

## The survey

Twenty-two works, chosen as the multi-volume works a Torah-study
collection is built from, asked of all five catalogs — in Hebrew at
NLI, romanized elsewhere, since that is how each indexes.

A title query returns more than the work asked for, so every record is
matched against the work before it is counted. The first pass reported
43 NLI records and 6 DNB records for one encyclopedia; filtering showed
22 and 0, the DNB hits being a different encyclopedia the title index
matched. Counts below are records whose `245` names the work.

Several cells reached the fifty-record cap on a single SRU response, so
those are records examined rather than exhaustive counts. Nothing in
the pattern depends on the difference.

## What each catalog does

| Catalog | Works held | Records | `leader/19=c` | `773` | `245 $n`/`$p` | `300` volume count | `505` |
|---|---|---|---|---|---|---|---|
| LC | 22 | 521 | **0** | 1 | 6 | 176 | 122 |
| NLI | 22 | 444 | **0** | 116 | 5 | 90 | 123 |
| Oxford | 20 | 215 | **0** | 9 | 40 | 64 | 79 |
| DNB | 14 | 291 | 97 | 110 | 98 | 0 | 10 |
| K10plus | 20 | 501 | 314 | 359 | 314 | 10 | 18 |

**Across LC, Oxford and NLI: `leader/19=c` appears on 0 of 1,180
records.** Not rarely — never, across 22 works that all three hold. On
the other side K10plus declares 314 of 501 and DNB 97 of 291. In 19 of
the 22 works a PICA catalog declares per-volume records while none of
the other three does.

## Work by work

Records naming the work, with declared dependent parts in bold.

| Work | LC | Oxford | NLI | DNB | K10plus |
|---|---|---|---|---|---|
| Talmud Bavli | 46 | 20 | 12 | 32 (**11**) | 34 (**28**) |
| Miqraot Gedolot | 41 | 13 | 20 | — | 16 (**14**) |
| Shulhan Arukh | 48 | 19 | 6 | 31 (**2**) | 28 (**18**) |
| Mishneh Torah | 41 | 15 | 8 | 10 (**6**) | 23 (**16**) |
| Zohar | 46 | 27 | 25 | 32 | 31 (**21**) |
| Mishnah Berurah | 36 | 3 | 21 | — | 18 (**13**) |
| Talmud Yerushalmi | 32 | 3 | 17 | 20 (**3**) | 14 (**8**) |
| Tosefta | 43 | 5 | 12 | 43 (**27**) | 28 (**3**) |
| Sifre | 47 | 7 | 20 | 12 (**2**) | 1 |
| Or ha-Hayim | 36 | 6 | 38 | 1 | — |
| Yalkut Shimoni | 29 | 19 | 31 | 50 (**5**) | 49 (**6**) |
| Ein Yaakov | 23 | 8 | 8 | 2 (**1**) | 36 (**23**) |
| Arbaah Turim | 14 | 3 | 40 | — | 10 (**4**) |
| Encyclopaedia Judaica | 10 | 8 | 16 | 47 (**38**) | 45 (**42**) |
| Otsar ha-Geonim | 5 | 5 | 34 | — | 17 (**13**) |
| Torah Shelemah | 5 | 4 | 19 | — | 48 (**47**) |
| Die Mischna (Giessen) | 5 | 37 | 10 | — | 24 (**5**) |
| Midrash Rabbah | 5 | — | 2 | 4 | — |
| Pesiqta Rabbati | 4 | 6 | 36 | 6 (**2**) | 41 (**19**) |
| Arukh ha-Shulhan | 2 | 5 | 33 | — | 5 (**4**) |
| Schottenstein Talmud | 2 | — | 14 | 1 | 2 |
| Entsiklopedyah talmudit | 1 | 2 | 22 | — | 31 (**30**) |

**Entsiḳlopedyah talmudit is the sharpest contrast.** The Library of
Congress describes the whole encyclopedia with **one record**, extent
`300 $a "v."`. K10plus describes it with **31**, thirty of them
declared dependent parts carrying `773` and `245 $n`/`$p`. One
bibliographic situation; a thirty-one-fold difference in how many
records describe it.

**Torah Shelemah** runs the same way: 48 records at K10plus, 47
declared, against 5 at LC and 4 at Oxford. **Encyclopaedia Judaica** is
declared 38 times at DNB and 42 at K10plus, against 10 at LC and 8 at
Oxford.

**The Schottenstein Talmud is the exception worth naming.** Held by
four catalogs — 14 records at NLI, 2 at LC, 2 at K10plus, 1 at DNB —
and declared by none of them. The modern English-language Talmud, the
one a contemporary collection is most likely to contain, is the one no
catalog in this survey treats as a declared multipart set.

## Why the convergence is better evidence on one side

The three catalogs that never declare share no software. LC answers
through a Z39.50 gateway; Oxford and NLI run separate Alma
installations, in different countries, under different cataloging
agencies. Three independent systems producing the same treatment across
1,180 records is evidence about a cataloging tradition rather than
about one system's export.[^anglo]

The two that do declare share PICA, and K10plus is a union catalog
built on the same software family as DNB. Their agreement is weaker
evidence for the same reason the first group's is strong: a shared data
model can produce shared output without any shared decision.[^pica]

So the pattern is asymmetric. That the Anglo-American tradition does
not use `leader/19` is well supported. That the German tradition does
is supported by two catalogs that may amount to one observation.

## Four idioms, not two

Within those traditions the survey shows four distinct mechanisms.

**Declare and link.** K10plus and DNB: a record per volume,
`leader/19=c`, `773` to the parent, `245 $n`/`$p` carrying the volume
designation. K10plus applies it to 314 records here, DNB to 97.

**Describe the set as a whole.** LC most consistently: 176 of its 521
records carry a volume count in `300 $a` and 122 carry a `505` contents
note, with a single `773` in the entire set of records. The volumes are
listed inside one record rather than given records of their own.

**Enumerate without linking.** Oxford: 40 records carry `245 $n`/`$p`
with no `773` and no leader declaration. Its 37 records for *Die
Mischna* are one per tractate — Nidda, Gittin, Schabbat, Abôt — each
naming its tractate in `245 $p`, each with a contents note, none linked
to a parent or declared in the leader. Oxford does create per-volume
records; it just does not say so anywhere a machine can read it as a
relationship.

**Link without declaring.** NLI: **116 of 444 records carry `773`**,
more than a quarter, and none carries `leader/19`. The relationship is
recorded as a link but never as a record type.

## What follows for otzar

**Read `leader/19` when it is there, and expect it from two sources.**
It is the only place in this material where set membership is stated
rather than inferred. It will arrive from K10plus and DNB and from
nowhere else in the current source list.

**Expect a one-to-many mismatch when reconciling across catalogs.** The
same set is one record from LC and thirty-one from K10plus. Any
identity rule that assumes records correspond one-to-one across sources
will be wrong on exactly the material otzar is built for. This is a
data-model consequence, not a parsing one.

**Do not read absence as absence of the relationship.** An LC record
with no `773` and no `leader/19` is not a record of a standalone book.
It is likely the set-level record, and the volume list is in its `505`.

**`773` means different things by source.** At K10plus it accompanies a
declared dependent part. At NLI it appears on a quarter of records with
nothing declared. Reading it as the same evidence at both is a mistake
in the direction of over-matching.

**Parse `505` for volume lists.** Where the Anglo-American catalogs
describe a set they put the volumes in a contents note: 122 records at
LC, 123 at NLI, 79 at Oxford. For those sources that note is the volume
list, and it is the only machine-readable one available.

[^anglo]: **Inference, and the load-bearing one in this chapter.** What
    is counted is that three catalogs return no `leader/19=c` across
    1,180 records for 22 works. That this reflects a shared
    Anglo-American cataloging tradition rather than three independent
    coincidences is a reading, supported by those catalogs running
    unrelated systems in three countries. Confirming it means checking
    AACR2 and RDA guidance on multipart monographs, and asking whether
    the tradition prescribes set-level description.

[^pica]: **Inference.** DNB and K10plus both run PICA, and their
    per-volume records agree closely. Whether that reflects a German
    cataloging tradition or one export routine is not distinguished
    here. A third PICA-independent German-tradition catalog would
    separate the two.
