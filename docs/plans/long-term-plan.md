# otzar — Long-term plan

This document reviews where otzar stands as of July 2026 and lays out a
forward plan. It is written to be readable by any person or agent picking up
the project later, without assuming deep familiarity with the code. Earlier
planning documents (`app-plan.md`, `implementation-plan.md`,
`extract-from-experiments.md`) describe the original design; this document
describes what actually got built, what didn't, and what to do next.

---

## 1. Purpose and vision

otzar is a catalog for a small circle of friends cataloging a shared
collection of books. The collection is heavy in right-to-left scripts —
Hebrew, Aramaic, Yiddish — alongside English, and records often carry both
original-script and romanized (Latin-letter) forms of titles and names.

What "good" looks like:

- **Easy and fun to use.** Cataloging a book should feel quick and
  satisfying, not like data entry.
- **Smart about being multilingual.** Hebrew and romanized forms are both
  first-class: stored, displayed, and searchable. Right-to-left text renders
  correctly next to left-to-right text.
- **Automates everything reasonable.** Barcode scans and title-page photos
  should pull full bibliographic records from national libraries so people
  type as little as possible.
- **Thoughtful device handoffs.** A phone is the camera; a laptop is the
  review desk. Moving work between them should take one tap, not a login and
  a URL.
- **Uses the full depth of bibliographic records.** MARC records carry
  authors, subjects, series, places, dates, identifiers — all of it should
  feed search, browse, and "related items" features with a clear interface.
- **Multiple users of one catalog.** A few people cataloging together;
  anyone can browse and search.
- **Possibly multi-tenant later.** Several independent catalog+user groups
  on one server. Optional, future.

**Scale constraint (do not over-build):** each catalog holds at most a few
thousand items, and a server might someday host 5–7 such catalogs. SQLite,
one small VM, and simple synchronous code are appropriate at this scale.
There is no future where this needs PostgreSQL clusters, background job
queues, or a dedicated search server unless something is actually broken
without them.

---

## 2. Current state

An honest inventory of what exists and works today, grounded in the code.

### 2.1 The three Django apps

- **`catalog`** — the data models, full-text search, browse views, record
  detail pages, and the home page. This is where everything is stored and
  displayed.
- **`sources`** — clients for external bibliographic services: SRU catalog
  search (NLI, LC, DNB), VIAF authority lookup, MARC parsing, a search
  "cascade" engine, Open Library cover lookup, and a response-cache wrapper.
  It has no database models of its own (`sources/models.py` is empty);
  everything it retrieves is either handed to the caller or stored via
  `catalog` models. The Django file cache (at `DATA_DIR/cache`) is its only
  persistence.
- **`ingest`** — the data-entry workflows: manual entry, ISBN/barcode
  scanning, title-page OCR, the review queue, QR phone handoff, authority
  checking, and series volume management. Its models are `ScanResult`
  (a pending scan awaiting review) and `APIUsageLog` (intended for cost
  tracking; see 2.9).

### 2.2 Data model (`catalog/models.py`, `ingest/models.py`)

- **Record** — the central model. Title plus romanized title, subtitle,
  publication date (integer year for sorting plus a freeform display string
  for "ca. 1850"-style dates), place, language, notes, cover image URL, and
  the original MARC record stored as JSON (`source_marc`) with its source
  catalog (NLI, LC, or DNB). Each record gets a public ID like `otzar-3f8a`
  — a configurable prefix (env var `RECORD_ID_PREFIX`) plus a base62
  encoding of the database row number (`catalog/id_generation.py`) — and a
  Unicode slug for readable URLs (`/catalog/otzar-3f8a/mishneh-torah/`,
  Hebrew slugs supported). Many-to-many links to Author, Subject, Publisher,
  and Location.
- **Author** — name, romanized name, VIAF ID, and a JSON list of variant
  name forms.
- **Subject** — heading, romanized heading, source (LC/NLI/local).
- **Publisher** — name, romanized name, place.
- **Series / SeriesVolume** — a series with optional total volume count;
  SeriesVolume links a series to a record with a string volume number and a
  `held` flag, so gaps ("we own 4 of 10") are representable.
- **Location** — a freeform shelf label ("Floor 1, Room B, Shelf 4a").
- **ExternalIdentifier** — ISBN, LCCN, LC classification, Dewey, NLI control
  number, VIAF ID, OCLC number, with a uniqueness constraint per record.
- **TitlePageImage** — exists and is registered in the admin, but no ingest
  flow populates it today (see 2.4 and 4.3).
- **ScanResult** (ingest) — a scan awaiting review: type (ISBN or OCR),
  status (pending/confirmed/discarded), the ISBN or image, raw OCR output,
  candidate records as JSON, the selected candidate, the created record, and
  who scanned it.

### 2.3 Ingest paths

All require login. Landing page at `/ingest/`.

- **Manual entry** (`/ingest/new/`) — a form for title, romanized title,
  subtitle, dates, place, language (with an autosuggest backed by the
  pycountry language list), notes, plus one author, one publisher, and one
  location. The same form edits existing records (`/ingest/edit/<id>/`).
- **ISBN/barcode scan** (`/ingest/scan/`) — browser-based barcode reading
  from the camera; the ISBN is looked up in NLI (`alma.isbn`), LC
  (`bath.isbn`), and DNB (`dnb.num`) simultaneously. Candidates are shown
  with expandable detail; selecting one pre-fills a confirmation page that
  creates the Record with authors, subjects, identifiers, and classification
  numbers extracted from the MARC, plus a best-effort Open Library cover
  lookup. Every lookup also creates a ScanResult so it appears in the review
  queue.
- **Title-page OCR** (`/ingest/scan-title/`) — upload or photograph a title
  page; the image goes to Claude Vision (`ingest/ocr.py`) with a detailed
  prompt covering ALA-LC Hebrew romanization, gematria date conversion, and
  no-nikkud rules. The extracted metadata comes back as editable fields;
  "Search catalogs" then runs the cascade search (see 2.5) and shows
  candidates. On main, the uploaded image is saved to `tmp/title_pages/` for
  debugging only — it is not attached to the record.
- **Review queue** (`/ingest/queue/`) — pending scans with their candidates;
  confirm creates the record, discard marks the scan discarded. Users see
  their own scans; staff see everyone's. `cleanup_staging` (management
  command) deletes discarded scans and stale staging images after 30 days.
