# The data

Three files carry the record-level data the study measured. They are
published so the tables can be checked, and they are frozen: nothing
here is revised after publication.

What they check and what they do not: every figure in the marker and
case chapters, and the marker rows in the implications chapter, is
computable from `corpus-features.csv`. The clustering, adjusted mutual
information, bootstrap and stability figures in the signatures chapter
are not — those need the 725-feature vector, which is not published.

| File | Size | Contents |
|---|---|---|
| [`corpus-features.csv`](data/corpus-features.csv) | 1.3 MB | 5,252 rows, one per record |
| [`queries.csv`](data/queries.csv) | 10 KB | 133 of the 136 SRU queries that drew the corpus |
| [`case-records.xml`](data/case-records.xml) | 205 KB | 21 MARCXML records: the six matched items |
| [`set-survey.csv`](data/set-survey.csv) | 4 KB | 110 rows: how each catalog describes each of 22 multi-volume works |

## Why derived data rather than the records

The corpus itself is 5,252 records from five institutions, and
redistributing all of it would mean asserting redistribution rights for
all five. Records the Library of Congress itself created are United
States federal work[^lcterms] — though LC's database also holds records other
institutions created, identified by `040 $a`, and 41 NLI rows in this
corpus carry `040 $aDLC` in the other direction. DNB publishes its
bibliographic data under CC0 1.0, and K10plus states an open licence
for its catalogue data.[^licences] Terms for the National Library of Israel
and the Bodleian are not established here.

`corpus-features.csv` is derived data — a structural description of
each record, not the record — and it carries the `001` control number
and `003` control number identifier of every row. Any record in the
study can be fetched from its own catalog with those, so every claim
stays checkable without republishing anyone's catalog.

The six matched items in `case-records.xml` are published in full
because the case chapter quotes them field by field, and a reader
checking that chapter needs the records in front of them. That file
does include records whose terms are not established above: six from
NLI and three from the Bodleian, alongside five from LC, five from
K10plus and two from DNB. Twenty-one records quoted as evidence is a
different act from republishing a catalogue, but it is not zero, and it
is the one place this study reproduces records rather than describing
them.

## Reproduction, and what it cannot give you

`queries.csv` lists every query, its endpoint and its draw axis. Running
them again against the five endpoints draws a **comparable** corpus. It
does not draw the **same** one.

SRU returns results in a server-determined order, catalogs add and
revise records continuously, and ranking shifts underneath a repeated
query. A redraw is a new sample of the same populations along the same
axes, and its numbers will differ. This is why the frozen CSV matters:
for the figures it covers, it is the only way to check the arithmetic.
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
| `draw_year` | The year **asked for** in the query, not the record's own date. Empty on the 156 publisher-stratum rows, whose queries name no year |

### Leader and 008

| Column | Meaning |
|---|---|
| `ldr06_record_type` | Type of record. Present here: `a` language material (4,449), `p` mixed material (292), `j` musical sound (199), `c` notated music (103), `k` two-dimensional image (82), `g` projected image (53), `i` nonmusical sound (30), `t` manuscript (26), `e` cartographic (9), `d` manuscript music (4), `m` computer file (4), `o` kit (1) |
| `ldr07_bib_level` | Bibliographic level: `m` monograph, `s` serial, `a` monographic component part, `b` serial component part, `c` collection, `d` subunit |
| `ldr17_encoding_level` | Fullness of the description |
| `ldr18_description_form` | Descriptive cataloging form: `c` ISBD punctuation omitted (1,959), `i` ISBD punctuation included (1,344), `a` AACR2 (1,267), blank meaning non-ISBD (410), `u` unknown (253), `-` (11), `p` obsolete partial ISBD (7), `n` (1). This records punctuation, not which rules were applied |
| `ldr19_multipart_level` | Multipart resource record level: `c` part with dependent title (287), `b` part with independent title (59), `a` set (41), `-` (12), empty where not coded (4,853). The tables in the study count `-` as blank. The position was redefined in 2007, which is part of why older records leave it empty[^l19hist] |
| `date_type_008` | `008/06` |
| `year1_008`, `year2_008` | `008/07-10` and `008/11-14`. `year1` is the publication date used for the era tables |
| `place_008`, `lang_008` | `008/15-17` and `008/35-37` |

### Cataloging source: `040`

| Column | Meaning |
|---|---|
| `agency_040a` | Original cataloging agency. Empty on 1,217 of 1,432 NLI rows: NLI omits `$a` on its own original cataloging but keeps it on copy, so 215 NLI rows carry a value (DLC 41, MiAaPQ 26, UkMbAM-D 20, others). DNB values are internal cataloging-unit codes |
| `cataloging_lang_040b` | Language of cataloging. NLI is mixed: 634 empty, 528 `eng`, 266 `heb`, 4 other |
| `convention_040e` | Description convention: empty (3,020), `rda` (1,544), `rakwb` German RAK-WB (621), `pn` provider-neutral e-resource record (65), `ncafnor` (1), `gihc` (1) |

