# MARC as these catalogs actually send it

otzar reads records from three SRU endpoints, and what they send differs
from what a reading of the MARC specification predicts. This records what
a survey of real responses found, so that decisions about which fields to
read rest on measurement rather than on inference from the format
documentation.

## The survey

122 records: 81 from the National Library of Israel, 41 from the Library
of Congress, 0 from the Deutsche Nationalbibliothek. Nineteen queries,
chosen to cover the multi-volume works a Judaica collection is most
likely to hold -- Talmud Bavli in Hebrew and English, Talmud Yerushalmi,
Mishnah Berurah, Miqraot Gedolot, Mishneh Torah, Arukh ha-Shulhan, Igrot
Moshe, Sefat Emet, and the Sapirstein Rashi.

The corpus is small and it is not a random sample. It is drawn from one
subject area, and the numbers below should be read as "what this kind of
material looks like" rather than as catalog-wide statistics. Where a
field appears zero times, that is worth more than where it appears often:
a field absent from 122 records of exactly the material otzar exists to
hold is not a field to build on.

## Field frequency

Records carrying at least one instance of each field:

| Field | NLI | LC | Total | Carries |
|---|---:|---:|---:|---|
| `245` | 81 | 41 | 122 | Title statement |
| `300` | 70 | 40 | 110 | Extent |
| `700` | 58 | 28 | 86 | Added entry, personal name |
| `260` | 54 | 27 | 81 | Publication, pre-RDA |
| `246` | 49 | 15 | **64** | Varying form of title |
| `100` | 44 | 11 | 55 | Main entry, personal name |
| `730` | 25 | 20 | **45** | Added entry, uniform title |
| `130` | 25 | 17 | **42** | Main entry, uniform title |
| `505` | 32 | 8 | 40 | Contents note |
| `710` | 32 | 7 | 39 | Added entry, corporate name |
| `020` | 22 | 16 | 38 | ISBN |
| `264` | 23 | 14 | 37 | Publication, RDA |
| `250` | 20 | 14 | 34 | Edition statement |
| `740` | 23 | 8 | 31 | Added entry, uncontrolled title |
| `490` | 12 | 10 | 22 | Series statement, transcribed |
| `240` | 15 | 5 | **20** | Uniform title under a 1XX |
| `880` | 0 | 15 | 15 | Alternate graphic representation |
| `773` | 13 | 0 | 13 | Host item entry |
| `830` | 11 | 2 | 13 | Series added entry, authorized |
| `440` | 0 | 1 | 1 | Series statement, obsolete |
| `800` `810` `811` | 0 | 0 | **0** | Series added entry under a name |

Subfields that decide how a multipart work is expressed:

| Subfield | NLI | LC | Meaning |
|---|---:|---:|---|
| `730 $p` | 14 | 18 | Part of a named work, as an added entry |
| `130 $p` | 14 | 10 | Part of the work in the main entry |
| `020 $q` | 6 | 11 | Volume qualifier on an ISBN |
| `240 $p` | 4 | 0 | Part of the work under a 1XX |
| `505` basic | 32 | 7 | Contents as one undivided string |
| `245 $n` `$p` | 1 | 0 | Part number and part title in the title |
| `505` enhanced | 0 | 1 | Contents with `$t` per volume |
| `490 $x` `830 $x` | 0 | 1 | Series ISSN |

## Two multiscript mechanisms, not one

This is the largest difference between the two catalogs, and it is not
a difference of degree.

**LC uses `880`.** Fifteen of its 41 records carry alternate graphic
representation fields, linked to `245`, `246`, `100`, `240`, `260`,
`264`, `700`, `710`, `505`, `730` and `740` through `$6`.

**NLI uses none.** Zero of 81 records carry an `880`. Instead 78 of 81
mark the script on the field itself with `$9 heb` or `$9 lat`, and link
the parallel forms with `$8 PreferredLanguageHeading`:

```
130 0# $a Talmud Bavli. $p Pesahim. $l English. $k Selections.
        $f 194-? $g Jerusalem $9 lat $8 PreferredLanguageHeading
130 0# $a משנה. $p פרה. $f תשע"ו $g ירושלים
        $9 heb $8 PreferredLanguageHeading
```

Code written against `880` linkage alone reads nothing from NLI, which
is the endpoint that holds the Hebrew material. Code written against
`$9` and `$8` alone reads nothing from LC. Both are needed, and they are
different shapes: one is a pointer between two fields, the other is a
label on each of several parallel fields.

