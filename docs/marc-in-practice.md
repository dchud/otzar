# MARC as these catalogs actually send it

**The problem this answers is the multi-volume set.** A Judaica
collection is full of works that arrive in many physical volumes: a
Talmud in eighteen, a Mishnah Berurah in six, a Miqraot Gedolot one book
of the Bible at a time. For every record it takes in, otzar has to decide
which set the volume belongs to, which volume of that set it is, and
whether some other record already described the same set under a
different name.

MARC has fields for saying all of that, and a reading of the
specification suggests which ones to use. The trouble is that the answer
changes depending on which catalog sent the record and when it was made,
and several of the fields the specification points at turn out not to be
there at all.

So this is a count. 1,027 real records from three SRU endpoints, measured
rather than reasoned about, so that decisions about which fields to read
rest on what the catalogs send. The absences matter more than the
frequencies: a field that never appears is one no amount of careful
parsing will find.

## There is no single pattern, and there will not be one

The three endpoints do not share a cataloging practice, and neither do
the eras within any one of them, and neither do individual catalogers
working the same material in the same decade. A record is the product of
the rules in force where and when it was made, the material in hand, and
the judgement of the person who made it. Variation between them is
correct practice rather than error, and it does not converge.

So the numbers below describe tendencies, not rules. They are useful for
deciding what is worth reading and in what order, and for knowing which
absences are safe to build on. They are not useful for predicting what
any particular record contains, and code that treats a 90% figure as a
guarantee will meet the other 10% in a collection this size within the
first afternoon.

The practical consequence is that reading a field should never be
conditional on another field being absent, and that every treatment worth
supporting is worth supporting alongside the others rather than as a
fallback in a chain. What otzar can rely on is its own model, assembled
from whatever evidence each record happens to offer.

## The survey

1,027 records: 481 from the National Library of Israel, 446 from the
Library of Congress, 100 from the Deutsche Nationalbibliothek. The
queries covered the multi-volume works a Judaica collection is most
likely to hold, in Hebrew and in translation, and were repeated without
date restriction so that older imprints came back alongside current ones:
Talmud Bavli and Yerushalmi, Mishnah and Mishnayot, Mishnah Berurah,
Miqraot Gedolot, Mishneh Torah, Shulhan Arukh, Ein Yaakov, Midrash
Rabbah, Zohar, Arukh ha-Shulhan, Igrot Moshe, Sefat Emet, responsa, and
the Sapirstein Rashi.

Read the numbers as "what this kind of material looks like", not as
catalog-wide statistics. Three cautions apply throughout:

**The sample is skewed, and it is skewed in the direction that
matters.** Every query was a title search for a work named in advance --
`alma.title="תלמוד בבלי"` and its like. That returns records catalogued
under the title searched for, and misses the ones expressing the same
work differently: a record whose `245` reads something else entirely,
and whose only statement of the work is a `130` uniform title, is
precisely the case this survey exists to find and precisely the case a
title search will not return.

The corpus therefore undercounts the variation it set out to measure.
Treat the figures for the rarer treatments as lower bounds, not as
estimates, and do not quote any of them as a population figure.

The DNB results are not comparable to the other two. Its `773` rate is
high because the queries returned journal articles and digitised items --
`773 $t In: Journal of ...` -- rather than multipart monographs. Its
figures describe a different kind of material and are reported for
completeness rather than as a statement about how DNB treats sets.

Where a field appears zero times across the whole corpus, that is worth
more than where it appears often. A field absent from 1,027 records of
exactly the material otzar exists to hold is not a field to build on.

## Two dates, and they explain different things

A MARC record carries two dates and they are not the same. `008/07-10`
is when the **book** was published. `008/00-05` is when the **record**
was made. In this corpus the median gap between them is 19 years, and
274 records of 973 were catalogued fifty or more years after the book was
printed -- the legacy of retrospective conversion, which moved card
catalogs into MARC through the 1980s and 1990s and gave old books modern
records.

Splitting on one date and not the other hides the mechanism. Splitting on
both shows which is doing the work.

### By publication date

Boundaries at 1970, when ISO 2108 made the ten-digit ISBN an
international standard, and at 2007, when the thirteen-digit form became
mandatory.

| Field | pre-1970 | 1970-2006 | 2007+ |
|---|---:|---:|---:|
| `020` ISBN | **0%** | 39% | 45% |
| `260` publication, pre-RDA | 95% | 85% | 18% |
| `264` publication, RDA | 4% | 12% | 74% |
| `246` varying title | 18% | 37% | 46% |
| `130` uniform title | **30%** | 29% | 21% |
| `240` uniform title under a 1XX | 10% | 11% | 13% |
| `730` added uniform title | 11% | 24% | 25% |
| `740` uncontrolled title | 15% | 29% | 6% |
| `505` contents note | 9% | 26% | 27% |
| `490` series statement | **4%** | 14% | 28% |
| `830` series added entry | **2%** | 14% | 18% |
| `773` host item | 11% | 11% | 22% |
| `440` obsolete series | 0% | 3% | 0% |
| `880` alternate script | 6% | 10% | 14% |