- **QR phone handoff** — `/ingest/qr/` renders a QR code containing a signed
  token (1-hour expiry, Django's `TimestampSigner`). Scanning it on a phone
  logs the phone browser in as the same user and puts it in "phone scanner"
  mode: scans get a brief confirmation and land in the queue, while the
  desktop polls (`/ingest/scan/poll/`) and shows arriving scans live. This
  works today for the barcode path.
- **Authority check** (`/ingest/authority-check/`) — an HTMX endpoint used
  during manual entry that checks a typed author name against existing
  Authors by exact name, exact romanized name, or normalized variant-name
  match (`ingest/authority.py`), so the cataloger can reuse an existing
  author instead of creating a duplicate.
- **Series management** (`/ingest/series/<id>/`) — add volumes to a series
  from a spec like "1-13", "all 8", or "1, 3, 5"; gaps in the numeric range
  are detected and shown.

### 2.4 The in-flight work: phone-to-desktop title-page handoff (PR #7)

Bead `otzar-xh6`, branch `bd-xh6-phone-title-page-handoff`, GitHub PR #7 —
open, deliberately paused pending this plan. It extends the QR handoff to
the title-page path: the QR token now carries a target (`isbn` or `title`),
the phone gets a streamlined capture screen, uploaded images are stored on
`ScanResult.image` (a new `awaiting_ocr` status) instead of the untracked
tmp directory, and either device can review the photo and trigger OCR or
discard it *before* API tokens are spent. The PR includes unit tests, a
five-test Playwright suite simulating phone and desktop as two browser
contexts, and a migration. Two manual smoke-test items in the PR checklist
are unchecked (real phone test; verifying disk cleanup on discard).

### 2.5 External sources (`sources/`)

- **SRU client** (`sru.py`) — a small configurable client using httpx with a
  polite delay between requests (default 3 seconds, `SRU_REQUEST_DELAY`),
  30-second timeout, and structured success/error results. Pre-configured
  instances for NLI (SRU 1.2, with automatic quoting of `alma.*` values), LC
  (SRU 1.1), DNB, and VIAF; endpoints overridable by env vars.
- **Cascade engine** (`cascade.py`) — data-driven lists of progressively
  broader CQL queries. NLI has 7 steps (title+place+date down to title
  alone); LC has 4 (romanized title+date down to a multi-word Hebrew keyword
  AND query). The engine stops at the first step returning records. Used by
  the title-page OCR flow. DNB is queried for ISBN lookup only — there is no
  DNB cascade.
- **MARC parsing** (`marc.py`) — extracts records from SRU envelopes with
  the `mrrc` library and parses title, author, publication, date, language,
  ISBN, LCCN, OCLC, classifications, additional authors (700), subjects
  (650), and series (490/830). Handles both LC's pattern (Hebrew in linked
  880 fields) and NLI's (Hebrew directly in primary fields). Can serialize a
  record to MARCJSON for storage.
- **VIAF client** (`viaf.py`) — full search-cascade client that parses VIAF
  clusters (IDs, headings, variants, source IDs like NLI's J9U and LC's
  LCCN) and scores the best match. **Built and unit-tested, but not called
  from any ingest or catalog flow** — authority checking today uses only
  local Author data.
- **Covers** (`covers.py`) — Open Library cover lookup by ISBN/OCLC/LCCN,
  called at record-confirm time and available as a backfill management
  command (`fetch_covers`).
- **Response cache** (`cache.py`) — a wrapper over Django's file cache with
  a 30-day TTL, keyed on URL+parameters. **Built and unit-tested, but not
  wired into the SRU or VIAF clients** — every external query today goes to
  the network. (Rate-limit delays are respected, so this is a latency and
  courtesy issue, not a correctness one.)

### 2.6 Search (`catalog/search.py`, `catalog/search_views.py`)

SQLite FTS5 (a built-in full-text index) in a virtual table covering title,
romanized title, subtitle, authors, subjects, publishers, place, notes, and
external identifiers. Related-model text is denormalized (copied) into the
index when a record is indexed. Indexing happens explicitly in the ingest
views when records are created or edited — **not** via signals, so records
edited or deleted through the Django admin silently go stale in the index,
and there is no standalone reindex management command (`reindex_all()`
exists in code and is invoked only by `load_test_data`).

