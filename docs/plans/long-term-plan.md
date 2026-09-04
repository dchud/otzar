# otzar — Long-term plan

This document describes where otzar stands as of September 2026 and lays
out a forward plan. It is written for a person or agent picking up the
project later, without assuming familiarity with the code. The earlier
planning documents in this directory (`app-plan.md`,
`implementation-plan.md`, `extract-from-experiments.md`) describe the
original design; this one describes what was built, what was not, and what
to do next. Work is tracked in beads (`br`); this document points at bead
IDs rather than restating them, and `bd-1yg` covers what happens to the
documents in this directory, including this one.

Bead IDs carry either the current `bd-` prefix or the older `otzar-`
prefix. Children created under a parent get a dotted ID (`bd-k0s.1`).

---

## 1. Purpose and vision

otzar is a catalog for a small circle of friends cataloging a shared
collection of books. The collection is heavy in right-to-left scripts —
Hebrew, Aramaic, Yiddish — alongside English, and records often carry both
original-script and romanized forms of titles and names.

What the project is for:

- **Quick to use.** Cataloging a book should take a few taps, not a form.
- **Multilingual by design.** Hebrew and romanized forms are both stored,
  displayed, and searchable. Right-to-left text renders correctly next to
  left-to-right text.
- **Automates what can be automated.** Barcode scans and title-page photos
  pull full bibliographic records from national libraries so people type
  as little as possible.
- **Device handoffs.** A phone is the camera; a laptop is the review desk.
  Moving work between them takes one QR scan, not a login and a URL.
- **Uses the depth of bibliographic records.** MARC records carry authors,
  subjects, series, places, dates, and identifiers; all of it should feed
  search, browse, and related-items views.
- **Several users of one catalog.** A few people cataloging together;
  anyone can browse and search.
- **Possibly several catalogs on one server, later.** Optional; see §6.

**Scale constraint:** each catalog holds at most a few thousand items, and
a server might someday host 5–7 such catalogs. SQLite, one small VM, and
synchronous request handling are the right fit. Nothing here needs
PostgreSQL, a job queue, or a search server unless something is measurably
broken without them.

---

## 2. Current state

An inventory of what exists and works, checked against the code on `main`
on 2026-09-04.

### 2.1 The three Django apps

- **`catalog`** — the data models, full-text search, browse views, record
  detail pages, and the home page.
- **`sources`** — clients for external bibliographic services: SRU catalog
  search (NLI, LC, DNB), VIAF authority lookup, MARC parsing, the search
  cascade, publisher-string normalization, Open Library cover lookup, and a
  response-cache wrapper. It has no database models (`sources/models.py`
  is empty); everything it retrieves is handed to the caller or stored via
  `catalog` models. The Django file cache at `DATA_DIR/cache` is its only
  persistence.
- **`ingest`** — the data-entry workflows: manual entry, ISBN/barcode
  scanning, title-page OCR, the review queue, QR phone handoff, authority
  checking, and series volume management. Its models are `ScanResult` (a
  scan awaiting review) and `APIUsageLog` (cost tracking; see 2.9).

### 2.2 Data model (`catalog/models.py`, `ingest/models.py`)

