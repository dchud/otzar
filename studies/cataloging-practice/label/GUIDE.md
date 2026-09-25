# Labeling guide

Version: 1

This is the document the labeler reads. It defines the six fields
recorded for each record, the key that records each value in the
labeling tool, the rule for uncertainty and notes, and twelve worked
examples.

Each record is judged from its description alone. The tool shows the
record as the catalog returned it and nothing derived from it. One
position is hidden: leader/19, which codes whether a record describes
a set or a part of one, is shown as `█`, because it is the coded form
of the `level` and `own-title` judgments. Everything else in the record
is shown as sent.

The key tables in [Fields](#fields) are what the tool reads. Changing a
field, a value or a key there changes the tool; the tool refuses to
start if two values in one field share a key.

## Reading a record

The tool prints the catalog's name, the leader, each control field, and
each data field as its tag and two indicators, a blank indicator shown
as `#`, followed by its subfields with their codes (`$a`, `$b`). Each
value lays out in its own direction, so Hebrew and Latin script in one
field do not reorder each other.

Judge from the whole description, not the title alone. Where 245 holds
only `<>` and a `$6` link, the title is in the 880 that `$6` names.

## Fields

Six fields, asked in this order. `own-title` is asked only when `level`
is `volume`. Every answered field also carries `sure` or `unsure`; see
[Uncertainty and notes](#uncertainty-and-notes).

### `work`

Which of the 22 works the record describes, chosen from the list, not
typed. A record describes a work when its main content is the text of
the work or when it is about the work; `relation` says which.

- When one work's text is printed with another's, as a Tur with Bet
  Yosef, the work is the one whose text is the main content.
- Two entries name editions, not texts: `Die Mischna (Giessen)` is the
  Giessen Mishnah and `Schottenstein Talmud` is the ArtScroll
  Schottenstein edition. A record that fits one of these and also the
  text it edits takes the edition's entry. Another edition of the
  Mishnah is `other-work`.
- `other-work`: the record is an edition of, or is about, a particular
  work that is not among the 22.
- `none`: the record is not an edition of a particular work and is not
  about one. `none` sets `relation` to `unrelated`.

| Key | Value |
|---|---|
| `e` | `Entsiklopedyah talmudit` |
| `d` | `Die Mischna (Giessen)` |
| `b` | `Talmud Bavli` |
| `q` | `Miqraot Gedolot` |
| `m` | `Mishnah Berurah` |
| `s` | `Shulhan Arukh` |
| `t` | `Mishneh Torah` |
| `y` | `Talmud Yerushalmi` |
| `r` | `Midrash Rabbah` |
| `z` | `Zohar` |
| `a` | `Arukh ha-Shulhan` |
| `j` | `Encyclopaedia Judaica` |
| `l` | `Torah Shelemah` |
| `c` | `Schottenstein Talmud` |
| `i` | `Ein Yaakov` |
| `k` | `Yalkut Shimoni` |
| `f` | `Tosefta` |
| `4` | `Arbaah Turim` |
| `g` | `Otsar ha-Geonim` |
| `v` | `Sifre` |
| `h` | `Or ha-Hayim` |
| `p` | `Pesiqta Rabbati` |
| `o` | `other-work` |
| `x` | `none` |

### `relation`

The record's relation to the chosen work. With `other-work`, the
relation is to that other work.

| Key | Value | Meaning |
|---|---|---|
| `e` | `edition` | The described resource's main content is the text of the work, in any language, whole or part, with or without commentary, including translations, abridgments and selections. |
| `a` | `about` | A study, index, concordance, bibliography, review or commentary that stands without the text. |
| `x` | `unrelated` | The title matched but the resource is something else (children's books under ספרי). Recorded when `work` is `none`; the tool sets it. |
| `c` | `cannot-judge` | The record is too sparse to read. Requires a note. |

### `level`

The study's question, judged from the whole description.

A series is not a multi-volume resource. A book that is one of a series
of separately titled books (a 490 or 830 naming the series) is `single`
unless it is also a volume of a set.

| Key | Value | Meaning |
|---|---|---|
| `w` | `whole-set` | The record describes a multi-volume resource as one thing, whether or not the extent counts the volumes and whether or not the set is complete. |
| `v` | `volume` | The record describes one physical volume, or a small numbered subset, of a multi-volume resource, whether or not it is linked to a parent. |
| `s` | `single` | One physical unit that is not part of a set, including one-volume editions of a multi-volume work. |
| `a` | `analytic` | A part smaller than a volume: a tractate within a volume, an article, folios in a codex, a track. |
| `x` | `other` | Archival collection or subunit, serial, kit, collection-level e-resource. Requires a note. |
| `c` | `cannot-judge` | The record is too sparse to read. Requires a note. |

### `own-title`

Asked only when `level` is `volume`. This is the property leader/19
`b` and `c` encode, labeled without seeing the code.

| Key | Value | Meaning |
|---|---|---|
| `s` | `standalone` | The volume's title would identify it without the set title. |
| `d` | `dependent` | The volume's title would not identify it without the set title. |
| `?` | `unsure` | The record gives no basis for either. |

### `origin`

| Key | Value | Meaning |
|---|---|---|
| `l` | `library` | Created or adapted by a library, including copy cataloging. |
| `v` | `vendor` | Publisher- or aggregator-supplied, typically an e-book record with a 776, a vendor code in 040 $a, or a batch-load signature. |
| `?` | `unsure` | The record gives no basis for either. |

### `carrier`

Labeled separately from `origin`, so that treating "online resource" as
a sign of a vendor record can be scored as the heuristic it is.

| Key | Value | Meaning |
|---|---|---|
| `p` | `print` | Print. |
| `o` | `online` | Online. |
| `x` | `other` | Any other carrier: microform, disc, sound recording, photograph. Requires a note. |

## Uncertainty and notes

Every answered field carries `sure` or `unsure`. An unsure label still
records the best choice: mark the field unsure and choose the value the
record points to.

The value `unsure` under `own-title` and `origin` is for a record that
gives no basis for a best choice. When the record points one way
without settling it, choose that value and mark the field unsure.

`cannot-judge` is a value for `relation` and `level` only, reserved for
records too sparse to read: no 245, or a 245 that is only a number. It
is not a synonym for unsure and is expected on under two per cent of
records. A 245 of `<>` whose linked 880 holds the title is not sparse.

The note is free text. It is required when `cannot-judge` or `other` is
chosen, and the tool does not save a record without it.

## Keys in the tool

| Key | Action |
|---|---|
| a value key | Records that value for the highlighted field and moves to the next field. |
| `u` | Marks the highlighted field unsure, or clears the mark. Press it before the value key, or go back to the field with `↑`. |
| `n` | Moves to the note. `Esc` leaves it. |
| `↑` `↓` | Moves between fields, to change an answer. |
| `Enter` | Saves the record and shows the next unlabeled one. |
| `Backspace` | Returns to the previous record, with its saved labels, for correction. |

Progress is shown as a count. Each save appends one line to the labels
file; a correction appends another, and the later line stands. A
session can stop at any record: the next session starts at the first
record not yet saved.

The relabel pass shows the held-back records again, in a new order,
without their earlier labels. A record is shown in it no earlier than
seven days after its last save in the main pass.

## Revising the vocabulary

One revision of the fields, values and keys is permitted after the
pilot, the first 150 records. After it the guide is frozen. The version
at the top of this guide is recorded in every label: raise it with any
change to a field, a value or a key.

## Worked examples

These records are excluded from the sample. Three are described in
Hebrew script only (3, 4 and 5). Unless marked, every field is `sure`.

### 1. `k10plus|DE-627:604708289`

K10plus. 245 `$a Sefer ʿEn Yaʿaḳov $n 5 $p Neziḳin : 1 ; Bava Ḳama, Bava
Metsiʿa, Bava Batra $c kolel kol ha-agadot mi-Talmud Bavli
ṿi-Yerushalmi ...`; 300 `379 S.`; 773 links to the set record with
`$g 5`.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `Ein Yaakov` | `edition` | `volume` | `dependent` | `library` | `print` |

The main content is the text of Ein Yaakov, the aggadot Ibn Ḥabib
compiled. The record describes one physical volume, numbered 5, of a
multi-volume edition. Its part title names an order and tractates of
the Talmud; without "Sefer ʿEn Yaʿaḳov" it would not say which work
this is, so `dependent`. A union-catalog record (040 `DE-627`), printed
volume.

### 2. `k10plus|DE-627:604707479`

K10plus. 245 `$a Sefer ʿEn Yaʿaḳov $c kolel kol ha-agadot ...`; 264
`$c 5768- [2007 oder 2008-]`; no 300.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `Ein Yaakov` | `edition` | `whole-set` | | `library` | `print` |

The set record that example 1's 773 points to. It describes the
edition as one thing: an open date, no part designation. That it has no
extent at all does not matter; a whole-set record need not count its
volumes.

### 3. `nli|:990010968480205171`

NLI, Hebrew script only. 245 `$a חמשה חומשי תורה : $b מקראות גדולות עם
מ"ד פירושים.`; 250 `[2.`; 300 `1 כרך`; 505 `[2]: ספר שמות`. The 907
and AVD fields record a digitized copy.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `Miqraot Gedolot` | `edition` | `volume` | `dependent` | `library` | `print` |

The title proper is the Pentateuch; the work is named in `$b`. The
record describes one volume, the second, Shemot, of a multi-volume
edition, given in 250 and 505. There is no 773 and no series; a volume
need not be linked to be a volume. Its own title, ספר שמות, would not
identify this edition without the set title. The record describes the
printed volume; the digitized copy it points to does not change the
carrier.

### 4. `nli|:990011409340205171`

NLI, Hebrew script only. 245 `$a אוצר לשון תלמוד ירושלמי : $b
קונקורדאנציה לתלמוד ירושלמי / $c מאת משה ברבי חיים יהושע קוסובסקי.`; 300
`9 כרכים (כרך א-ח, י)`; a 500 note for each volume.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `Talmud Yerushalmi` | `about` | `whole-set` | | `library` | `print` |

A concordance to the Yerushalmi, which stands without the text, so
`about`, although the work's name is in the title. The record describes
nine volumes as one thing.

### 5. `nli|:990000894670705171`

NLI, Hebrew script only. 245 `$a "אור החיים", הפירוש לתורה של רבי חיים בן
עטר.`; 773 `$t מחניים ... $g 4 (תשנג) 282-291`.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `Or ha-Hayim` | `about` | `analytic` | | `library` | `print` |

A ten-page article in the journal Maḥanayim, so `analytic`. It is a
study of Ḥayyim ben Attar's commentary, not the commentary.

### 6. `nli|:990036689780205171`

NLI. 245 `$a 100 ספרי ילדים אהובים / $c כתבה וערכה תמי הראל.`; 246 `100
beloved children's books`; 300 `143 עמודים`; 650 `Children's
literature, Hebrew $v Bibliography`.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `none` | `unrelated` | `single` | | `library` | `print` |

ספרי here is "books of": this is a guide to children's books. It is
not an edition of any particular work and not about one, so `none`,
which records `unrelated`. One volume, not part of a set.

### 7. `k10plus|DE-627:862690056`

K10plus. 245 `$a Ṭur Yoreh deʿah $b hu ha-ṭur ha-sheni me-arbaʿah
ha-ṭurim`; 264 `Ṿin ... 1811`; 300 `336, 10 Blätter`; 490 `Arbaʿah
ha-ṭurim ... $v ha-Ṭur ha-sheni`; 800 links to the set.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `Arbaah Turim` | `edition` | `volume` | `standalone` | `library` | `print` |

One volume of the Vienna edition of the four Turim, which 490 and 800
name and number. "Ṭur Yoreh deʿah" identifies it without the set title.
The text of the Tur is the main content; Bet Yosef and Darkhe Mosheh
are printed with it.

### 8. `oxford|UkOxU:990233156390107026`

Oxford. 245 `$a A bilingual edition of Pesiqta Rabbati. $n Volume 2,
chapters 23-52 / $c translated and edited by Rivka Ulmer.`; 546
`Parallel Hebrew text with English translation.`; 490 and 830 `Studia
Judaica`; 040 `$a GyWOH $b eng $c GyWOH $d UkOxU`; 776 `$i PDF
version`.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `Pesiqta Rabbati` | `edition` | `volume` | `dependent` | `vendor` (unsure) | `print` |

Hebrew text with an English translation, so `edition`. The second
volume of a two-volume edition; Studia Judaica is a series, not the
set. "Volume 2, chapters 23-52" would not identify it without "A
bilingual edition of Pesiqta Rabbati". For origin, 040 `$a` is a book
vendor's code and a 776 is present, both signs of a vendor record, but
040 `$d` shows Oxford modified it, which `library` also covers. The
best choice is `vendor`, marked unsure.

### 9. `oxford|UkOxU:991026784100907026`

Oxford. 245 `$a Die Mischna : $b Text, Übersetzung und ausführliche
Erklärung ... $p Gittin (Scheidebriefe) / $c Dietrich Correns.`; 300
`1 online resource (200 pages)`; 040 `$a DE-B1597 $b eng $c DE-B1597`;
588 `Description based on publisher supplied metadata ...`; 776 with
the print ISBN.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `Die Mischna (Giessen)` | `edition` | `volume` | `dependent` | `vendor` | `online` |

The Giessen Mishnah's tractate Gittin: text, German translation and
commentary. One volume of that edition; "Gittin (Scheidebriefe)" names
a tractate found in many works and editions, so `dependent`. The 040
code is the publisher's and 588 says the description is the
publisher's: `vendor`. An online resource.

### 10. `lc|:5003374`

LC. 245 `$a The Soncino Midrash Rabbah $h [electronic resource].`; 300
`1 CD-ROM ; 4 3/4 in. + 1 manual (61 p. ; 22 cm.) + 2 floppy disks.`;
520 `Includes complete Hebrew text and Soncino English translation of
the Midrash rabbah ...`; 440 `The CD-ROM Judaic classics library`.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `Midrash Rabbah` | `edition` | `single` | | `library` | `other` |

Hebrew text and English translation, so `edition`. One disc holds the
whole work: a one-volume edition of a multi-volume work is `single`,
and the series in 440 does not make it part of a set. A CD-ROM is
neither print nor online, so `other`, with the note "CD-ROM".

### 11. `k10plus|DE-627:1941481469`

K10plus. 130 `Mishnah`; 245 `$a The Oxford annotated Mishnah $n Volume
3 $p [Qodashim - Tohorot - Appendix ...] $c edited by Shaye J.D.
Cohen, Robert Goldenberg, Hayim Lapin`; 773 links to the set with `$g
Volume 3`.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `other-work` | `edition` | `volume` | `dependent` | `library` | `print` |

An annotated English translation of the Mishnah. The list's Mishnah
entry is the Giessen edition only, so this is `other-work`, and its
relation, judged against the Mishnah, is `edition`. Volume 3 of the
set; "Qodashim - Tohorot" names orders of the Mishnah and would not
identify this edition.

### 12. `lc|:14303200`

LC. Leader/07 `s`. 245 `$a Lishkat ha-gazit : $b miḳbats maʼamarim ʻal
mifʻal Mishnah berurah ha-mevoʼar.`; 300 `v.`; 362 `Gil. 1-`; 600
`$t Mishnah berurah $v Periodicals.`; 042 `lccopycat`.

| work | relation | level | own-title | origin | carrier |
|---|---|---|---|---|---|
| `Mishnah Berurah` | `about` | `other` | | `library` | `print` |

A periodical of articles on the Mishnah Berurah ha-Mevoʾar project, so
`about`. A serial is `other`, with the note "serial". The record is
copy cataloging at LC (042), which is `library`.
