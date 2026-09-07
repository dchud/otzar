# MARC as these catalogs actually send it

otzar reads records from three SRU endpoints, and what they send differs
from what a reading of the MARC specification predicts. This records what
a survey of real responses found, so that decisions about which fields to
read rest on measurement rather than on inference from the format
documentation.

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

The sample is not random. It is one subject area, reached through title
searches, and a title search finds what is catalogued under the title
searched for.

The DNB results are not comparable to the other two. Its `773` rate is
high because the queries returned journal articles and digitised items --
`773 $t In: Journal of ...` -- rather than multipart monographs. Its
figures describe a different kind of material and are reported for
completeness rather than as a statement about how DNB treats sets.

Where a field appears zero times across the whole corpus, that is worth
more than where it appears often. A field absent from 1,027 records of
exactly the material otzar exists to hold is not a field to build on.

## What changed between eras

Records carrying at least one instance of each field, by date of
publication from `008`. 279 records predate 1945, 248 fall between 1945
and 1989, and 446 are from 1990 or later; 54 carry no usable date.

| Field | pre-1945 | 1945-89 | 1990+ | Carries |
|---|---:|---:|---:|---|
| `245` | 100% | 100% | 100% | Title statement |
| `300` | 94% | 92% | 93% | Extent |
| `260` | 93% | 93% | 40% | Publication, pre-RDA |
| `100` | 53% | 60% | 54% | Main entry, personal name |
| `130` | **34%** | 26% | 24% | Main entry, uniform title |
| `630` | 29% | 31% | 45% | Subject added entry, uniform title |
| `246` | 24% | 13% | 48% | Varying form of title |
| `751` | 19% | 19% | 34% | Added entry, geographic name |
| `740` | 17% | 22% | 12% | Added entry, uncontrolled title |
| `730` | 13% | 13% | 26% | Added entry, uniform title |
| `240` | 11% | 9% | 12% | Uniform title under a 1XX |
| `773` | 11% | 11% | 19% | Host item entry |
| `505` | 11% | 12% | 29% | Contents note |
| `880` | 8% | 4% | 14% | Alternate graphic representation |
| `264` | 6% | 4% | 54% | Publication, RDA |
| `250` | 6% | 13% | 29% | Edition statement |
| `490` | **3%** | 8% | 24% | Series statement, transcribed |
| `830` | **3%** | 6% | 17% | Series added entry, authorized |
| `440` | **0%** | **3%** | **0%** | Series statement, obsolete |
| `020` | **0%** | 13% | 46% | ISBN |
| `800` `810` `811` | **0%** | **0%** | **0%** | Series added entry under a name |

Three readings of that table matter more than the rest.

**A pre-1945 set has no ISBN.** Not rarely -- never, in 279 records. Any
path that begins with a barcode or an ISBN lookup is unavailable for the
older half of a collection like this, and identification has to come from
the title page and from matching on title, author and imprint.

**The fields that name a series are a modern habit.** `490` and `830`
stand at 3% before 1945 and 24% and 17% after 1990. The material where
set membership is hardest to establish is the material least likely to
state it in the fields set membership is normally read from.

**The uniform title runs the other way.** `130` is at its most common on
the oldest records, 34%, and stays around a quarter throughout. For this
material it is the most reliable statement that two volumes belong to one
work, and it is more reliable the older the record is.

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

`505` appears on 185 records and 6 of them use the enhanced form with
`$t` per volume -- none at all before 1945. The rest put everything in a
single `$a`:

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

**`440` is a mid-century field, not an old one.** It stands at 0% before
1945, 3% between 1945 and 1989, and 0% after 1990. It was valid from the
late 1960s until 2008, and the records that use it are the ones
catalogued during that window and never reconverted. Expecting older copy
to be full of it has the shape of the argument right and the era wrong.

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

Eleven of the fifteen `$w`-only host entries in the corpus are on
pre-1945 records. A reader expecting `$t` and `$g` finds neither.

## Reproducing this

Queries used `alma.title`, `alma.all_for_ui` and `alma.isbn` against NLI;
`dc.title`, `cql.anywhere` and `bath.isbn` against LC; and `WOE` against
DNB, which returns nothing unless `record_schema` is `MARC21-xml` rather
than the `marcxml` the other two accept.

Records chosen to stand for particular treatments are stored under
`tests/fixtures/marc/`, one per file, with `tests/marc_fixtures.py`
recording what each was kept for.