- **Record** — title plus romanized title, subtitle, publication date (an
  integer year for sorting plus a display string for dates like "ca.
  1850"), place, language, notes, cover image URL, and the source MARC
  record as JSON (`source_marc`) with its source catalog. Each record gets
  a public ID like `otzar-3f8a` — a configurable prefix (`RECORD_ID_PREFIX`)
  plus a base62 encoding of the row number (`catalog/id_generation.py`) —
  and a Unicode slug for readable URLs, Hebrew included. Many-to-many links
  to Author, Subject, Publisher, and Location. `language` stores the MARC
  bibliographic language code; templates render it as a name through
  `catalog/language_codes.py`.
- **Author** — name, romanized name, VIAF ID, and a JSON list of variant
  name forms.
- **Subject** — heading, romanized heading, source (LC/NLI/local).
- **Publisher** — name, romanized name, place.
- **Series / SeriesVolume** — a series with optional total volume count;
  SeriesVolume links a series to a record with a string volume number and a
  `held` flag, so gaps ("we own 4 of 10") are representable.
- **SeriesClaim / SeriesClaimRow** — a claim over a volume specification
  ("1-13", "all 8") made from one scan, with one row per volume carrying
  its search status, candidate records, selected candidate, and created
  record. Data model only; no view creates or reads a claim yet (the
  `otzar-zwg` epic, §4.2).
- **Location** — a freeform shelf label ("Floor 1, Room B, Shelf 4a").
- **ExternalIdentifier** — ISBN, LCCN, LC classification, Dewey, NLI
  control number, VIAF ID, OCLC number, unique per record.
- **TitlePageImage** — a record-linked image with a permanent upload path
  and a `staged` flag. The model and admin inline exist; no ingest path
  creates one (`bd-yg9`, §4.3).
- **ScanResult** (ingest) — a scan in one of four states (`awaiting_ocr`,
  `pending`, `confirmed`, `discarded`): type (ISBN or OCR), the ISBN or
  the image, raw OCR output, candidate records as JSON, the selected
  candidate, the created record, and who scanned it. Images are stored
  under `media/staging/YYYY/MM/DD/`.
- **APIUsageLog** (ingest) — api, model, user, and token counts. Nothing
  writes to it (`bd-y1g.3`).

One fact a reader of the schema would not guess: `source_marc` is null on
every record created before 2026-09-04. Until that day `parse_record` did
not emit the key the confirm path reads (`bd-lg9`); the source documents
were not kept, so those records cannot be backfilled, and anything built
on the field has to tolerate its absence.

### 2.3 Ingest paths

All require login. Landing page at `/ingest/`, and every ingest page
carries a mode bar switching between barcode, title page, and manual
entry.

- **Manual entry** (`/ingest/new/`) — a form for title, romanized title,
  subtitle, dates, place, language (autosuggest at `/api/languages/`
  returning ISO 639 bibliographic codes), notes, plus one author, one
  publisher, and one location. The same form edits existing records
  (`/ingest/edit/<id>/`) and shows only the first of each relation
  (`bd-eqq`).
- **ISBN/barcode scan** (`/ingest/scan/`) — browser-based barcode reading
  from the camera; the ISBN is looked up in NLI (`alma.isbn`), LC
  (`bath.isbn`), and DNB (`dnb.num`). Candidates are shown with expandable
  detail; selecting one pre-fills a confirmation page. Every lookup creates
  a ScanResult so it appears in the review queue.
- **Title-page OCR** (`/ingest/scan-title/`) — upload or photograph a
  title page. The image is stored on `ScanResult.image` with status
  `awaiting_ocr`; either device can review the photo and run OCR
  (`/ingest/scan-title/<id>/ocr/`) or discard it (which deletes the file)
  before API tokens are spent. OCR sends the image to Claude
  (`ingest/ocr.py`, default model `claude-sonnet-5`, `CLAUDE_MODEL` to
  override) with a prompt covering ALA-LC Hebrew romanization, gematria
  date conversion, and no-nikkud rules, and a JSON schema that constrains
  the reply to eight fields; truncated or refused replies are reported as
  failures rather than parsed. The extracted fields are editable
  (`/ingest/scan-title/<id>/edit/`); "Search catalogs" runs the cascade
  (2.5) and shows candidates. A failed re-run discards the previous
  extraction (`bd-xtx`).
- **Confirm** — both confirm paths (the review page and the queue's "Use
  this") build the record through one function,
  `_create_record_from_candidate`, which creates or reuses authors,
  publishers, subjects, and identifiers from the candidate, fetches a
  cover, and indexes the record. Authors are matched by exact name only
  (`otzar-1yn.1`, §4.1).
- **Review queue** (`/ingest/queue/`) — pending scans with candidates;
  confirm creates the record, discard marks the scan discarded. Users see
  their own scans; staff see everyone's. `cleanup_staging` deletes
  discarded scans after 30 days but sweeps the wrong image directory
  (`bd-4jn`). The queue's presentation is being reworked (`bd-73m`,
  `bd-nzb`) and candidates are to be scored against the OCR output
  (`bd-mb8`).
- **QR phone handoff** — `/ingest/qr/` renders a QR code containing a
  signed token (one-hour expiry) that names a target, `isbn` or `title`.
  Scanning it logs the phone in as the same user and opens a streamlined
  capture screen for that target; the desktop polls (`/ingest/scan/poll/`,
  `/ingest/scan-title/poll/`) and shows arriving scans and photos. Both
  targets work; one QR locks the phone to one target (`otzar-ts6`).
- **Authority check** (`/ingest/authority-check/`) — an HTMX endpoint used
  during manual entry that checks a typed author name against existing
  Authors by exact name, exact romanized name, or normalized variant-name
  match (`ingest/authority.py`).
- **Series management** (`/ingest/series/<id>/`) — add volumes to a series
  from a spec like "1-13", "all 8", or "1, 3, 5"; gaps are detected.
  Volume designations in Arabic digits, Hebrew letters (gematria), and
  Roman numerals normalize to one form (`normalize_volume_number` in
  `ingest/series_workflow.py`).

### 2.4 What landed between July and September 2026

The July version of this document described the phone-to-desktop
title-page handoff as an open pull request. It merged on 2026-09-04,
followed the same day by: MARC parsing fixes (non-sorting delimiters
stripped, subject subdivisions assembled and deduplicated), with a repair
command for rows written before the fix; the source MARC record carried
through to every new record; publisher
strings normalized before catalog queries; schema-constrained OCR output;
language codes rendered as names; volume-number normalization; the
SeriesClaim data model; title-page capture fixes (decode failures
surfaced, staged images named for their bytes); a repository link and the
running commit in the site chrome; repairs to the check environment; and
the working conventions in `CLAUDE.md` and `AGENTS.md`, including the
process-label lint that `docs/plans/` is exempt from.

### 2.5 External sources (`sources/`)

- **SRU client** (`sru.py`) — httpx with a polite delay between requests
  (default 3 seconds, `SRU_REQUEST_DELAY`), 30-second timeout, structured
  success/error results. Instances for NLI (SRU 1.2, with automatic
  quoting of `alma.*` values), LC (SRU 1.1), DNB, and VIAF; endpoints
  overridable by env vars.
- **Cascade engine** (`cascade.py`) — data-driven lists of progressively
  broader CQL queries. NLI has 7 steps (title+place+date down to title
  alone); LC has 4 (romanized title+date down to a multi-word Hebrew
  keyword query). The engine stops at the first step returning records.
  Publisher values pass through `normalize_publisher` (`normalize.py`)
  before substitution. The result carries the step name and query, which
  the view does not show (`otzar-g4d`). DNB is queried for ISBN lookup
  only; there is no DNB cascade (`bd-x9w`).
- **MARC parsing** (`marc.py`) — extracts records from SRU envelopes with
  `mrrc` and parses title, author, publication, date, language, ISBN,
  LCCN, OCLC, classifications, additional authors (700), subjects (650,
  with subdivisions), and series (490/830). Handles LC's pattern (Hebrew in
  linked 880 fields) for title and author only; subjects and series read
  the primary field alone (`bd-wnx`). Carries the whole record through to
  the candidate as MARC-in-JSON (`source_marc`), uncleaned, at roughly
  4–5 KB per candidate.