### By record-creation date

Boundaries at 1981, when the Library of Congress implemented AACR2, and
at 2013, when the national libraries implemented RDA.

| Field | pre-1981 | 1981-2012 | 2013+ |
|---|---:|---:|---:|
| `020` ISBN | 18% | 19% | 31% |
| `260` publication, pre-RDA | 96% | 93% | 28% |
| `264` publication, RDA | **3%** | **3%** | **64%** |
| `246` varying title | 3% | 28% | 41% |
| `130` uniform title | 30% | 33% | 17% |
| `730` added uniform title | 6% | 20% | 20% |
| `505` contents note | 6% | 20% | 18% |
| `490` series statement | 18% | 10% | 18% |
| `440` obsolete series | **9%** | 1% | 0% |
| `773` host item | 3% | 8% | 25% |
| `880` alternate script | 0% | 8% | 13% |

Records created before 1981 number only 33, so that column is indicative
rather than solid.

### What each table is good for

**ISBN presence follows the book.** Zero before 1970 and nothing will
change that: ISO 2108 postdates the printing. By record date the same
field reads 18%, 19%, 31% -- smeared, because when somebody catalogued a
book says nothing about whether it has an ISBN.

**RDA encoding follows the record.** `264` reads 3%, 3%, 64% by record
date, which is the 2013 implementation showing up as a step. By
publication date it looks gradual, and the gradient is an artifact:
recently published books tend to have recently made records.

**`440` was a cataloger's field, not an era's.** By record date it runs
9%, 1%, 0%. It was valid from the late 1960s until 2008, so books printed
long before it exist and records using it do not.

**One field can follow both.** ISBN presence follows the book; ISBN
*format* follows the record. Forty-one books published before 2000 carry
a thirteen-digit ISBN, a form that did not exist until 2007 -- because
the record was made or revised afterwards, and the number was converted.
Presence and shape are different questions with different answers.

The practical consequence: when a field is missing, ask which date
explains it. A field the book is too old for will never appear. A field
the record is too old for may arrive whenever that record is next
touched.

### Standards these boundaries come from

| Year | What |
|---|---|
| 1967 | Nine-digit SBN in use in the United Kingdom |
| 1970 | ISO 2108, the ten-digit ISBN |
| 1975 | ISO 3297, the ISSN |
| 1978 | AACR2 published; LC implemented it in 1981 |
| 1980s-90s | Retrospective conversion of card catalogs into MARC |
| 2007 | Thirteen-digit ISBN mandatory |
| 2008 | `440` made obsolete |
| 2010 | RDA published; the national libraries implemented it in 2013 |

## What differs between catalogs

| Field | NLI | LC | DNB |
|---|---:|---:|---:|
| `246` | **54%** | 14% | 8% |
| `751` | **54%** | 0% | 0% |
| `630` | 44% | 32% | 21% |
| `730` | 32% | 11% | 0% |
| `130` | 30% | 30% | 3% |
| `505` | 28% | 13% | 0% |
| `880` | 2% | **21%** | 0% |

`751` and `246` are largely NLI habits, `880` largely an LC one. A parser
tuned on one endpoint's output will read the others badly, and the
differences are large enough that "it works against LC" says little about
what it will do against NLI.

## Two multiscript mechanisms

**LC uses `880`,** on 21% of its records, linking through `$6` to `245`,
`246`, `100`, `240`, `260`, `264`, `700`, `710`, `505`, `730` and `740`.

**NLI marks script on the field itself,** with `$9 heb` or `$9 lat`, and
links parallel forms through `$8 PreferredLanguageHeading`. It does this
on almost every record, and uses `880` on 2%.

The two are not alternatives. Where NLI does emit an `880`, it emits both
at once:

```
130 0# $a Talmud Bavli $9 lat $6 880-01 $8 PreferredLanguageHeading
880 0# $6 130-01/r $a תלמוד בבלי.
```

Code that reads `880` alone gets almost nothing from NLI. Code that reads
`$9` alone gets nothing from LC. Both are needed, and they are different
shapes: `880` is a pointer between two fields, while `$9` and `$8` label
each of several sibling fields that then have to be grouped.

Neither mechanism is limited to Hebrew and Latin. The Vilna Talmud record
carries a Russian form in Cyrillic in the same structure:

```
246 31 $6 880-03 $a Talmud Vavilonskiĭ
880 31 $6 246-03  $a Талмудъ Вавнлонскій
```