Query behavior: the query is split into words, each quoted, and all words
must match as whole tokens. So searching "Rambam" finds records containing
the word "Rambam" in any indexed field; searching "Ramb" finds nothing, and
Hebrew words with attached prefix particles (-ב, -ה, -ל) do not match their
base form. Results are ranked by FTS5's built-in relevance ranking. This
matches the documented plan ("basic token matching should be adequate at
this scale") and the known limitation is stated in the user guide.

The search page is at `/search/`; the site navigation has a *link* to it,
not an embedded search box (the original plan called for a search bar in the
navigation).

### 2.7 Browse (`catalog/browse_views.py`)

Nine paginated browse views: authors (with record counts), titles
(Hebrew-script titles grouped first, then Latin), subjects, publishers,
dates (grouped by decade), locations, series (with held/gap counts), places
(normalized from MARC punctuation), and detail pages for authors, subjects,
and places. The record detail page shows all fields with proper
right-to-left handling, links to browse pages, other works by the same
author, sibling series volumes with gap indicators, external identifiers, a
cover image, and the full source MARC in the tagged format librarians
expect. Staff can edit or delete records from the detail page (delete does
remove the record from the search index).

### 2.8 Multilingual and accessibility

- A `bidi` template-tag library wraps text in `dir="rtl"`/`dir="ltr"`/
  `dir="auto"` spans based on Hebrew character detection; it is used across
  browse, search, detail, and ingest templates. Form inputs for title,
  subtitle, and place use `dir="auto"`.
- Dark mode with a toggle (Alpine.js + localStorage, defaulting to system
  preference); skip-to-content link; visible focus rings; 44px touch
  targets in navigation; e2e tests cover dark mode and browsing.
- The interface language is English (per plan). HTMX and Alpine.js load
  from the unpkg CDN, so the app needs internet access to render
  interactivity.

### 2.9 Auth and multi-user

- Django's built-in auth. Browse and search are public; all ingest views
  require login; record edit/delete require login (delete requires staff).
  Accounts are created through the Django admin.
- **Site password** (`otzar/middleware.py`, `SitePasswordMiddleware`): if
  the `SITE_PASSWORD` env var is set, anonymous visitors see a minimal
  password page before reaching any public page; entering it sets a session
  flag. Logged-in users and the admin/login/health paths bypass it. It is
  configured by environment variable only — the app-plan's idea of setting
  it from the admin is not implemented.
- Records track `created_by`; scans track `scanned_by`. The review queue is
  scoped per-user unless the viewer is staff — which means the "several
  people scan, one person reviews" group workflow only works if the reviewer
  is staff.
- `APIUsageLog` (for OCR cost monitoring) has a model and an admin page,
  but **no code writes to it** — OCR calls are not logged.

### 2.10 Deployment, operations, CI

- **Fly.io**: `fly.toml` (iad region, shared-cpu-1x/512MB, auto-stop with
  one machine minimum), `Dockerfile`, `entrypoint.sh` running migrations
  before gunicorn, persistent volume at `/data` for SQLite + media + cache.
  SQLite runs in WAL mode with a 5-second busy timeout, which is the right
  setup for a few concurrent writers.
- **CI/CD**: GitHub Actions `ci.yml` and `deploy.yml` (test, lint, format
  check, then deploy on main).
- **Backups**: Fly's daily volume snapshots work by default. Litestream
  (continuous SQLite backup to S3) is documented in `docs/deployment.md`
  but **not installed in the Dockerfile or entrypoint** — it is a documented
  future setup step, not a running system.
- **Docs**: `docs/user-guide.md`, `docs/administration.md`,
  `docs/deployment.md`, `docs/development.md` are current and substantial.
  Material for MkDocs is named in the stack but there is no `mkdocs.yml`;
  the docs are plain Markdown files.
- Known doc/code drift: `administration.md` says the OCR model defaults to
  `claude-sonnet-4-6`; the code default (`ingest/ocr.py`) and `.env.example`
  are `claude-haiku-4-5-20251001` (Haiku is ~7x cheaper; Sonnet was more
  accurate on decorative Hebrew fonts in testing per `.env.example`).
- `pymarc` is in `pyproject.toml` dependencies but nothing imports it; the
  MARC library actually used is `mrrc`.

### 2.11 Tests

On main: 321 unit tests (`tests/`) covering models, search, SRU/MARC/VIAF
parsing, cascade, ISBN, OCR parsing, authority matching, review queue,
browse, bidi, covers, and caching; 56 Playwright end-to-end tests
(`tests/e2e/`) covering auth, barcode scanning, browsing, dark mode, ingest,
and search. `pytest-socket` blocks accidental live HTTP in tests. PR #7 adds
roughly 30 more unit tests and a 5-test handoff e2e suite.

### 2.12 Open beads (issue tracker) at a glance

| Bead | What | Status |
| --- | --- | --- |
| `otzar-xh6` (P2, epic) | Phone-to-desktop title-page handoff | **In flight — PR #7 open** |
| `otzar-zwg` (P2, epic) | Series-aware ingest: claim a whole set from one scan, auto-fetch sibling volumes, review in a live matrix, commit. 9 child tasks already broken out (volume-number normalization incl. gematria/Roman numerals, SeriesClaim data model, per-row HTMX lookups, commit endpoint, e2e test) | Open, not started |
| `otzar-pbv` (P2, epic) | Optional record metadata: provenance notes, bookplates, stamps, dedications — consistent text+image capture, storage, search, and display. 3 child tasks | Open, not started |
| `otzar-1yn` (P3, feature) | Enrich authors/subjects from authority sources (VIAF, LC id.loc.gov, Wikidata, NLI J9U); exploratory | Open |
| `otzar-9h9` (P3) | GitHub link + build state in site chrome | Open |
| P4 backlog | Phone landing screen offering both scan types (`ts6`); in-browser rotate/crop before OCR (`rxn`); janitor for stale awaiting-OCR rows (`eiy`); multi-page title+verso OCR (`5mr`); gitignore generated tailwind.css (`2or`) | Open |

These map well onto the vision: `xh6`/`ts6`/`rxn`/`5mr` are the
machine-handoff thread, `zwg` is the automation thread, `pbv` is the
record-depth thread, and `1yn` is the multilingual/authority thread.

---

## 3. What's good

Strengths worth preserving and building on:

- **The architecture matches the plan and the scale.** Three apps with
  clean boundaries; stateless source clients; SQLite with WAL; synchronous
  request handling; no premature infrastructure. The original build order
  was followed and it shows — layers compose rather than tangle.
- **The multilingual foundations are real, not cosmetic.** Original-script
  and romanized fields exist on every model where it matters; MARC parsing
  handles both the LC 880-linkage pattern and NLI's direct-Hebrew pattern;
  the OCR prompt encodes ALA-LC romanization and gematria dates; bidi
  rendering is applied consistently in templates; the FTS index covers both
  script forms so Hebrew and romanized searches find the same record.
- **Source MARC as source of truth.** Every fetched record keeps its
  original MARC as JSON, viewable in tagged form on the detail page. Local
  fields can diverge for correction, but nothing is lost. This is the right
  librarian instinct and enables future re-extraction (e.g. fields not yet
  parsed).
- **The scan-to-queue-to-confirm pipeline works end to end**, including the
  QR phone handoff for barcodes — the vision's signature workflow. PR #7
  completes the same loop for title pages.
- **The cascade design is data, not code.** Adding a catalog or tuning
  query order means editing a list of templates, not writing new logic.
- **Test discipline is high** for a hobby-scale project: ~380 tests, e2e
  coverage of every user-facing flow, network access blocked in tests, CI
  gating deploys. The CLAUDE.md rule "user-visible change ⇒ e2e test" is
  actually being followed.
- **Docs are honest.** The user guide states the Hebrew-morphology search
  limitation plainly instead of hiding it. Keep that tone.
- **Stable, prefix-configurable record IDs and Unicode slugs** — small
  thing, done right, and it quietly prepares for multi-tenancy.

---

## 4. What's not there yet

Gaps between the vision and today, grouped by theme. Where a bead exists it
is named; gaps with **no bead** are flagged.

### 4.1 Multilingual depth

- **Author identity across scripts.** The confirm paths
  (`confirm_scan`, `confirm_candidate`) create authors with
  `get_or_create(name=...)` — so "שניאור זלמן מלאדי" from NLI and
  "Shneur Zalman, of Lyady" from LC become two Author rows for the same
  person. The authority-check prompt exists only in manual entry, and the
  VIAF client that could group variants automatically is not wired in.
  This is the single biggest data-quality gap; it degrades author browse
  ("variant name forms grouped" is a vision item) and compounds over time.
  Partially covered by bead `otzar-1yn`; the cheap first step (run the
  existing local `find_author_matches` during scan confirm) has **no bead**.
- **Search matches whole words only.** No prefix matching (typing "Maimo"
  finds nothing) and no handling of Hebrew prefix particles (a search for
  ספר won't match הספר). FTS5 supports `word*` prefix queries almost for
  free; stripping common Hebrew prefixes at index/query time is a bounded,
  well-understood improvement. Acceptable today per plan, but this is where
  "smart about multilingual" will be felt most. **No bead.**
- **Sorting is by Unicode code point,** not language-aware collation.
  Hebrew mostly sorts correctly by accident of the alphabet's code-point
  order; Latin titles with diacritics can sort oddly. Fine at current size;
  revisit only if browse pages look wrong. **No bead.**
- Subjects and series have romanized fields but nothing populates them from
  MARC 880 links yet (only titles and authors get alternate-script
  handling). **No bead.**

### 4.2 Automation

- **External responses are not cached** despite a finished cache module —
  every cascade step re-hits NLI/LC with 3-second delays, so a repeated
  search can take 20+ seconds. Wiring `ResponseCache` into `SRUClient` is
  probably a one-day task with existing tests. **No bead.**
- **OCR cost tracking is a stub.** `APIUsageLog` is never written; the
  admin page shows nothing; there is no scan-count safety limit. **No
  bead.**
- **Series automation** — the whole `otzar-zwg` epic: claim a set from one
  scan, auto-fetch siblings, review in a matrix. Today each volume is a
  separate full ingest, and confirming a scan doesn't even link the record
  to a Series when the MARC has 490/830 series data (child bead
  `otzar-j2k` covers this).
- The OCR cascade searches NLI and LC only; DNB participates only in ISBN
  lookup. If German/Yiddish material matters, a DNB cascade is a
  configuration-only addition. **No bead.**

### 4.3 Machine-to-machine handoffs

- **Title-page handoff is in PR #7, unmerged.** Until it merges, phone
  title-page scanning dumps images into an untracked tmp directory with no
  review-before-OCR step.
- **Confirmed scans never attach the title-page image to the record.** The
  `TitlePageImage` model and the app-plan's image lifecycle
  (staging → permanent `media/title-pages/YYYY/MM/DD/{record-id}.jpg`,
  visible when browsing) are unimplemented; after PR #7 the image lives on
  the ScanResult but still doesn't become a permanent record asset. For a
  collection of old books where the title page *is* the identity of the
  item, this is a real loss. **No bead.**
- One QR currently locks the phone to one scan type; the combined phone
  landing screen is bead `otzar-ts6` (P4). Rotate/crop before OCR is
  `otzar-rxn`; multi-page capture is `otzar-5mr`.
- After PR #7 merges, `cleanup_staging` still points at the old
  `tmp/title_pages/` location and won't clean `media/staging/`; stale
  `awaiting_ocr` rows are bead `otzar-eiy`. The command needs updating.
  **No bead for the command update itself.**

### 4.4 Search & browse richness

- **No facets or filters** — search results can't be narrowed by language,
  date range, location, or author. The plan called this "progressive
  enhancement"; nothing exists yet. **No bead.**
- **No search box in the site navigation** (link only). **No bead.**
- **Related-items depth**: record detail shows same-author works and series
  siblings, but not same-subject items, commentary chains, or
  "shelved nearby" items (all vision items; shelf proximity has no data
  model support yet beyond exact location match). **No bead.**
- **Stale index risk**: admin edits bypass FTS indexing, and there is no
  `reindex` management command for recovery. Small fix, real operational
  footgun. **No bead.**
- Optional record depth (provenance, bookplates, stamps, dedications) is
  epic `otzar-pbv` — this is also a browse/search richness item since those
  texts should be indexed.

### 4.5 Multi-user

- Group workflow requires the reviewer to be staff (queue scoping is
  per-user otherwise). Whether all catalogers should see the shared queue
  is a product decision — see open questions. **No bead.**
- Site password can't be managed from the admin (env var + restart only).
  Livable; note only. **No bead.**
- No per-user activity view ("what did I catalog this session?") — a small
  fun/usability win for work sessions. **No bead.**

### 4.6 UX polish

- Manual entry supports exactly one author, one publisher, one location per
  record through the form (more via admin only), and subjects can't be
  edited outside the admin at all. **No bead.**
- Frontend libraries load from a CDN; on flaky wifi (a real condition while
  cataloging at shelves) HTMX/Alpine may fail to load. Vendoring them is
  trivial. **No bead.**
- Build-state chrome is bead `otzar-9h9`.

### 4.7 Operations

- **Litestream is documented but not installed** — the only real backup
  today is Fly's daily snapshot (5-day default retention unless raised in
  `fly.toml`). For a database receiving hand-entered cataloging labor,
  losing up to a day is painful. Either install Litestream as documented or
  consciously accept snapshot-only and say so in the docs. **No bead.**
- Restore procedure is documented but marked untested. **No bead.**
- Doc drift: OCR model default (administration.md vs code), and the MkDocs
  claim with no mkdocs.yml. Unused `pymarc` dependency. **No bead.**

---

## 5. Where to focus

A recommended sequence, with reasoning. The guiding principle: ship the
in-flight work, then fix the small things that silently undermine quality
(author duplication, stale index, no caching, no backups), then take the
big swings (series automation, authority enrichment) that each make
cataloging dramatically less repetitive.

### Step 1 — Land PR #7 (title-page handoff). Recommendation: finish it, don't rework it.

The PR is complete against its epic, well-tested (unit + e2e), and directly
serves the vision's signature workflow. Nothing found in this review argues
for redesign. Two things before merge:

1. Do the two unchecked manual smoke tests (real phone through the QR loop;
   verify discard removes the image file from disk).
2. Note the follow-ups it creates rather than expanding the PR:
   `cleanup_staging` must learn the new `media/staging/` location
   (currently it only cleans `tmp/title_pages/`), and bead `otzar-eiy`
   (prune stale `awaiting_ocr` rows) becomes relevant.

Letting it sit costs more than merging it: the branch touches
`ingest/views.py`, templates, and `ScanResult` — exactly where the series
epic (`otzar-zwg`) will also work, so merge-conflict risk grows with every
week of delay. Merge first, sequence `zwg` after.

### Step 2 — A small "close the loops" batch (1–2 sessions, all cheap, high leverage)

These are small tasks that fix things already 90% built. File beads for
each; none needs design work:

- **Attach the confirmed scan's image to the record** as a `TitlePageImage`
  (move from staging to `media/title-pages/.../{record-id}.jpg` on confirm,
  per the app-plan lifecycle) and show it on the record detail page. This
  makes PR #7's photos permanent catalog assets instead of throwaways.
- **Wire `ResponseCache` into `SRUClient`** (and VIAF). Cuts repeat-search
  latency from ~20s to instant and is kinder to NLI/LC.
- **Run the local authority check on scan confirm** — before
  `get_or_create(name=...)`, call the existing `find_author_matches` and
  surface a "same as existing author?" choice in the confirm UI. This stops
  the duplicate-author bleeding cheaply, ahead of full VIAF enrichment.
- **Log OCR calls to `APIUsageLog`** (tokens are on the API response
  already) so the admin cost page means something.
- **Add a `reindex` management command** and index-on-save for admin edits
  (or at minimum document that admin edits require reindexing).
- **Housekeeping**: fix the `administration.md` OCR-model default; update
  `cleanup_staging` for the new staging location; remove `pymarc` if truly
  unused; vendor HTMX/Alpine; decide on MkDocs (set it up or drop the claim
  from AGENTS.md/CLAUDE.md).

### Step 3 — Backups you can trust (half a session)

Install Litestream in the Docker image per the existing documentation, or
explicitly decide snapshots-only and raise `snapshot_retention` in
`fly.toml`. Then actually run the restore procedure once and mark it
tested. This is boring and should come before feature work because every
later feature increases what a data loss would cost. **No bead yet — file
one.**

### Step 4 — Series-aware ingest (`otzar-zwg`)

The biggest cataloging-effort win available. Collections like this one are
full of multi-volume sets (Talmud, Mishneh Torah, encyclopedias); today
each volume is a full ingest cycle. The epic is already well-specified with
nine child beads, honest caveats (best-effort matching, gematria/Roman
volume numbers, browser-driven fan-out instead of background workers — the
right call at this scale). Start with the two children that stand alone and
pay off immediately even if the matrix work slips:

- `otzar-cex` — surface 245$n/$p volume metadata in the parser and queue.
- `otzar-j2k` — persist Series/SeriesVolume on single-scan confirm (today
  MARC series data is parsed and then dropped).

Then the claim-flow chain (`ra1` → `zx8` → `2t3` → `520` → `2ao` → `t07` →
`pqr`).

### Step 5 — Authority enrichment (`otzar-1yn`, promote from P3)

With step 2's local matching in place, wire `viaf_enrich` into the ingest
flow: on confirming a record with a new author, query VIAF (cached, rate
limited), store the VIAF ID and variant names, and use variants to group
author forms across scripts in browse. This is the "smart about
multilingual" vision item with the most compounding value — every enriched
author improves future matching. Subject enrichment (LC id.loc.gov
broader/narrower terms) can follow later; it's an exploration, not a
commitment.

### Step 6 — Record depth and search/browse richness

- Epic `otzar-pbv` (provenance, bookplates, stamps, dedications) — makes
  the catalog say things only *this* copy of a book can say. Independent of
  everything above; can interleave whenever it's the fun thing to build.
- Search improvements, in effort order: search box in the nav header;
  FTS5 prefix matching (`word*`); optional Hebrew prefix-particle handling;
  then facets (language, decade, location) once there's enough data that
  narrowing matters. File beads as each is picked up.
- Related-items depth on record detail: same-subject items is a simple
  query away; "shelved nearby" needs a sortable shelf ordering and should
  wait until locations are used consistently in practice.

### Step 7 — The P4 handoff refinements

`ts6` (one QR, both scan types on a phone landing screen) is the best of
these and a natural follow-on once both handoff flows are merged and used
in a real cataloging session; feedback from that session should decide
whether `rxn` (rotate/crop) and `5mr` (multi-page) are worth building.

### Dependency summary

```
PR #7 merge ─► cleanup_staging update, otzar-eiy, otzar-ts6
            ─► image-to-record attachment (step 2)
            ─► otzar-zwg (shares files; sequence after merge)
step 2 local authority check ─► step 5 VIAF enrichment
step 2 response caching ─► makes zwg's per-volume fan-out gentler on NLI/LC
steps 3, 6 (pbv), and doc fixes: independent, schedule freely
```

---

## 6. Multi-tenant considerations (optional / future — do not build yet)

The question: could one server host 5–7 independent catalogs, each with its
own user group, records, media, site password, and ID prefix? Three honest
options, weighed for *this* project's scale (each catalog: a few thousand
records, single-digit users, a few hundred MB of media).