- **VIAF client** (`viaf.py`) — a search-cascade client that parses VIAF
  clusters and scores the best match. Built and unit-tested; not called
  from any ingest or catalog flow.
- **Covers** (`covers.py`) — Open Library cover lookup by ISBN/OCLC/LCCN,
  called at confirm time and available as a backfill command
  (`fetch_covers`).
- **Response cache** (`cache.py`) — a wrapper over Django's file cache
  with a 30-day TTL, keyed on URL plus parameters. Built and unit-tested;
  not wired into the SRU or VIAF clients, so every external query goes to
  the network (`bd-y1g.1`).

### 2.6 Search (`catalog/search.py`, `catalog/search_views.py`)

SQLite FTS5 in a virtual table covering title, romanized title, subtitle,
authors, subjects, publishers, place, notes, and external identifiers.
Related-model text is denormalized into the index when a record is
indexed. Indexing happens in the ingest views when records are created or
edited, not via signals, so records edited or deleted through the Django
admin go stale in the index, and there is no reindex management command
(`bd-y1g.2`).

The query is split into words, each quoted, and all words must match as
whole tokens: "Rambam" finds records containing that token; "Ramb" finds
nothing; Hebrew words with attached prefix particles do not match their
base form. The user guide says partial words match, which is wrong
(`bd-k0s.1`, `bd-k0s.2`). The search page is at `/search/`; the site
navigation links to it and has no search box (`bd-k0s.3`).

### 2.7 Browse (`catalog/browse_views.py`) and record pages

Nine paginated browse views: authors (with record counts), titles
(Hebrew-script first, then Latin), subjects, publishers, dates (by
decade), locations, series (with held/gap counts), places (normalized from
MARC punctuation), and detail pages for authors, subjects, and places. The
record page shows all fields with right-to-left handling, links to browse
pages, other works by the same author, sibling series volumes with gap
indicators, external identifiers, a cover image, and the source MARC in
tagged form when present. Staff can edit or delete records from the page;
delete removes the record from the index. The header links to the
repository and the footer shows the running commit.

