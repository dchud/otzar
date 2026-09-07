# Six items, side by side

The aggregate tables compare catalogs holding different books, so a
difference in prevalence could be a difference in the material rather
than in the cataloging. These six items remove that ambiguity: each is
one work, held by two to four of the catalogs, matched on ISBN.

Every record is cited by its `001` control number, its `003` control
number identifier where present, and its leader, so the comparisons can
be checked against the source catalogs.

Overlap in the corpus is thin — 35 ISBNs appear in more than one
catalog — so these are illustrations of mechanisms the aggregate tables
measure, not an independent sample. A matched-pair test on 35 items
would have no power.

## 1. Same software, same rules, different institution

**Yoshe kalb**, Israel Joshua Singer, Sweden: l'Aleph, 2015.
ISBN 9789176370582. Held by NLI and Oxford; not held by LC, DNB or
K10plus.

| | NLI | Oxford |
|---|---|---|
| Leader | `01097cam a2200313 i 4500` | `00000nam a22      i 4500` |
| leader/06, /07, /18 | `a`, `m`, `i` | `a`, `m`, `i` |
| `001` | `990040883010205171` | `990206784250107026` |
| `003` | *(absent)* | `UkOxU` |
| `040` | `$aEQO $cEQO $dOCLCO $beng $erda` | `$aUkOxU $beng $erda $cUkOxU` |
| `100` | `1# $aSinger, Israel Joshua, $d1893-1944 $9lat $eauthor $8PreferredLanguageHeading` | `1# $aSinger, Israel Joshua, $d1893-1944, $eauthor.` |
| `240` | `10 $aYoshe ḳalb` | `10 $aYoshe ḳalb` |
| `245` | `10 $aYoshe kalb $h[on order] / $cIsrael J. Singer.` | `10 $aYoshe kalb / $cIsrael J. Singer.` |
| `264` | `#1 $aSweden : $bl'Aleph, $c[2015?]` | `#1 $aSweden : $bl'Aleph, $c[2015?]` |
| `300` | `$a341 pages ; $c21 cm.` | `$a341 pages ; $c21 cm` |
| Tags present | 020 035 040 041 100 240 245 264 300 336 337 338 590 900 901 903 906 939 999 | 020 035 040 100 240 245 264 300 336 337 338 AVA |

Both are RDA (`040$e rda`, leader/18 `i`). The description is the same
work of cataloging down to the punctuation. The divergence is entirely
in fields that are not about the book: NLI adds `590`, `900`, `901`,
`903`, `906`, `939` and `999`; Oxford adds `AVA`. That is the
institutional signature the clustering measures, seen in one item.

Two details do differ bibliographically. NLI's `245$h [on order]`
records a local acquisition state inside a bibliographic subfield. And
NLI tags its heading with `$9lat` and
`$8PreferredLanguageHeading` — its own mechanism for recording which
script a heading is in, where other catalogs use `880`.

## 2. One record, propagated: LC, Oxford and K10plus

**100 sipurim Erets-Yiśreʼeliyim**, Zeʼev Ṿalk, Jerusalem: Karmel,
2015. ISBN 9789655404487. Held by NLI, LC, Oxford and K10plus.

LC and Oxford carry what is recognisably the *same record*:

| | LC | Oxford |
|---|---|---|
| `001` | `18601508` | `990205839580107026` |
| `003` | *(absent)* | `UkOxU` |
| `040` | `$aWEINB $beng $erda $cWEINB $dHLS $dOCLCO $dCGU $dLTSCA $dCUY $dUMC $dOCLCF $dCOO $dDLC` | `$aWEINB $beng $erda $cWEINB $dDLC $dHLS $dCGU $dLTSCA $dCUY $dUMC $dOCLCF $dCOO $dOCLCO $dZCU $dUkOxU` |
| `245` | `10 $6880-02 $a100 sipurim Erets-Yiśreʼeliyim = $b100 Israeli stories / $cZeʼev Ṿalk.` | *identical* |
| `880` for `245` | `10 $6245-02/(2/r $a100 סיפורים ארץ־ישראליים = ...` | `10 $6245-02//r $a100 סיפורים ארץ־ישראליים = ...` |

Both `040` chains begin `$aWEINB` and accumulate the same
institutions, ending `$dDLC` for LC and `$dUkOxU` for Oxford. Neither
library created this description; both received it and appended
themselves.

This qualifies the "institutional signature" finding in an important
way. Part of what separates LC from Oxford in the clustering is not
independent practice but **position in a copy-cataloging network**. The
bibliographic content travelled; only the local fields are each
library's own.

The `$6` linkage syntax, however, is not shared:

| Catalog | `$6` on the `880` paired with `245` |
|---|---|
| LC | `245-02/(2/r` |
| Oxford | `245-02//r` |
| K10plus | `245-01/Hebr/r` |

Three encodings of the same fact — that this field is Hebrew script,
right-to-left. Any parser reading `$6` has to accept all three shapes.

NLI's record for this book is unrelated to the other three. It carries
no `880` at all, puts `$a100 סיפורים ארץ-ישראליים` directly in `245`,
declares `040$b heb` — the record itself is *catalogued in Hebrew* —
and has no `040$a` at all.

K10plus differs again: `040$e rakwb` for the German rules, `$4aut`
relator codes rather than `$e author`, and `$9` on `020` carrying the
hyphenated ISBN alongside the plain one in `$a`.

## 3. The same object is a different kind of thing

**41 muzik-lider**, Motl Polianski, Tel Aviv: Y.L. Peretz, 1995.
ISBN 9789657012017. Held by NLI, LC and K10plus.