### Option A — One app instance per catalog (separate Fly apps)

Each catalog gets its own Fly.io app: own volume, own SQLite file, own
secrets (`RECORD_ID_PREFIX`, `SITE_PASSWORD`, `SECRET_KEY`), own
`<name>.fly.dev` URL, sharing the same Docker image and codebase.

- **Code changes required: none.** The app is already fully configured by
  environment variables, media lives under `DATA_DIR`, and the ID prefix is
  per-instance. This works today.
- Isolation is total — no possibility of one catalog's query leaking
  another's data; a bad migration or restore affects one group only.
- Backups stay simple: one volume snapshot / one Litestream stream per
  catalog.
- Cost: ~$3–4/month per catalog (~$25/month for 7). Auto-stop keeps idle
  catalogs near-free in CPU terms.
- Operational overhead: 7 deploy targets — mitigated by one shared image
  and a loop in the deploy workflow; 7 sets of secrets to manage once.

### Option B — One Django process, one SQLite file per catalog

A single server maps hostname → database alias (Django supports multiple
databases). Each catalog keeps its own SQLite file and media subdirectory.

- Code changes: a tenant-resolution middleware; a database router; running
  migrations against every alias; per-tenant media path prefixes; moving
  `RECORD_ID_PREFIX` and `SITE_PASSWORD` from env vars to per-tenant
  configuration; making the FTS helper and file cache tenant-aware; the
  auth/session tables live per-database (which actually gives the desired
  per-catalog user separation, but complicates any shared admin).