### 2.8 Multilingual and accessibility

- A `bidi` template-tag library wraps text in `dir="rtl"`/`dir="ltr"`/
  `dir="auto"` spans based on Hebrew character detection, used across
  browse, search, detail, and ingest templates. Form inputs for title,
  subtitle, and place use `dir="auto"`.
- Dark mode with a toggle (Alpine.js plus localStorage, defaulting to
  system preference); skip-to-content link; visible focus rings; 44px
  touch targets in navigation.
- The interface language is English. HTMX and Alpine.js load from the
  unpkg CDN, so interactivity needs internet access (`bd-b4a`).

### 2.9 Auth and multi-user

- Django's built-in auth. Browse and search are public; ingest views
  require login; record edit requires login and delete requires staff.
  Accounts are created through the admin.
- **Site password** (`otzar/middleware.py`): if `SITE_PASSWORD` is set,
  anonymous visitors see a password page before any public page. It is
  configured by environment variable only.
- Records track `created_by`; scans track `scanned_by`. The review queue
  is scoped per user unless the viewer is staff, so the "several people
  scan, one reviews" workflow requires the reviewer to be staff
  (`bd-2lp`).
- `APIUsageLog` has a model and an admin page; no code writes to it
  (`bd-y1g.3`).

### 2.10 Deployment, operations, CI

**There is no deployment.** The app has never run anywhere but a
developer's machine. The repository carries a Fly.io configuration
(`fly.toml`, a deploy workflow that fails on every push to `main` because
the Fly app was never created, and Fly-specific prose in
`docs/deployment.md` and `docs/administration.md`) for a target that has
been abandoned. `bd-mej` removes that footprint. `bd-n7a` plans the
replacement: AWS, with S3 backups and a restore that has been run rather
than documented. `Dockerfile` and `entrypoint.sh` (migrations, then
gunicorn) have no platform coupling and stay. `.env.example` carries
`AWS_*` keys, unused, placed there for Litestream.

- **CI**: `ci.yml` runs format check, lint, the process-label lint, unit
  tests, and e2e tests. `./scripts/check.sh` runs the same locally;
  `--quick` skips e2e.
- **Backups**: none exist, because nothing is deployed. Litestream is
  documented in `docs/deployment.md` and not installed anywhere.
- **Docs**: `docs/user-guide.md`, `docs/administration.md`,
  `docs/deployment.md`, `docs/development.md`. The deployment guide is
  entirely Fly and will be rewritten under `bd-mej`/`bd-n7a`. Material for
  MkDocs is named in the stack description with no `mkdocs.yml`; the docs
  are plain Markdown (`bd-m50`).
- Known drift: `administration.md` gives the OCR model default as
  `claude-sonnet-4-6`; code, `.env.example`, and `development.md` say
  `claude-sonnet-5`. `pymarc` is a declared dependency nothing imports.
  Both in `bd-m50`.
- Management commands: `load_test_data`, `fetch_covers`,
  `clean_marc_punctuation`, `clean_control_characters` (report by
  default, `--apply` to write), `cleanup_staging`.

### 2.11 Tests

On `main` on 2026-09-04: 657 unit tests (`tests/`) and 97 Playwright
end-to-end tests (`tests/e2e/`) covering auth, barcode scanning, browsing,
dark mode, ingest and the ingest mode bar, search, site chrome, and the
title-page handoff (phone and desktop as two browser contexts).
`pytest-socket` blocks live HTTP in tests.

### 2.12 Open beads at a glance

`br ready --json` is the source of truth; this table is a map.

