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