- Saves perhaps $20/month versus Option A while adding a permanent layer of
  routing logic that every future feature must respect. At this scale the
  complexity buys almost nothing.

### Option C — One shared database with a catalog foreign key everywhere

Every table gains a `catalog` FK; every query, the FTS index, media paths,
ID generation, and permissions get scoped per tenant.

- The most invasive change, and the riskiest: one missed `.filter(catalog=…)`
  is a cross-tenant data leak. This is the right design for hundreds of
  tenants; it is over-engineering for 5–7 and contradicts the project's
  scale principle.

### Recommendation

**Option A, when the need actually materializes — and it requires no code
today.** The current single-catalog design is already multi-tenant-ready in
the way that matters (all instance identity is configuration, not code).
The only preparatory discipline worth keeping now, essentially free:

- Keep all per-community values (prefix, password, endpoints, model choice)
  in environment variables — already true; don't let future features bake
  in singletons or absolute paths outside `DATA_DIR`.
- Keep media paths relative to `MEDIA_ROOT` — already true.
- If shared hosting cost ever genuinely matters, revisit Option B then; do
  not build it speculatively. Option C should be considered out of scope
  for this project's lifetime unless the scale assumptions change.

One open design question if/when multi-tenant happens: whether users are
per-catalog (a person in two groups has two accounts — what Option A gives
naturally) or shared across catalogs (needs Option B/C machinery). For a
circle of friends, per-catalog accounts are almost certainly fine.