| Bead | What | Notes |
| --- | --- | --- |
| `otzar-zwg` (P2, epic) | Series-aware ingest: claim a set from one scan, auto-fetch siblings, review in a matrix, commit | `otzar-ra1` (volume normalization) and `otzar-2t3` (SeriesClaim models) done; `cex`, `j2k`, `zx8`, `520`, `2ao`, `t07`, `pqr` open |
| `otzar-pbv` (P2, epic) | Optional record metadata: provenance, bookplates, stamps, dedications | children `epd`, `efh`, `e02` |
| `otzar-1yn` (P3) | Enrich authors and subjects from authority sources | new child `otzar-1yn.1` (P1): match existing authors on confirm |
| `bd-k0s` (P2, epic) | Search and browse quality | children: prefix matching (P2), Hebrew prefixes, nav search box, same-subject items (P3), facets (P4) |
| `bd-y1g` (P2, epic) | Connect the response cache, usage log, and reindex paths | children: cache (P2), reindex and admin indexing (P2), usage log and daily cap (P3) |
| `bd-mej`, `bd-n7a` (P2) | Remove the Fly deployment; plan AWS with backups and a tested restore | see 2.10 |
| `bd-lg9` (P2, bug) | `source_marc` never populated | fix merged 2026-09-04; the bead closes with the next tracker batch; records created before it stay null |
| `bd-73m`, `bd-nzb`, `bd-mb8`, `bd-xtx` (P2) | Review queue rows with inline confirm; queue on `/ingest/` with a count; score candidates against OCR output; failed OCR re-run discards the previous extraction | the ingest-review thread |
| `bd-yg9` (P2) | Attach the confirmed title-page image to the record | |
| `otzar-55i`, `otzar-4x2` (P2) | Author roles and statement of responsibility; volume evidence for set records | parser depth |
| `bd-jov`, `otzar-g4d` (P3) | Repair stored non-sorting delimiters; show the matched cascade step | `bd-jov`'s command merged 2026-09-04; running it against the live database is a manual step |
| `bd-4jn`, `bd-wnx`, `bd-b4a`, `bd-2lp`, `bd-eqq` (P3) | `cleanup_staging` directory; 880 for subjects and series; vendor HTMX/Alpine; queue visibility decision; multi-value manual entry form | |
| `otzar-ts6`, `otzar-rxn`, `otzar-5mr`, `otzar-eiy` (P4) | Phone landing screen for both scan types; rotate/crop before OCR; multi-page capture; stale `awaiting_ocr` janitor | handoff refinements |
| `bd-x9w`, `bd-zvy`, `bd-m50`, `otzar-2or`, `bd-1yg` (P4) | DNB cascade; per-user activity view; repository drift; gitignore generated CSS; retire planning documents | |

Threads: `xh6` (done), `ts6`/`rxn`/`5mr`/`yg9` are the device-handoff
thread; `zwg`, `mb8`, `73m` are the automation thread; `pbv`, `55i`,
`4x2` are the record-depth thread; `1yn`, `wnx`, `k0s` are the
multilingual thread; `mej`, `n7a`, `y1g` are the operations thread.

---

## 3. What holds up

Properties of the codebase worth preserving:

- **The architecture matches the scale.** Three apps with clear
  boundaries; stateless source clients; SQLite with WAL; synchronous
  request handling; no infrastructure beyond what the load requires.
- **The multilingual foundations are structural.** Original-script and
  romanized fields exist on every model where it matters; MARC parsing
  handles both the LC 880-linkage pattern and NLI's direct-Hebrew pattern
  for titles and authors; the OCR prompt encodes ALA-LC romanization and
  gematria dates; bidi rendering is applied consistently; the FTS index
  covers both script forms.
- **One record-creation path.** Every confirm goes through
  `_create_record_from_candidate`, so the ISBN path, the title-page path,
  and the queue produce identical records. This was not true in July; the
  two copies had drifted.
- **The scan-to-queue-to-confirm pipeline works end to end** for both
  barcodes and title pages, including the phone handoff, with a
  review-before-OCR step so a bad photo costs no tokens.
- **The cascade is data.** Adding a catalog or reordering queries means
  editing a list of templates.
- **Test coverage is broad**: 754 tests, e2e coverage of every
  user-facing flow, network access blocked in tests, CI gating merges. The
  rule "user-visible change requires an e2e test" is followed.
- **Stable, prefix-configurable record IDs and Unicode slugs**, which
  also make per-instance identity a configuration matter (see §6).

One claimed strength from July held only in the schema: "source MARC as
source of truth." The write path never filled the field until `bd-lg9`
landed on 2026-09-04. Records created before then have no source document
and cannot be re-derived from one.

---

## 4. Gaps

Grouped by theme. Every item names its bead.

### 4.1 Multilingual depth

- **Author identity across scripts** (`otzar-1yn.1`, P1). Confirm creates
  authors by exact name, so the same person from NLI and from LC becomes
  two rows. This is the largest data-quality gap and it compounds with
  every confirm. The local matcher already exists and is used only by
  manual entry. VIAF-based grouping follows under `otzar-1yn`.
- **Whole-word search only** (`bd-k0s.1`, `bd-k0s.2`). No prefix
  matching and no handling of Hebrew prefix particles. Both are FTS5-level
  changes.
- **Subjects and series carry no alternate-script form** (`bd-wnx`). Only
  titles and authors get 880 handling, so the subject browse shows one
  heading twice in two scripts.