| | NLI | LC | K10plus |
|---|---|---|---|
| Leader | `05177nam a2200541 i 4500` | `04885ccm a2200865 i 4500` | `      ccm a22      c 4500` |
| **leader/06** | **`a` language material** | **`c` notated music** | **`c` notated music** |
| `001` / `003` | `990013807730205171` / — | `20115513` / — | `1606747541` / `DE-627` |
| `240` uniform title | *(absent)* | `10 $aSongs. $kSelections` | *(absent)* |
| `245` | `10 $a41 מוזיק לידער : $bצו טעקסטן פון יידישע דיכטער` | `10 $a41 muzik-lider tzu tekstn fun Yidishe dikhter` | `13 $a41 Muzik-Lider $btzu tekstn fun yidishe Dichter = 41 melodies...` |
| `300` | `$a[7], 82, [5] עמודים : $bתוים ; $c25 ס"מ.` | `$a1 score (82 pages) ; $c25 cm` | `$a82 S. $bNoten` |
| `505` contents | *(absent)* | 0# listing each song | *(absent)* |
| `700` added entries | *(none)* | **19**, one per poet | *(none)* |

The same physical item is language material at NLI and notated music at
LC and K10plus. LC's record additionally carries a uniform title, an
enumerated contents note, and nineteen name added entries — one for
each poet whose text is set — none of which exist in the other two
records.

For otzar this is the sharpest warning in the study. A rule that
branches on leader/06 to decide how to read a record will take three
different branches for one book. And the analytic access LC provides —
nineteen names and a song-level contents note — simply does not exist
in the NLI or K10plus description of the same object.

## 4. One series, four treatments

**Hiob: eine biblische Tragödie in drei Akten**, Itzhak Katzenelson,
Berlin/Münster: LIT, 2015. ISBN 9783643120649. Held by NLI, LC, DNB
and K10plus.

All four place it in the series *Limmud - Beiträge zum Judentum*.

| | `490` | `830` | Notes |
|---|---|---|---|
| NLI | `1# $aLimmud - Beiträge zum Judemtum, Quellen ; $vBand 1` | `#0 $aLimmud - Beiträge zum Judemtum, Quellen ; $vBd. 1 $9lat` | traced; series title carries a typo |
| LC | `0# $aLimmud- Beiträge zum Judemtum, Quellen ; $vBand 1` | *(absent)* | **untraced**; no authorized form |
| DNB | `1# $aLimmud - Beiträge zum Judentum : [...], Quellen $vBand 1` | `#0 $aLimmud - Beiträge zum Judentum $n[...] $pQuellen $vBand 1 $w(DE-101)1123042594 $w(DE-600)2879631-7 $911 $7as` | traced; `$n`/`$p` split; two `$w` links |
| K10plus | `1# $aLimmud - Beiträge zum Judentum, Quellen $vBand 1` | `#0 $aLimmud - Beiträge zum Judentum $pQuellen $vBand 1 $91 $w(DE-627)876300859 $w(DE-576)475911784 $w(DE-600)2879631-7 $x2699-5344 $7am` | traced; **ISSN in `$x`**; three `$w` links |

Record identifiers: NLI `001 990036510430205171`; LC `001 19725345`;
DNB `001 1032587253`, `003 DE-101`; K10plus `001 885337603`,
`003 DE-627`.

One series, four descriptions of it:

- **LC alone does not trace it.** `490` first indicator `0` and no
  `830`. A lookup that expects an authorized series heading finds
  nothing, for a book that is unambiguously part of a series.
- **Only K10plus supplies the ISSN**, `$x2699-5344`. The identifier
  that would let otzar match this series across catalogs exists in
  exactly one of the four records.
- **Only the German catalogs supply `$w` control-number links** to the
  series authority — and they link to different authority files
  (`DE-101`, `DE-627`, `DE-576`, `DE-600`), one of which, `DE-600`, is
  shared between them.
- **The series title itself differs.** NLI and LC both read
  "Judemtum", a typo for "Judentum"; the German catalogs read it
  correctly. String matching on series title fails across this pair for
  a single transposed letter.
- **Subfield structure differs.** DNB and K10plus split the subseries
  into `$p Quellen`; NLI and LC run it into `$a` after a comma.

The name authority differs too. NLI and LC give
`Katzenelson, Itzhak`; DNB and K10plus give `Ḳatsenelson, Yitsḥaḳ`
with GND identifiers in `$0`. And the place of publication is
"Münster" at NLI, "Berlin" at LC, and both at DNB and K10plus.

## 5 and 6. Two further confirmations

**Tse tame: gerush ruḥot**, Sara Zfatman, Jerusalem: Magnes, 2015.
ISBN 9789654938044, NLI `001 990038641240205171`. NLI again catalogs in
Hebrew with `040$b heb`, Hebrew directly in `245`, no `880`, and
`$9heb $8PreferredLanguageHeading` on the `100` — the same mechanism as
case 1, on unrelated material.

**"Ausgestopfte Juden?"** ISBN 9783835352599, held by DNB and LC. The
German record carries `015`, `016`, `044` and `850`; the LC record
carries `906`, `925`, `955`. Neither field group says anything about
the book.

## What the six show together

The aggregate tables report that catalogs differ. These records show
*how*, and the mechanisms are distinct:

1. **Local blocks diverge while descriptions agree** (case 1) — the
   dominant clustering signal, and bibliographically empty.
2. **Descriptions agree because they are the same record** (case 2) —
   copy cataloging, which means institutional clusters partly measure
   network position rather than independent practice.
3. **Script placement is a house decision** (cases 1, 2, 5) — Hebrew in
   `245` or in `880`, with three `$6` syntaxes.
4. **Material type is a judgement, not a fact** (case 3) — leader/06
   differs for one object, and analytic access differs with it.
5. **Series evidence is unevenly recorded** (case 4) — tracing, ISSN,
   authority links and even spelling vary across four records of one
   series.