---

## 7. Open questions for the owner

Recorded here so revisions of this plan can resolve them:

1. **Review queue scoping.** The vision describes several people scanning
   while one reviews, but non-staff reviewers see only their own scans
   today. Should all catalogers see the shared pending queue (simplest:
   drop the per-user filter), or is "reviewer = staff" the intended model?
2. **Search expectations.** Is whole-word matching acceptable for the
   foreseeable future, or should prefix matching (`Maimo…`) and Hebrew
   prefix-particle handling be scheduled as a named effort? (Both are
   modest FTS5-level changes, not a search-engine migration.)
3. **Backup posture.** Install Litestream as documented, or accept
   daily-snapshot-only with longer retention? Either is defensible at this
   scale; it should be a decision rather than a default.
4. **OCR model economics.** Code defaults to Haiku (~$3/1,000 scans);
   docs claim Sonnet (~$20/1,000, better on decorative Hebrew type). Which
   is the intended default? (Then fix whichever of code/docs is wrong.)
5. **DNB's role.** It's in ISBN lookup and the source-catalog choices but
   not in the OCR search cascade. Is German/Yiddish coverage worth adding a
   DNB cascade, or should DNB stay ISBN-only?
6. **Docs tooling.** Set up Material for MkDocs as the stack description
   promises, or drop that line and stay with plain Markdown files?
7. **Deployment target.** Stay on Fly.io, or move to AWS? Appendix A works
   this through in detail. Short version: both are fine at this scale; Fly
   is cheaper when the catalog sits idle, AWS is a better fit if the owner
   already runs things there and wants everything in one account.

---

## Appendix A — AWS as an alternate deployment target

The main plan assumes Fly.io because that is what the app is set up for
today (`fly.toml`, `Dockerfile`, `entrypoint.sh`, the deploy workflow). This
appendix works through Amazon Web Services (AWS) as an alternative, since the
owner has recently had good results deploying small web apps there. It
describes what would actually change, weighs the trade-offs, and gives a
concrete step-by-step deployment recipe sized for this app's real usage.

Nothing here is a recommendation to switch right now. It is written so that
if the owner decides to move, the path is clear; and so the comparison is on
the record either way. Dollar figures are approximate and change over time —
treat them as "which order of magnitude," not quotes, and check current AWS
and Fly pricing before committing.

### A.1 The one constraint that shapes everything: SQLite wants a single writable disk

otzar stores everything in a single SQLite database file, and cataloging
writes to it (new records, edited records, scan results). SQLite is a
single-writer database that expects a **real local disk** on **one machine**.
Three consequences drive the whole AWS design:

1. **One instance, not many.** You cannot run several copies of the app
   behind a load balancer all writing to the same database file — that
   corrupts SQLite. This is fine: at a few users and a few thousand records,
   one small machine is plenty. But it means the fashionable "serverless
   container" AWS services (App Runner, ECS Fargate) are a poor fit, because
   they are built for stateless apps that can be run in multiple copies and
   have no permanent local disk.