- **Sorting is by code point**, not language-aware collation. Hebrew
  sorts acceptably; Latin titles with diacritics can sort oddly. No bead
  until a browse page is seen to be wrong.

### 4.2 Automation

- **External responses are not cached** (`bd-y1g.1`). Every cascade step
  re-hits NLI and LC with 3-second delays; a repeated search takes 20
  seconds or more. The cache module exists.
- **OCR cost tracking is a stub** (`bd-y1g.3`). `APIUsageLog` is never
  written and there is no scan-count limit.
- **Series automation** — the `otzar-zwg` epic. Two children have landed
  (volume normalization, the claim data model). Confirming a single scan
  still does not link the record to a Series when the MARC has 490/830
  data (`otzar-j2k`), and 245 $n/$p volume parts are dropped
  (`otzar-cex`).
- **Candidates are not ranked against the photograph** (`bd-mb8`). The
  OCR output is used to build queries and then ignored; a title-only
  fallback returns dozens of editions in catalog order.
- **DNB is ISBN-only** (`bd-x9w`, P4). A DNB cascade is a configuration
  addition when a German or Yiddish book needs it.

### 4.3 Device handoffs

- **Confirmed scans never attach the title-page image to the record**
  (`bd-yg9`). The image stays on the ScanResult in staging; the
  `TitlePageImage` model is unused. For a collection where the title page
  is the identity of the copy, this is the largest remaining gap in the
  handoff thread.
- **`cleanup_staging` sweeps the pre-handoff directory** (`bd-4jn`).
  Staged images live under `media/staging/`; the command looks in
  `tmp/title_pages/`. `otzar-eiy` (stale `awaiting_ocr` rows) folds in.
- **One QR locks the phone to one scan type** (`otzar-ts6`); rotate/crop
  before OCR (`otzar-rxn`) and multi-page capture (`otzar-5mr`) wait on
  feedback from real sessions.

### 4.4 Search and browse richness

- **No search box in the navigation** (`bd-k0s.3`); **no facets**
  (`bd-k0s.5`, P4, when result lists outgrow a screen); **no same-subject
  related items** (`bd-k0s.4`).
- **Stale index on admin edits and no reindex command** (`bd-y1g.2`).
- **Record depth**: provenance, bookplates, stamps, dedications
  (`otzar-pbv`); author roles and the statement of responsibility
  (`otzar-55i`); volume evidence from 505/020 $q/300 for set records
  (`otzar-4x2`).

### 4.5 Multi-user

- **Queue visibility for non-staff reviewers** is a decision, not a bug
  (`bd-2lp`). `bd-nzb` carries the same scoping into the mode-bar count.
- **Per-user activity view** (`bd-zvy`, P4).
- The site password is environment-only. Livable; no bead.

### 4.6 UX

- **Manual entry accepts one author, one publisher, one location, and no
  subjects** (`bd-eqq`). Everything else is admin-only.
- **Frontend libraries load from a CDN** (`bd-b4a`). On shelf wifi the
  page renders without its interactivity.
- **Review queue presentation** (`bd-73m`, `bd-nzb`): candidates hidden
  behind a Details button; the landing page duplicates the mode bar.

### 4.7 Operations

- **No deployment, no backups** (`bd-mej`, `bd-n7a`). See 2.10 and §8.
- **Repository drift** (`bd-m50`): `pymarc`, the MkDocs claim, the OCR
  model default in the administration guide.
- **Failed OCR re-run destroys a good extraction** (`bd-xtx`). A
  deliberate choice that needs reversing or defending.

---

## 5. Where to focus

A recommended order, with reasoning. The July version of this plan put
"land the handoff PR" first, then a batch of small wiring fixes, then
backups on Fly, then the series epic. The handoff landed; none of the
wiring batch was picked up, because none of it had a bead — that is
corrected above. The backup step was premised on a deployment that never
existed. What follows replaces that sequence.

### Step 1 — Fixes that compound with every record

Items in this class get worse the longer the catalog grows and cost the
same to fix now or later, so they go first. One has already landed:
`bd-lg9` (populate `source_marc`) merged on 2026-09-04, and every record
created before it has no source document, permanently — which is the
argument for doing the other two now:

- `otzar-1yn.1` — match existing authors on confirm. Every duplicate
  author row created before this lands has to be merged by hand.
- `bd-y1g.2` — reindex command and admin-write indexing. The failure is
  silent and the recovery command does not exist.

Both are one-session tasks with existing tests to extend.

