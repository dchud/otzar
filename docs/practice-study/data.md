# The data

Three files carry everything the study measured. They are published so
the tables can be checked and the analysis redone, and they are frozen:
nothing here is revised after publication, because every number in the
other five pages is computed from exactly these bytes.

| File | Size | Contents |
|---|---|---|
| [`corpus-features.csv`](data/corpus-features.csv) | 1.3 MB | 5,252 rows, one per record |
| [`queries.csv`](data/queries.csv) | 10 KB | the 133 SRU queries that drew the corpus |
| [`case-records.xml`](data/case-records.xml) | 205 KB | 21 MARCXML records: the six matched items |

## Why derived data rather than the records

The corpus itself is 5,252 records from five institutions, and
redistributing it would mean asserting redistribution rights for all
five. Library of Congress records are United States federal work; DNB
and K10plus publish their metadata openly. The terms for the National
Library of Israel and the Bodleian are not established here, so their
records are not republished.

`corpus-features.csv` is derived data — a structural description of
each record, not the record — and it carries the `001` control number
and `003` control number identifier of every row. Any record in the
study can be fetched from its own catalog with those, so every claim
stays checkable without republishing anyone's catalog.

The six matched items in `case-records.xml` are published in full
because the case chapter quotes them field by field, and a reader
checking that chapter needs the records in front of them. Twenty-one
records is a quotation, not a redistribution of a catalog.

## Reproduction, and what it cannot give you

`queries.csv` lists every query, its endpoint and its draw axis. Running
them again against the five endpoints draws a **comparable** corpus. It
does not draw the **same** one.

SRU returns results in a server-determined order, catalogs add and
revise records continuously, and ranking shifts underneath a repeated
query. A redraw is a new sample of the same populations along the same
axes, and its numbers will differ. This is why the frozen CSV matters:
it is the only way to check the arithmetic in the other five pages.
Anyone redrawing the corpus is running a replication, which is a
different and also useful thing.

If the study is ever redrawn, the new file belongs beside this one under
its own name rather than replacing it. Overwriting would silently
invalidate every number already published.

## Column dictionary: `corpus-features.csv`

### Identity and provenance

| Column | Meaning |
|---|---|
| `record_id` | Study-local identifier, `catalog\|003:001` |
| `catalog` | `nli`, `lc`, `dnb`, `k10plus`, `oxford` |
| `control_number` | MARC `001` |
| `control_number_identifier` | MARC `003`; empty where the record carries none |
| `query` | The CQL that first returned this record |
| `draw_axis` | `language+year`, `subject+year`, `publisher`, `control` |
| `draw_domain` | `judaica` or `control` |
| `draw_year` | The year **asked for** in the query, not the record's own date |

### Leader and 008

| Column | Meaning |
|---|---|
| `ldr06_record_type` | Type of record: `a` language material, `c` notated music, `j` musical sound, `k` two-dimensional image, `p` mixed material, `t` manuscript |
| `ldr07_bib_level` | Bibliographic level: `m` monograph, `s` serial, `a` monographic component part, `b` serial component part, `c` collection, `d` subunit |
| `ldr17_encoding_level` | Fullness of the description |
| `ldr18_description_form` | Descriptive cataloging form: `a` AACR2, `c` ISBD punctuation omitted, `i` ISBD punctuation included, `u` unknown. This records punctuation, not which rules were applied |
| `ldr19_multipart_level` | Multipart resource record level: `a` set, `b` part with independent title, `c` part with dependent title, empty where not coded |
| `date_type_008` | `008/06` |
| `year1_008`, `year2_008` | `008/07-10` and `008/11-14`. `year1` is the publication date used for the era tables |
| `place_008`, `lang_008` | `008/15-17` and `008/35-37` |

### Cataloging source: `040`

| Column | Meaning |
|---|---|
| `agency_040a` | Original cataloging agency. Empty on NLI records, which omit `$a`. DNB values are internal cataloging-unit codes |
| `cataloging_lang_040b` | Language of cataloging. NLI records carry `heb` |
| `convention_040e` | Description convention: `rda`, `rakwb`, `pn`, or empty |

### Markers

Each is `1` or `0`. These are the definitions the marker chapter uses.

| Column | True when |
|---|---|
| `has_773` | Any `773` host item entry |
| `has_490` | Any `490` series statement |
| `has_490_traced` | The first `490` has first indicator `1` |
| `has_830` | Any `830` series added entry |
| `has_800_810_811` | Any name-title series added entry |
| `has_440` | Any `440`, obsolete since 2008 |
| `has_245_n_or_p` | `245` carries `$n` or `$p` |
| `has_246` | Any `246` variant title |
| `has_505` | Any `505` contents note |
| `has_505_t` | A `505` carrying `$t`, an enhanced contents note |
| `has_740` | Any `740` added entry |
| `has_730` | Any `730` uniform title added entry |
| `has_130_or_240` | Any `130` or `240` uniform title |
| `has_880` | Any `880` alternate graphic representation |
| `has_020` | Any `020` ISBN |
| `has_300_c` | `300` carries `$c` dimensions |

### Full tag list

| Column | Meaning |
|---|---|
| `datafield_tags` | Every distinct datafield tag on the record, space separated, sorted |

This column is what makes the file reusable rather than only checkable.
The clustering used a richer representation — tag, tag-plus-subfield,
tag-plus-indicator-value, repeated-field and `008` shape features — and
that vector is not published, but `datafield_tags` supports tag-level
co-occurrence work directly.

## `queries.csv`

One row per query, with the catalog, the CQL, the draw axis and domain,
and `records_first_seen_here`.

That last column needs care. Records were deduplicated on `003` plus
`001` across the whole draw, and each is attributed to the first query
that returned it. A query whose results were mostly returned by an
earlier query shows a low count. The column is not a measure of how
many records that query matches — the catalogs' own totals, which the
study did not record per query, would be needed for that.

## `case-records.xml`

A MARCXML collection of the 21 records behind the case chapter: six
ISBNs, each fetched from all five catalogs, with a record for every
catalog that holds it. An XML comment before each record gives its ISBN
and catalog. The records are as retrieved, unmodified.

## Regenerating everything

The endpoints are listed in the [overview](index.md). Requests were
spaced at least four seconds per host, 50 records per query, with
`recordSchema=marcxml` except DNB, which requires `MARC21-xml`.