2. **No network file systems.** SQLite's own documentation warns against
   putting the database on a network file share. On AWS that specifically
   means **do not** put the database on EFS (Amazon's shared network disk).
   The database must live on a disk attached directly to the one instance
   (an EBS volume, or the instance's built-in SSD).
3. **The disk must persist across restarts and redeploys.** Whatever runs
   the app has to keep the same disk when you deploy new code, exactly as
   Fly's persistent volume does today.

This is the same shape as the current Fly setup (one small VM, one attached
volume). The AWS question is really "which AWS product gives me one small
always-on machine with a persistent disk, TLS, and good backups, at low
cost?" — not "how do I make this scale," because it does not need to.

If the app ever genuinely outgrew SQLite (it should not, at this scale),
the AWS-native answer would be Amazon RDS running PostgreSQL, which removes
the single-disk constraint entirely. That is explicitly out of scope here
and contradicts the plan's scale principle; it is mentioned only so the
option is known.

### A.2 The workload, and what it means for sizing

- **Browsing and searching** are light: a handful of users, intermittently,
  reading from SQLite. Trivial load.
- **Ingest sessions** are the heaviest thing the app does, but the heavy part
  is *waiting on other people's servers*, not local computation. A scan
  spends its time calling Claude Vision (OCR) and the national-library
  catalogs (NLI, LC, DNB), which are deliberately rate-limited to one request
  every few seconds. The local machine mostly resizes an image, parses a MARC
  record, and writes a few database rows.
- The one local resource that matters during ingest is **memory**, because
  image handling (resizing an uploaded title-page photo) is the most
  memory-hungry step. This argues for **1–2 GB of RAM**, not the absolute
  smallest 512 MB tier.

Conclusion: a small ARM-based instance (AWS calls these "Graviton";
instance types starting with `t4g`) with 1–2 GB of RAM handles everything,
including "heavy sustained ingest," with room to spare. There is no need for
autoscaling, multiple instances, or a large machine.

### A.3 Fly.io versus AWS — honest trade-offs

**Where Fly.io is better for this app today**

- **Scale-to-zero.** Fly can stop the machine when no one is using it and
  start it on the next request. For "a few users, here and there," the app
  is idle most of the day and costs almost nothing while stopped. Plain AWS
  instances (EC2, Lightsail) do **not** stop themselves — you pay for the
  machine 24/7 whether or not anyone visits. This is the single biggest cost
  difference, and it favors Fly for intermittent use.
- **Batteries included.** Automatic TLS certificates, a built-in persistent
  volume, daily volume snapshots, and one-command deploys already work. On
  AWS you assemble these from separate pieces.
- **It is already set up and tested.** Moving costs time and introduces new
  ways to get backups or TLS subtly wrong.

**Where AWS is better**

- **The owner already uses it.** Familiarity and having everything in one
  account is a real, non-technical advantage — fewer places to manage, one
  bill, one set of credentials.
- **A mature, first-class backup ecosystem.** S3 for durable object storage,
  automated EBS volume snapshots via AWS Backup or Data Lifecycle Manager,
  S3 versioning and lifecycle rules to age out old backups automatically.
  The owner's requirement — "write to the database and take backups, ideally
  with AWS services" — maps cleanly onto these (see A.5).
- **Durable media storage as an option.** Title-page images and covers can
  be moved to S3 (see A.5), so the photos survive even if the instance is
  lost, without a separate backup step.
- **Free tier.** A new-ish AWS account may cover a small instance and modest
  storage for the first 12 months, making a trial nearly free. (Verify — the
  specific free-tier offers change.)

**Roughly even**

- **Ongoing cost.** For an always-on small machine the two are within a few
  dollars a month of each other. Fly pulls ahead only because of
  scale-to-zero during idle time.
- **Operational burden.** Both need occasional attention. On AWS you own a
  bit more (operating-system updates on the instance), though a managed VPS
  product like Lightsail keeps this small.

### A.4 Recommended AWS architecture

The closest AWS equivalent to the current Fly setup, kept deliberately
simple:

```
                    Route 53 (or any DNS)  ── catalog.example.org
                              │  A record → static IP
                              ▼
   ┌───────────────────────────────────────────────────────────┐
   │  One small instance  (Lightsail plan, or EC2 t4g.small)    │
   │  ARM/Graviton · 1–2 GB RAM · static IP                     │
   │                                                            │
   │   Caddy  ── automatic HTTPS (Let's Encrypt), reverse proxy │
   │     │                                                      │
   │     ▼                                                      │
   │   Django app (gunicorn) — the existing Docker image        │
   │     │              runs migrations on start, as it does now │
   │     ▼                                                      │
   │   SQLite file + media   on a persistent block-storage disk │
   │     │                                                      │
   │   Litestream ── streams every DB change ──► S3 bucket      │
   └───────────────────────────────────────────────────────────┘
                              │                       ▲
              scheduled volume snapshot               │ continuous
              (AWS Backup / DLM) ──► EBS snapshot      │ backup + restore
                                                       ▼
                                                   S3 (versioned, lifecycle-aged)
```

**Two flavors of the same shape — pick one:**

- **AWS Lightsail (recommended for "light and simple").** Lightsail is AWS's
  simplified virtual-server product: a fixed monthly price that bundles the
  instance, its SSD, a generous data-transfer allowance, and a free static
  IP, with a much smaller set of knobs than raw EC2. Built-in automatic
  snapshots. This is the least-effort path and the best match for the owner's
  "deploy to AWS in a light manner." Choose a 1–2 GB RAM plan.
- **EC2 + EBS (recommended if you want the full AWS toolbox).** A `t4g.small`
  EC2 instance with a separate EBS (gp3) volume for the database and media.
  More individual pieces to configure (security group, volume, Elastic IP),
  but every AWS service — AWS Backup, fine-grained IAM, CloudWatch alarms —
  is directly available. Choose this if the owner wants to manage it
  alongside other EC2 things they already run.

Both run the **existing Docker image unchanged**, so the application itself
does not care which you pick. Everything below applies to either; where they
differ it is called out.

**Component by component**

- **The instance.** One `t4g` (Graviton/ARM) machine, 1–2 GB RAM. ARM is
  chosen because it is cheaper than Intel/AMD for the same performance and
  the app has no ARM-incompatible dependencies (it is pure Python plus
  SQLite). The Docker image is already built and would just need to be built
  for ARM (a one-line change to the build, or build multi-architecture).
- **The disk.** Lightsail: the plan's bundled SSD, optionally an added block
  disk. EC2: a gp3 EBS volume (say 20 GB — the database is tens of megabytes,
  media is the bulk, and 20 GB is generous and cheap). This is the "one
  persistent local disk" the SQLite constraint requires. Mount it and point
  both the SQLite file and `MEDIA_ROOT` at it, mirroring the Fly `/data`
  volume.
- **TLS and reverse proxy: Caddy.** Caddy obtains and renews Let's Encrypt
  certificates automatically with a two-line config and proxies to gunicorn.
  This replaces Fly's automatic TLS at zero cost. (The alternative, an AWS
  Application Load Balancer, adds roughly $16/month of fixed cost and is not
  worth it here. A CloudFront distribution in front is possible for caching
  and TLS but adds complexity for little benefit at this traffic level —
  skip both unless a concrete need appears.)
- **Static IP + DNS.** Attach a static IP (free on Lightsail while the
  instance runs; an Elastic IP on EC2, free while attached to a running
  instance). Point the domain's A record at it — via Route 53 (about
  $0.50/month for the hosted zone) or the domain registrar's own DNS at no
  extra cost.
- **The app process.** Run the existing container. The cleanest pattern is to
  let Litestream supervise the app so backup and runtime start and stop
  together: Litestream runs the app as its child process
  (`litestream replicate -exec "<start gunicorn>"`) and streams the database
  to S3 the whole time it is up. Migrations continue to run in the container
  entrypoint before gunicorn starts, exactly as today, so deploys stay
  non-destructive.

### A.5 Backups — the part the owner specifically asked about

The requirement is: the app must be able to **write to the database**, and
there must be **backups, ideally using AWS services**. Three layers, which
combine well. Use at least the first two.

1. **Continuous database backup — Litestream to S3 (primary).**
   Litestream watches SQLite's write-ahead log and streams every change to
   an S3 bucket within seconds. If the instance or disk is lost, you restore
   the database to within seconds of the last write onto a fresh instance
   with one `litestream restore` command. This is the same tool the main
   plan already recommends for Fly (see §4.7) — it is not Fly-specific, it
   just needs somewhere to stream to, and S3 is its most common target. This
   directly answers "backups with AWS services": the store is S3.
   - Give the instance permission to write to exactly one bucket (an IAM role
     on EC2, or an access key scoped to that bucket on Lightsail).
   - Turn on **S3 versioning** and an **S3 lifecycle rule** to delete old
     backup data after, say, 30–90 days, so backup storage cannot grow
     without bound. This is the AWS-native way to control backup cost.
   - Cost is trivial — a few cents a month for a database this size.

2. **Whole-disk snapshots (covers media too).**
   Litestream backs up the *database*. The *media* files (title-page images,
   covers) also need protecting. Two ways, pick one:
   - **Snapshot the whole volume** on a schedule. Lightsail has built-in
     automatic snapshots; EC2 uses AWS Backup or Data Lifecycle Manager to
     take, e.g., a daily EBS snapshot and keep the last N. This captures the
     database *and* media together, and is the simplest "everything in one
     backup" option. Snapshots are incremental, so cost is low.
   - **Or move media to S3 directly** (see layer 3), which makes media
     durable without snapshots and lets the instance disk stay small.