### Step 2 — Stop paying for the abandoned deployment; plan the real one

`bd-mej` is mechanical and lands whenever someone has an hour: it removes a
workflow that fails on every merge and a deployment guide for a platform
that will never host the app. `bd-n7a` is the planning work for AWS and
ends in a decision and a few implementation beads. Neither blocks the
ingest work and the planning can run beside it. Backups and a rehearsed
restore are part of `bd-n7a`'s deliverable, not a separate step, because
there is nothing to back up until something is deployed.

### Step 3 — The ingest-review thread

`bd-73m` (queue rows with inline confirm), `bd-nzb` (queue on `/ingest/`
with a count), `bd-mb8` (score candidates against the OCR output), and
`bd-xtx` (keep the previous extraction on a failed re-run) are what the
last round of real cataloging asked for. They touch the same templates and
views as each other and should land as a group, with `bd-73m` first
because `bd-nzb` builds on its rows.

### Step 4 — Series-aware ingest (`otzar-zwg`)

The largest cataloging-effort reduction available: multi-volume sets
(Talmud, Mishneh Torah, encyclopedias) are common and each volume is a
full ingest today. Two children are done. Take the two that stand alone
next — `otzar-cex` (245 $n/$p in the parser and queue) and `otzar-j2k`
(persist Series/SeriesVolume on single-scan confirm) — then the claim
chain `zx8` → `520` → `2ao` → `t07` → `pqr`. Land `bd-y1g.1` (response
caching) before the fan-out so a retried claim costs nothing at NLI and
LC.

### Step 5 — Make the photograph part of the record

`bd-yg9` (attach the confirmed image as a `TitlePageImage` and show it)
and `bd-4jn` (fix `cleanup_staging`) complete what the handoff started.
`bd-yg9` should use Django's storage API so it does not care whether
`bd-n7a` puts media on local disk or S3.

### Step 6 — Search quality (`bd-k0s`)

Prefix matching first; it is one line in `_sanitize_query` plus a ranking
check, and it corrects a false statement in the user guide. Hebrew prefix
handling, the navigation search box, and same-subject related items
follow. Facets wait for result lists that need narrowing.

### Step 7 — Everything else, as interest dictates

`otzar-pbv` (record depth) is independent of everything above. `otzar-1yn`
proper (VIAF enrichment) follows step 1's local matching. `bd-wnx`,
`bd-eqq`, `bd-b4a`, `bd-2lp`, and the P4 handoff refinements are
individually small; the handoff refinements in particular should wait for
feedback from a cataloging session that uses both scan types.

### Dependency summary

```
otzar-1yn.1, bd-y1g.2 (step 1)              independent of everything; do first
bd-mej ─► bd-n7a                             independent of ingest work
bd-73m ─► bd-nzb ; bd-mb8, bd-xtx            share ingest templates; land together
otzar-cex, otzar-j2k ─► zx8 ─► 520 ─► 2ao ─► t07 ─► pqr
bd-y1g.1 (caching) ─► before the zwg fan-out
bd-yg9 ─► uses storage API so bd-n7a's media decision does not block it
otzar-1yn.1 ─► otzar-1yn (VIAF)
bd-k0s.1 ─► bd-k0s.2 (same function)
```

---

## 6. Multi-tenant considerations (optional / future — do not build yet)

The question: could one server host 5–7 independent catalogs, each with
its own user group, records, media, site password, and ID prefix? Three
options, weighed for this project's scale (each catalog: a few thousand
records, single-digit users, a few hundred MB of media).

### Option A — One app instance per catalog

Each catalog gets its own instance: own SQLite file, own media directory,
own environment (`RECORD_ID_PREFIX`, `SITE_PASSWORD`, `SECRET_KEY`), own
hostname, sharing one container image and codebase.

- **Code changes required: none.** The app is configured by environment
  variables, media lives under `DATA_DIR`, and the ID prefix is
  per-instance.
- Isolation is total: no query can leak another catalog's data; a bad
  migration or restore affects one group.
- Backups stay simple: one database stream and one media bucket or
  snapshot per catalog.
- Operational overhead: several deploy targets, mitigated by one shared
  image and a loop in the deploy step; several sets of secrets to manage
  once. On a single VM this is several containers on different ports
  behind one reverse proxy.

### Option B — One Django process, one SQLite file per catalog

A single server maps hostname to database alias. Each catalog keeps its own
SQLite file and media subdirectory.