### `$9` does not mean the same thing in both catalogs

At NLI, `$9` on a heading field is a script code. At LC, `$9` appears in
`035` holding a control number:

```
NLI   700 ... $9 heb        LC   035 ... $9 (DLC)   87132228
```

A parser that treats any `$9` as a script marker misreads LC records.

## Volume identity is often a name, not a number

For the works this collection holds, the designation distinguishing one
volume from another is frequently a tractate or book name rather than an
enumeration, and it lives in `$p` of a uniform title:

```
130 0# $a Talmud Bavli. $p Rosh ha-shanah. $l English. $k Selections.
130 0# $a Mishnah. $p Sanhedrin. $l German. $f 1910. $g Leipzig
730 0# $a תלמוד בבלי. $p סוכה. $k לקוטים. $f תשס"ו $g בני ברק
```

`130 $p`, `240 $p` and `730 $p` between them appear on more records than
every numeric volume designation in the corpus. Ordering by a parsed
integer discards the majority of what is there.

Where a set has no uniform title and no series statement, the only
statement of its extent is `300 $a`, which is present on 93% of records
and says things like `18 volumes` or `20 volumes in 10` -- a count, with
no way to say which one is in hand.

## A series statement is two different things

The most frequent `490 $a` and `830 $a` values:

```
  8  Talmud Bavli                    a work with volumes to complete
  5  ArtScroll series                a publisher's label
  4  ArtScroll Series                the same label
  3  The ArtScroll series            the same label again
  3  מקראות גדולות                   a work
  2  Judaica books of the Prophets
  2  Studia Judaica (Walter de Gruyter & Co.)
  1  Miqraot gedolot                 the same work as מקראות גדולות
```

`Talmud Bavli` and `מקראות גדולות` are works whose volumes somebody sets
out to complete. `ArtScroll series` and `Studia Judaica` are publishers'
labels attached to books with nothing else in common; nobody holds volume
3 of ArtScroll. Treating every series statement as a set files a large
part of a Judaica collection under one row with meaningless positions.

The same list shows two failures of identity by title: one label under
three capitalisations, and one work under two scripts that NLI has
already marked as parallel forms.

## The contents note is rarely structured

`505` appears on 191 records and 6 of them use the enhanced form with
`$t` per volume: none at all before 1970, two between 1970 and 2006, and
four since. The other 185 put everything in a single `$a`:

```
505 8# $a [1] Berakhot, Peʼah, Demai, Kilayim, Sheviʻit, Terumot ...
505 8# $a [1]. Orach Chaim, chapters 242-292 (Laws of Shabbat). 2021.
```

The enhanced examples are not clean either:

```
505 00 $g Vol, 1. $t Bereishis / Genesis (Sefer Be-reshit, 2018) --
        $g vol 2. $t Shemos / Exodus (Sefer Shemot, 2018) --
        $g vol. 3 $t Vayikra / Leviticus ...
```

Three volume designations, three punctuations, one field.

## What the specification suggests and the data does not

**`800`, `810` and `811` appear zero times** -- in 1,027 records, across
three catalogs and three eras. A series added entry under a personal,
corporate or meeting name is a real MARC treatment and is not one these
endpoints send for this material.

**`440` belongs to a generation of catalogers, not to a generation of
books.** By record-creation date it runs 9%, 1%, 0%. It was valid from
the late 1960s until 2008, so books printed long before it exist in
quantity and records using it do not. Expecting older copy to be full of
it has the shape of the argument right and the date wrong.

**`245 $n` and `$p` are rare**, on 23 records in the whole corpus. The
part-in-the-title treatment is real, but the uniform title expresses the
same thing far more often.

**A series ISSN, `490 $x` or `830 $x`, appears on 6 records.** ISSN is
assigned to continuing resources, so a monographic series carries one and
a multipart monograph does not. It is worth reading because it is the
only assigned identifier available for a set, and worth nothing as a
filter.

**`773` does not always carry a title.** Older analytics link to their
host by control number alone:

```
773 18 $w 990010551080205171
```

Eleven of the fifteen `$w`-only host entries are on books published
before 1970, and none are on books published since 2007. A reader
expecting `$t` and `$g` finds neither.

## Reproducing this

Queries used `alma.title`, `alma.all_for_ui` and `alma.isbn` against NLI;
`dc.title`, `cql.anywhere` and `bath.isbn` against LC; and `WOE` against
DNB, which returns nothing unless `record_schema` is `MARC21-xml` rather
than the `marcxml` the other two accept.

Records chosen to stand for particular treatments are stored under
`tests/fixtures/marc/`, one per file, with `tests/marc_fixtures.py`
recording what each was kept for.