3. **Optional: media in S3 from the start (durability + simpler instance).**
   Configure Django (via the `django-storages` library) to store uploaded
   media in an S3 bucket instead of on the instance disk. Benefits: images
   survive instance loss with no snapshot needed; the instance disk only
   holds the small SQLite file; S3 versioning protects against accidental
   deletion. Costs: a new dependency, slightly more setup, and image reads
   go over the network (imperceptible at this scale, and CloudFront could
   cache them later if ever needed). This is an AWS-native improvement over
   the current local-media approach and pairs naturally with an AWS move —
   but it is optional; keeping media on the volume and snapshotting it is
   perfectly fine.

**Restore drill (do it once, write it down).** Whichever layers you choose,
actually perform a restore once onto a throwaway instance: launch a fresh
machine, `litestream restore` the database, pull the latest media (from
snapshot or S3), start the app, confirm the catalog looks right. An untested
backup is a hope, not a backup. The main plan already flags that the restore
procedure is currently documented-but-untested (§4.7); an AWS move is a good
moment to close that.

### A.6 Deploying and updating the code

Keep the current model: build a Docker image, run migrations in the
entrypoint, deploy by replacing the running container. What changes is only
the "where."

- **Build.** Keep the existing `Dockerfile`. Build for ARM (to match the
  `t4g` instance). GitHub Actions can build and push the image to a registry
  on every push to `main`, reusing most of the current `deploy.yml`.
- **Registry.** Push the image to GitHub Container Registry (free with the
  existing GitHub repo) or Amazon ECR (AWS-native; small storage cost).
  GHCR keeps things simplest.
- **Deploy step.** After the image is pushed, GitHub Actions connects to the
  instance over SSH (using a deploy key stored in GitHub secrets) and runs a
  short script: pull the new image, restart the container (`docker compose
  pull && docker compose up -d`). Migrations run automatically on container
  start, as they do now. This is a handful of lines and needs no extra AWS
  services.
- **Rollback.** Re-deploy the previous image tag, or restore from the last
  snapshot/Litestream point. Same discipline as today.

There is no separate database server to manage, no connection pooling, no
secrets rotation beyond the S3 credentials and the SSH deploy key — the
operational surface stays close to what Fly gives.

### A.7 Cost, and the levers that control it

Approximate monthly figures for an always-on small instance. **Verify
against current pricing.**

| Item | Approx. monthly | Notes |
| --- | --- | --- |
| Instance (Lightsail 1–2 GB, or EC2 `t4g.small`) | ~$5–15 | Fixed; the largest line item. Lightsail bundles transfer + IP. |
| Block storage (EC2 gp3 ~20 GB; bundled on Lightsail) | ~$0–2 | Tens of MB DB + media; 20 GB is generous. |
| S3 (Litestream backups + optional media) | <$1 | A few GB, versioned, lifecycle-aged. |
| Volume snapshots (if used) | <$1 | Incremental. |
| DNS (Route 53 hosted zone) | ~$0.50 | Or free via an external registrar's DNS. |
| Data transfer out | ~$0 | Low traffic; AWS includes a free monthly egress allowance that easily covers this. |
| **Total** | **~$8–18/month** | Versus roughly $3.50–6 on Fly *because Fly stops the idle machine.* |

**Cost levers, in order of impact:**

- **Instance size and family.** The instance is most of the bill. Stay on
  ARM/Graviton (`t4g`), and start at 1 GB RAM (step to 2 GB only if ingest
  image handling proves tight). Do not oversize "just in case."
- **Always-on is the price of the SQLite-single-instance design.** Unlike
  Fly, there is no clean scale-to-zero. If idle-time cost genuinely mattered,
  you could script the instance to stop overnight and start on a schedule,
  but that adds complexity and breaks "visit any time" — not worth it for a
  few dollars. Accept always-on, or note this as the reason to stay on Fly.
- **Reserved capacity.** If the app settles on AWS long-term, a 1-year EC2
  Savings Plan or Reserved Instance cuts the instance cost by a third or more
  for a commitment. Only worth it once you are sure you are staying.
- **Free tier.** A new account may make the first year nearly free — a cheap
  way to trial the move before committing.
- **Backup retention.** The S3 lifecycle rule and snapshot retention count
  are the knobs that keep backup storage from creeping up; set them once.
- **Skip the expensive-by-default pieces.** No load balancer (~$16/mo), no
  NAT gateway (~$32/mo — not needed; the instance can have a public IP
  directly), no RDS. These are the usual sources of surprise AWS bills and
  none are required here.

### A.8 What actually changes, and what stays identical

**Stays the same:** the Django code, the Docker image, migrations-in-
entrypoint, SQLite in WAL mode with a busy timeout, the media directory
layout, all configuration via environment variables, Litestream as the
backup tool, and the "one small VM + one persistent disk" shape.

**Changes:** the host (Fly machine → EC2/Lightsail instance); TLS
termination (Fly automatic → Caddy on the instance); the persistent disk
(Fly volume → EBS/instance SSD); backup destination (Fly snapshots → S3 +
EBS snapshots); the deploy step in GitHub Actions (`fly deploy` → build,
push to registry, SSH-restart); and DNS/IP wiring (Fly-managed →
static IP + your DNS). Optionally, media storage (local → S3).

Because instance identity is already all environment variables (see §6, the
same property that makes multi-tenancy cheap), the app needs little to no
code change to run on AWS — the work is in provisioning and the deploy
pipeline, not the application.

### A.9 Recommendation

- **If cost during idle time is the priority and Fly is working, stay on
  Fly.** Its scale-to-zero is a genuine fit for intermittent use and it is
  already set up. There is no technical problem with the current target.
- **If the owner would rather have everything in their AWS account, or wants
  AWS's backup tooling, move — and use the simple path:** one small
  Graviton instance (Lightsail for least effort, or EC2 `t4g.small` for full
  control), a persistent block disk holding SQLite and media, Caddy for
  automatic HTTPS, and Litestream streaming to S3 with a volume snapshot for
  media. Expect roughly $8–18/month always-on, or near-free on the first-year
  free tier while trialing.
- **Either way, do the one thing the current setup is missing regardless of
  provider:** turn on continuous backup (Litestream) and test a restore
  once. That is more important than which cloud hosts it.

A reasonable next step, if the owner wants to pursue this, is a short
spike: stand up a Lightsail instance from the free tier, deploy the existing
image, wire Litestream to a test S3 bucket, run an ingest session, and
practice a restore. That answers the real questions (does ingest feel fast
enough, is the backup story solid) for a dollar or two, without committing.