- Code changes: tenant-resolution middleware; a database router;
  migrations against every alias; per-tenant media path prefixes; moving
  `RECORD_ID_PREFIX` and `SITE_PASSWORD` from env vars to per-tenant
  configuration; making the FTS helper and file cache tenant-aware.
  Auth and session tables would live per database, which gives per-catalog
  user separation but complicates any shared admin.
- Saves one process per catalog while adding a routing layer every future
  feature must respect. At this scale the complexity buys almost nothing.

### Option C — One shared database with a catalog foreign key everywhere

Every table gains a `catalog` FK; every query, the FTS index, media paths,
ID generation, and permissions get scoped per tenant.

- The most invasive change and the riskiest: one missed
  `.filter(catalog=…)` is a cross-tenant data leak. Right for hundreds of
  tenants; over-engineering for 5–7.

### Recommendation

**Option A, when the need materializes; it requires no code today.** The
discipline worth keeping now costs nothing:

- Keep all per-community values (prefix, password, endpoints, model
  choice) in environment variables; do not let future features bake in
  singletons or absolute paths outside `DATA_DIR`.
- Keep media paths relative to `MEDIA_ROOT`, and reach storage through
  Django's storage API rather than the filesystem.
- Revisit Option B only if hosting cost for several instances matters.
  Option C is out of scope for this project's lifetime unless the scale
  assumptions change.

One open design question if multi-tenant happens: whether users are
per-catalog (what Option A gives) or shared across catalogs (needs Option
B/C machinery). For a circle of friends, per-catalog accounts are almost
certainly fine.

---

## 7. Open questions

Questions the July version listed that are now answered: the OCR model
default is `claude-sonnet-5` in code and configuration (the administration
guide lags; `bd-m50`); the deployment target is AWS (`bd-mej`, `bd-n7a`);
backup posture is part of `bd-n7a`; search prefix and Hebrew-particle
handling are scheduled (`bd-k0s`); DNB in the cascade is a P4 bead
(`bd-x9w`); docs tooling is in `bd-m50`.

Still open:

1. **Review queue scoping** (`bd-2lp`). Should every cataloger see the
   shared pending queue, or is "reviewer = staff" the intended model? The
   bead records the two options; it needs a decision before `bd-nzb`
   settles the mode-bar count.
2. **Which handoff refinements are wanted** (`otzar-ts6`, `otzar-rxn`,
   `otzar-5mr`). Decide after a cataloging session that uses both scan
   types from a phone.
3. **Per-catalog or shared accounts**, if and when §6 happens.

---

## 8. Deployment direction

The July version of this document carried an appendix comparing Fly.io
with AWS in detail. Fly is abandoned and AWS is the target, so the
comparison is moot. `bd-mej` removes the Fly footprint and `bd-n7a` holds
the AWS planning — the SQLite constraint (one writer, local disk, one
machine), the compute options to cost, Litestream to S3 for continuous
backup, and a restore that has been executed and verified. Read that bead
for the current state of the decision; do not duplicate it here.

Notes from the July analysis that `bd-n7a` does not restate and that
should inform it:

- **Sizing.** Browsing and searching are trivial load. Ingest is
  dominated by waiting on Claude and on rate-limited SRU endpoints; the one
  local resource that matters is memory for image handling. A small
  ARM/Graviton instance with 1–2 GB of RAM covers sustained ingest. No
  autoscaling, no second instance.
- **TLS.** Caddy on the instance gives automatic Let's Encrypt
  certificates with a two-line config. An Application Load Balancer adds
  roughly $16/month of fixed cost for nothing this app needs.
- **Deploy pipeline.** Keep the current model: build the image (for ARM),
  push to a registry (GitHub Container Registry keeps it simplest), then
  restart the container on the instance over SSH from GitHub Actions.
  Migrations run in the entrypoint, so deploys stay non-destructive.
- **Cost levers.** The instance is most of the bill; a 1-GB ARM instance
  is the starting point. Skip the load balancer, the NAT gateway
  (~$32/month, not needed with a public IP), and RDS. An always-on
  instance is the price of the single-writer SQLite design; there is no
  clean scale-to-zero, and it is not worth engineering one for a few
  dollars.
- **Media.** Reaching storage through Django's storage API keeps the
  local-disk versus S3 choice out of application code; `bd-yg9` is the
  first feature that depends on this.
- **Restore drill.** Whatever the layers, perform a restore once onto a
  throwaway instance and verify record count, a spot-checked record, and
  a search returning hits. That is `bd-n7a`'s acceptance criterion and it
  matters more than which compute option wins.