### Markers

Each is `1` or `0`. These are the definitions the marker chapter uses,
except `has_505_t`, which is carried in the file but not used there.

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
and `records_first_seen_here`. It holds 133 rows, not the 136 queries
the draw issued: three LC queries — `dc.subject="Rabbinical literature"`
for 1900, 1925 and 1950 — returned no records and so appear nowhere in
the corpus the file is derived from.

That last column needs care in two ways. Records were deduplicated on
`003` plus `001` across the whole draw, and each is attributed to the
first query that returned it, so a query whose results were mostly
returned earlier shows a low count. It is not a measure of how many
records the query matches; the catalogs' own totals, which the study
did not record per query, would be needed for that.

And "first" depends on the order the draw ran, which was a shuffle
seeded with `0` to interleave the servers, while this file is sorted by
catalog and query. The run order cannot be reconstructed from the file.

## `set-survey.csv`

One row per work and catalog, 22 works by 5 catalogs. Every table in
the [set chapter](sets.md) is computed from this file.

| Column | Meaning |
|---|---|
| `work`, `catalog` | The work as named in the survey; `lc`, `oxford`, `nli`, `dnb`, `k10plus` |
| `returned` | Records in the SRU response, before any filter |
| `named` | Of those, records whose `245` begins with the work's name. A title query returns books *about* a work as well as editions of it |
| `monograph` | Of those, records with `leader/07` `m`. The remainder are archival subunits, journal articles and analytic entries |
| `vendor_online` | Of the monographs, records whose `300 $a` says "online resource". Publisher-supplied e-records, counted separately because a run of them imitates per-volume library cataloging |
| `library` | `monograph` minus `vendor_online`. This is the denominator for every rate in the set chapter |
| `l19_a`, `l19_b`, `l19_c` | Library records coding leader/19 as a set, a part with an independent title, or a part with a dependent title |
| `t773` | Records carrying a host item entry |
| `np` | Records enumerating a part in `245 $n` or `$p` |
| `t505` | Records carrying a contents note |
| `extent_counted` | `300 $a` states a number of volumes: `3 v.`, `9 Bände` |
| `extent_open` | `300 $a` is open-ended: `v.`, `volumes`, `v. <1-27, 29-53>`. An earlier version of this study missed 168 LC records by requiring a leading digit |
| `set_level_extent` | The two above summed: records whose extent says the description covers a whole set |
| `truncated` | 1 where the response hit the fifty-record cap, so the row is a floor. 66 of the 110 rows are truncated |

Query forms differ per catalog — Hebrew at NLI, romanized elsewhere,
German forms at DNB — so `returned` and `library` are not comparable
holdings figures between catalogs. They support comparison of *rates
within* a catalog.

The queries are in `set_cases.py`; the title patterns and filters in
`set_report.py`, both under
[`studies/cataloging-practice/`](https://github.com/dchud/otzar/tree/main/studies/cataloging-practice).

The works were chosen by hand as the multi-volume works a Torah-study
collection is built from. That makes the file evidence that both
treatments occur widely on works every catalog holds, and not an
estimate of prevalence in any population.

## `case-records.xml`

A MARCXML collection of the 21 records behind the case chapter: six
ISBNs, each fetched from all five catalogs, with a record for every
catalog that holds it. An XML comment before each record gives its ISBN
and catalog. The record content is as retrieved; the bytes are not,
since the records were re-serialised into a single collection element
with those comments added.

## The scripts

The code that drew the corpus, built the feature vector, ran the
clustering, computed every table and generated the figures and the files
above is in the repository under
[`studies/cataloging-practice/`](https://github.com/dchud/otzar/tree/main/studies/cataloging-practice).
Its README gives the order the scripts ran in, what each produced, and
what they expect to find on disk.

The scripts are kept as they ran rather than tidied, so that the
committed code is the code the published numbers came from.

## Regenerating everything

The endpoints are listed in the [overview](index.md). Requests were
spaced at least four seconds per host, 50 records per query, with
`recordSchema=marcxml` except DNB, which requires `MARC21-xml`.

Running the scripts needs the corpus, which is not in the repository —
`corpus-features.csv` is a structural description of each record, not
the records. The corpus and the feature vector are distributed as a
separate archive; unpack it to `tmp/vagf/` and the pipeline runs from
`featurize.py` onward.

[^lcterms]: **Not verified here.** That works of the United States
    federal government are not subject to domestic copyright is
    external to this study, and its application to a specific
    bibliographic record depends on who created that record. Confirming
    it for any given row means reading its `040 $a`.

[^licences]: **Not verified here.** These licence terms are stated from
    general knowledge of the two agencies' open-data practice, not read
    from their published terms during this work. Confirm against the
    current licence statements at the DNB and K10plus data-service
    pages before relying on them.

[^l19hist]: **Not verified here.** That leader/19 was redefined in 2007
    from an earlier meaning comes from MARC 21 change documentation.
    Confirming it means reading the leader specification's change
    history.