NLI also carries the cross-script variant in `246`, which is part of why
that field is so common there:

```
246 1# $i בשער גם: $a ערוך השלחן
```

against a romanized `245`. A reader looking only at `245` sees one script
and concludes the record has no other.

## Volume identity is often a name, not a number

For the works this collection holds, the designation that distinguishes
one volume from another is frequently a tractate or book name rather than
an enumeration, and it lives in `$p` of a uniform title:

```
130 0# $a Talmud Bavli. $p Rosh ha-shanah. $l English. $k Selections.
730 0# $a תלמוד בבלי. $p סוכה. $k לקוטים. $f תשס"ו $g בני ברק
730 0# $a Bible. $p Pentateuch. $l Hebrew. $f 2018.
```

`130 $p`, `240 $p` and `730 $p` together appear on more records than
every numeric volume designation in the corpus combined. Ordering by a
parsed integer discards the majority of what is actually there.

`730` deserves particular note. It has the same name-title structure as
`130`, appears on 45 records, and names the works a volume contains --
which is how a compilation says what is inside it.

## A series statement is two different things

The most frequent `490 $a` and `830 $a` values in the corpus:

```
  8  Talmud Bavli
  5  ArtScroll series
  4  ArtScroll Series
  3  The ArtScroll series
  3  מקראות גדולות
  2  Judaica books of the Prophets
  2  מקורות ישראל
  2  ArtScroll Judaica classics
  2  Studia Judaica (Walter de Gruyter & Co.)
  1  Miqraot gedolot
```

Two kinds of thing share one field. `Talmud Bavli` and `מקראות גדולות`
are works with volumes somebody sets out to complete. `ArtScroll series`
and `Studia Judaica` are publishers' labels attached to unrelated books;
nobody holds volume 3 of ArtScroll. Treating every series statement as a
set files a large part of a Judaica collection under a single row with
meaningless positions.

The same list shows two failures of identity by title. One imprint
appears under three capitalisations, and `מקראות גדולות` and
`Miqraot gedolot` are one work in two scripts -- which NLI has already
marked as parallel forms with `$9 heb` and `$9 lat`, evidence sitting in
the record for a merge that a title comparison will not make.

## The contents note is rarely structured

`505` appears on 40 records and only one of them uses the enhanced form
with `$t` per volume. The other 39 put everything in a single `$a`:

```
505 8# $a [1]. Orach Chaim, chapters 242-292 (Laws of Shabbat). 2021.
505 8# $a הושענא רבה: כולל תלמוד בבלי המבואר מתיבתא פרק ד' מסוכה,
         פסקי הרא"ש, חידושי הלכות מהרש"א, ילקוט מפרשים החדש...
```

The one enhanced example is not clean either:

```
505 00 $g Vol, 1. $t Bereishis / Genesis (Sefer Be-reshit, 2018) --
        $g vol 2. $t Shemos / Exodus (Sefer Shemot, 2018) --
        $g vol. 3 $t Vayikra / Leviticus ...
```

Three volume designations, three punctuations. A parser that expects
`$t` per volume addresses one record in 122; a parser that expects
consistent enumeration inside `$g` addresses none of them completely.

## What the specification suggests and the data does not

Three fields a reading of the format would rank highly:

`800`, `810` and `811`, the series added entries under a personal,
corporate or meeting name, appear zero times. A set entered under a
person or body is a real MARC treatment and is not one these endpoints
send for this material.

`440`, the obsolete series statement, appears once. It was valid until
2008 and the expectation that older copy is full of it is not borne out
here; both catalogs have re-coded to a `490`/`830` pair.

`245 $n` and `$p`, the multipart monograph treatment, appear on one
record. The part-in-the-title pattern is real but rare compared with the
uniform title, which expresses the same thing in `130 $p` or `730 $p`.

A series ISSN, `490 $x` or `830 $x`, appears once. ISSN is assigned to
continuing resources, so a monographic series carries one and a multipart
monograph does not. It is worth reading because it is the only assigned
identifier available for a set, and worth nothing as a filter.

## Reproducing this

The queries used `alma.title`, `alma.all_for_ui` and `alma.isbn` against
NLI, `dc.title`, `cql.anywhere` and `bath.isbn` against LC. Two queries
returned nothing and the syntax rather than the catalog is the likely
reason: an author-title phrase search against NLI, and a subject search
against DNB, which returned no records for any query attempted.
