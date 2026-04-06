# otzar — Implementation plan

This document breaks the application plan into concrete implementation work,
organized into phases with dependencies and parallelization noted. It is
intended as a handoff to an implementation team.

**Important:** Phase names and numbers are organizational tools for this plan
only. They must not appear in code, tests, comments, documentation, or commit
messages. They are meaningless outside this document and will not make sense
after implementation is complete.

Reference documents:

- `docs/plans/app-plan.md` — what we're building and why
- `docs/plans/extract-from-experiments.md` — what to port from experimental code

---

## Phase 0: Project scaffolding

**Goal:** A running Django project with basic infrastructure in place.

**Dependencies:** None. This is the starting point.

### 0.1 Django project setup

- Initialize the Django project (`otzar`) and the three apps (`catalog`,
  `sources`, `ingest`)
- Configure `settings.py`: SQLite database (with WAL mode and busy timeout for
  concurrent access), static/media paths, installed apps, middleware
- Set up `.env` loading with python-dotenv for secrets (Anthropic API key, etc.)
- Configure `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` for local dev and eventual
  production
- Create initial superuser management command or document the step
- Set up the Justfile with common commands: `dev` (runserver), `test`, `lint`,
  `migrate`, `shell`

### 0.2 Dependencies

Add to `pyproject.toml`:

- `django` (already present)
- `anthropic` — Claude Vision API
- `httpx` — HTTP client for SRU/VIAF queries
- `mrrc` — MARC record parsing. An updated release with changes to the
  marcjson representation is expected soon; pin to the new version once
  available before implementing MARC storage.
- `python-dotenv` — environment configuration
- `pillow` — image handling for uploaded title page photos
- `qrcode` — QR code generation for cross-device handoff
- `pytest`, `pytest-django` — testing

Dev dependencies:

- `ruff` — linting and formatting (already referenced in CLAUDE.md)
- `django-debug-toolbar` — development aid

### 0.3 Configuration template

Create `.env.example` documenting all configuration variables with sensible
defaults where applicable:

```
# Django
SECRET_KEY=               # required, generate with django.core.management.utils.get_random_secret_key()
DEBUG=true                # set to false in production
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=     # set to production URL(s) when deployed

# Claude Vision OCR
ANTHROPIC_API_KEY=        # required for title page scanning
CLAUDE_MODEL=claude-sonnet-4-6  # model for OCR; sonnet recommended for Hebrew

# S3 backups (required in production, not needed for local dev)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
AWS_S3_REGION=us-east-1

# SRU catalog endpoints (defaults are the public endpoints)
SRU_NLI_URL=https://nli.alma.exlibrisgroup.com/view/sru/972NNL_INST
SRU_LC_URL=http://lx2.loc.gov:210/LCDB
SRU_VIAF_URL=https://viaf.org/viaf/search
SRU_REQUEST_DELAY=3       # seconds between requests to external catalogs

# Site settings
RECORD_ID_PREFIX=otzar-   # prefix for generated record identifiers
SITE_PASSWORD=             # optional; if set, public pages require this password
```

Settings that have stable public defaults (SRU URLs, request delay, record
prefix) should work out of the box for local development. Only
`SECRET_KEY` and `ANTHROPIC_API_KEY` are required to get started.

### 0.4 Frontend tooling

- Install and configure Tailwind CSS (via django-tailwind or standalone CLI)
- Set up HTMX and Alpine.js (CDN or vendored copies)
- Create base template (`base.html`) with:
  - HTML lang attribute, proper `dir` handling for bidi content
  - Tailwind stylesheet, HTMX and Alpine.js script tags
  - Navigation skeleton (home, browse, search, ingest)
  - Dark mode support: `prefers-color-scheme` media query, Tailwind `dark:`
    utilities, optional user toggle
  - Responsive viewport meta tag for mobile

### 0.5 Authentication and admin

- Configure Django auth with login/logout views
- Set up admin site: register future models as they're created
- Implement site-wide password middleware: optional HTTP basic auth or simple
  password gate controlled by a setting in the admin. When enabled, all
  public pages require the shared password. Cataloger accounts bypass it.

### 0.6 Testing infrastructure

- Configure pytest with pytest-django (`conftest.py`, `pytest.ini` or
  `pyproject.toml` section)
- Set up test database, fixtures directory
- Verify `uv run pytest` works with a trivial passing test

**Deliverable:** `uv run manage.py runserver` shows a styled placeholder page
with working navigation, auth, and dark mode toggle. Tests run.

### Review gate: Phase 0

- All tests pass (`uv run pytest`)
- Linting passes (`uv run ruff check .`)
- Dev server runs, placeholder page loads with styled navigation
- `.env.example` is complete; app starts with minimal config
- Dark mode toggle works
- Auth login/logout works
- Site-wide password gate works when enabled and is bypassable for logged-in
  users

---

## Phase 1: Catalog data models

**Goal:** The core schema that everything else writes to and reads from.

**Dependencies:** Phase 0 complete.

**Can parallel with:** Phase 2 (sources client code, not the storage layer).

### 1.1 Record model

The central model. Key fields:

- `record_id` — the public identifier (`otzar-3f8a` format). Base62-encoded
  sequence with configurable prefix. Stored as a CharField, used in URLs and
  file paths.
- `slug` — Unicode slug derived from title/author for readable URLs. Auto-
  generated, cosmetic (routing resolves by `record_id`). Use Django's
  `slugify()` with `allow_unicode=True` or a custom generator to support
  Hebrew/Aramaic slugs.
- `title` — primary title (original script)
- `title_romanized` — romanized form if available
- `subtitle` — optional
- `date_of_publication` — integer year for sorting and filtering. Nullable
  for undated works.
- `date_of_publication_display` — freeform string for display when the date
  is approximate or complex (e.g. "ca. 1850", "[between 1700 and 1720]",
  "5691 [1931]"). Falls back to the integer year if not set.
- `place_of_publication`
- `language` — primary language code(s)
- `source_marc` — the original MARC record stored as JSON (marcjson format).
  Easier to work with in Django templates than XML, and sufficient for
  display and re-extraction. Nullable (manually entered records won't have
  one).
- `source_catalog` — which external catalog the MARC came from (NLI, LC, or
  null for manual entry)
- `notes` — freeform text for cataloger annotations
- `created_by` — FK to User
- `created_at`, `updated_at` — timestamps

### 1.2 Author model

- `name` — display name (original script)
- `name_romanized` — romanized form
- `viaf_id` — VIAF cluster identifier, nullable
- `variant_names` — JSON field storing alternate forms from authority data
- M2M relationship to Record (an author can have many works; a work can have
  multiple authors/contributors)

### 1.3 Subject model

- `heading` — subject heading text
- `heading_romanized` — romanized form if applicable
- `source` — where the heading came from (LC, NLI, local)
- M2M relationship to Record

### 1.4 Publisher model

- `name` — publisher name
- `name_romanized`
- `place` — associated city/location
- M2M or FK relationship to Record

### 1.5 Series model

- `title` — series title
- `title_romanized`
- `total_volumes` — expected total, nullable (may not be known)
- `publisher` — FK to Publisher, nullable

### 1.6 SeriesVolume (through model)

- `series` — FK to Series
- `record` — FK to Record
- `volume_number` — the volume's position in the series. String, not integer,
  to support non-numeric designations (e.g. "3a", "supplement", "index").
- `held` — boolean, defaults to True. Allows representing gaps (known volumes
  not in the collection).

### 1.7 Location model

- `label` — freeform text (e.g. "Floor 1, Room B, Shelf 4a")
- M2M relationship to Record (an item could be in multiple locations; a
  location has many items)

### 1.8 ExternalIdentifier model

- `record` — FK to Record
- `identifier_type` — choice field: ISBN, LCCN, NLI control number, VIAF ID,
  OCLC, etc.
- `value` — the identifier string
- Unique constraint on (record, identifier_type, value) to prevent duplicates

### 1.9 TitlePageImage model

- `record` — FK to Record, nullable (staging images have no record yet)
- `image` — FileField. Staging images (not yet linked to a record) stored at
  `media/staging/YYYY/MM/DD/{uuid}.ext`. On record confirmation, moved to
  `media/title-pages/YYYY/MM/DD/{record-id}.ext`.
- `uploaded_at` — timestamp
- `staged` — boolean, True if not yet attached to a record

### 1.10 Record identifier generation

Implement the base62-encoded ID with configurable prefix:

- A site settings model (singleton) or Django settings for the prefix string
- A utility function that generates the next ID from a sequence
- The prefix default is `otzar-`

### 1.11 Admin registration

Register all models in Django admin with reasonable list displays, search
fields, and filters. The admin is the primary maintenance interface.

### 1.12 FTS5 setup

- Create an FTS5 virtual table (via migration) indexing key Record fields:
  title, title_romanized, notes
- Index Author names, Subject headings. Since these live in separate tables,
  the FTS index will need denormalized content (copy text into the FTS table
  on save, kept in sync via signals or explicit updates).
- Provide a search manager or utility function that queries the FTS5 table
  and returns ranked Record querysets

**Deliverable:** Migrations run. Models are visible in admin. A management
command or test can create and search sample records.

### Review gate: Phase 1

- All migrations apply cleanly on a fresh database
- All model tests pass: creation, validation, relationships, ID generation
- FTS5 search returns expected results for test records in multiple languages
- Admin interface is usable: can create, edit, search, and filter all models
- Record ID generation produces unique, correctly prefixed identifiers

---

## Phase 2: Sources app — external catalog clients

**Goal:** Working SRU and VIAF clients that can query external catalogs and
return parsed results.

**Dependencies:** Phase 0 complete. All of Phase 2 is model-independent — the
clients return parsed data without writing to the database. Can be built and
tested entirely in parallel with Phase 1.

### 2.1 SRU client

Port from experimental `sru.py`. A Python class or module that:

- Accepts a catalog identifier (NLI, LC) and query parameters
- Builds a CQL query string
- Makes an HTTP GET request via httpx
- Handles NLI's phrase-quoting requirement
- Handles LC's specific endpoint and SRU version
- Returns the raw XML response
- Includes polite delay between requests (configurable, default 3–5 seconds)
- Handles errors gracefully: network timeouts, HTTP errors, malformed
  responses. Returns a clear error result rather than crashing. The ingest
  UI should inform the cataloger when an external service is unavailable
  and allow them to proceed with manual entry.

Test with known queries against NLI and LC. Verify responses parse correctly.

### 2.2 MARC record parser

Port from experimental code. Uses `mrrc` to:

- Parse MARC XML records from SRU response envelopes
- Extract key fields: 245, 100, 260/264, 008, 020, 880
- Handle LC's 880-field alternate script linkage
- Handle NLI's direct Hebrew in primary fields
- Return a structured dict of extracted metadata

Test with saved SRU response XML from the experiment cache.

### 2.3 Response caching

Port the caching strategy from the experiments:

- Cache key: hash of base URL + query parameters
- Store cached responses in a Django-managed location (database table or file
  cache — decide during implementation)
- Cache lookup before making network requests
- Cache invalidation: time-based expiry (configurable, e.g. 30 days) or manual

### 2.4 VIAF client

Port from experimental `experiment_viaf.py`:

- Search VIAF by author name using a cascade (exact Hebrew → romanized →
  broad keyword → multi-word AND)
- Parse VIAF cluster responses: extract VIAF ID, J9U ID, LCCN, authorized
  headings, variant name forms
- Cluster matching logic: normalize and compare headings/variants
- Return structured enrichment data

Test with known author names.

### 2.5 Search cascade engine

Implement the general cascade mechanism:

- Takes a catalog identifier and a dict of metadata fields
- Runs a sequence of progressively broader queries (defined per catalog)
- Stops at the first query returning results
- Returns parsed MARC records

The NLI and LC cascade definitions (query templates and field mappings) are
configuration, not code. Define them as data structures that the cascade
engine consumes.

### 2.6 ISBN lookup

A simpler search path: given an ISBN, query NLI and LC directly by ISBN
(`bath.isbn` for LC, `alma.isbn` for NLI). No cascade needed — it's a
direct identifier match.

**Deliverable:** A management command or test script that takes an ISBN, author
name, or title and returns matching records from NLI/LC with VIAF enrichment.
All network responses are cached.

### Review gate: Phase 2

- All client tests pass using saved fixtures (no network dependency)
- Integration tests against live NLI, LC, and VIAF endpoints pass (run
  manually, not in CI)
- ISBN lookup returns correct records for known ISBNs
- Search cascade produces results for known Hebrew titles
- VIAF enrichment correctly extracts authority IDs and variant name forms
- Response caching works: second identical query hits cache, not network
- Rate limiting respected (verify delays between requests)

---

## Phase 3: Ingest app — data input workflows

**Goal:** Catalogers can add items via barcode, title page photo, or manual
entry from their phones.

**Dependencies:** Phase 1 (models) and Phase 2 (sources clients) complete.

### 3.1 Manual entry form

The simplest ingest path. A Django form for entering bibliographic fields
directly:

- Title, subtitle, author, publisher, place, date, language
- Location (freeform text)
- Notes
- On save: creates Record and related model instances (Author, Publisher, etc.)
- Mobile-friendly layout (single column, large touch targets)

This also serves as the editing interface for records created via other
methods.

### 3.2 ISBN/barcode scanning

Frontend:

- A page with a camera viewfinder using a JavaScript barcode library
  (QuaggaJS or Barcode Detection API)
- On successful barcode read, send ISBN to the server via HTMX

Backend:

- Receive ISBN, run ISBN lookup against NLI and LC
- Return a list of candidate records with key fields displayed
- Each candidate has an "expand details" option showing full metadata and
  source MARC
- Cataloger selects a match → pre-fills the manual entry form with extracted
  data for review and confirmation
- On confirm: create Record with source MARC attached

### 3.3 Title page OCR

Frontend:

- A page with camera capture (`<input type="file" accept="image/*"
  capture="environment">`)
- Client-side image resize to ~1500px on the long edge before upload
  (JavaScript, using canvas)
- Upload via HTMX with progress indicator

Backend:

- Receive image, store in staging area
- Send to Claude Vision API with the OCR prompt (port from experimental code):
  - Structured JSON output: title, subtitle, author, publisher, place, date,
    romanized forms
  - No nikkud in Hebrew output
  - ALA-LC romanization
  - Hebrew gematria date conversion
- Display extracted metadata to cataloger for review/correction
- On confirmation, run search cascade against NLI/LC
- Display candidate records (same UI as 3.2)
- Cataloger selects match or proceeds with OCR-extracted data alone
- On confirm: create Record, attach title page image

### 3.4 Authority matching on ingest

When creating a new Record, before saving:

- Check if the author name matches or nearly matches an existing Author in the
  catalog
- Use VIAF cluster data (variant names) to identify near-matches
- If matches found, prompt the cataloger: "This looks like the same author as
  N other items. Confirm?" with the option to link to existing Author or
  create a new one
- Same pattern for Publisher (exact match check)

### 3.5 Series workflow

After a Record is created or during ingest:

- If the source MARC record contains series data (MARC 490/830 fields),
  present it to the cataloger
- Option to link to an existing Series or create a new one
- "Add more volumes" flow:
  - Cataloger indicates volume numbers held (e.g. "all 13" or "1, 3, 5, 7")
  - For volumes not yet in the catalog, the app uses known series metadata
    (title, author, publisher) to pre-fill search queries
  - Each additional volume can be confirmed quickly without repeating the full
    ingest cycle
- SeriesVolume records created for held volumes; gap volumes represented with
  `held=False` if total is known

### 3.6 Review queue

Scanned items (barcode or title page) land in a review queue rather than
requiring immediate confirmation on the phone. This supports cross-device
workflow (scan on phone, review on laptop) and group cataloging (multiple
scanners, one reviewer).

- A `ScanResult` model (or similar) storing: uploaded image or ISBN, OCR
  output, candidate MARC records from external search, status (pending /
  confirmed / discarded), scanned-by user, timestamp
- Queue view showing pending items with candidate matches
- Each item expandable to show full candidate details and source MARC
- Confirm action: creates the Record and related models from the selected
  candidate
- Discard action: marks the scan as discarded (image moves to staging cleanup)
- Staging cleanup: a management command (runnable via cron or manually) that
  deletes discarded scan results and their images after a configurable
  retention period (e.g. 30 days), giving catalogers time to reconsider

### 3.7 Cross-device handoff

- Ingest page shows a QR code linking to the phone scanning interface
- QR link includes a short-lived auth token (via Django's signing framework
  or a one-time token) so the cataloger doesn't need to log in again on the
  phone
- Phone scanning UI is minimal: scan barcode or take photo, see brief
  confirmation that it landed in the queue, move to the next item
- Review and confirmation happen on any device via the queue view

### 3.8 Ingest session state

The ingest interface should preserve work-in-progress across the three methods.
If a barcode scan fails and the cataloger switches to title page OCR, any data
already entered or extracted should carry over. Implementation options:

- Session storage (Django sessions)
- HTMX-driven single-page flow that accumulates state client-side
- Decide during implementation based on complexity

**Note on OCR response time:** Claude Vision API calls take a few seconds. For
the phone scanning workflow this is acceptable — the scan lands in the review
queue and the cataloger moves to the next item. If processing time becomes an
issue with high-volume scanning, a background task queue (e.g. Django-Q or
Celery) could process OCR asynchronously, but this is not needed initially.

**Note on API costs:** Claude Vision calls cost roughly $0.02 per image with
Sonnet. At hundreds of scans this is modest but not zero. The admin interface
should show basic usage stats (total scans, recent API calls) so costs can
be monitored. Consider adding a configurable daily or monthly scan limit as
a safety net.

**Deliverable:** A cataloger can add a record via any of the three methods from
a phone browser, with series workflow, authority matching, review queue, and
cross-device handoff working.

### Review gate: Phase 3

- Manual entry creates a complete Record with all related models
- Barcode scan finds and imports a known ISBN
- Title page OCR extracts correct metadata from test images (Hebrew and
  English)
- Search cascade returns candidates after OCR extraction
- Candidate selection UI shows summary and expandable detail with source MARC
- Authority matching correctly identifies existing authors and prompts for
  confirmation
- Series workflow: can create a series from one volume, add additional
  volumes, represent gaps
- Review queue: scans land in pending state, can be confirmed or discarded
  from a different device
- QR code handoff works: scan from laptop, open on phone, scans appear in
  queue
- All ingest tests pass
- Test on an actual phone (iOS Safari and/or Android Chrome): camera capture,
  image upload, barcode scan

---

## Phase 4: Catalog views — browsing and search

**Goal:** The public-facing catalog with multiple browse paths and search.

**Dependencies:** Phase 1 (models), and at least some data in the database
(from Phase 3 testing or fixtures).

**Can parallel with:** Phase 3 (later tasks). Browse views don't depend on
the ingest UI being finished — they just need data. Create a management
command or fixture set that populates the database with representative test
records (Hebrew, English, mixed-script, series with gaps, multiple authors)
using real MARC data from the experiment cache. This test dataset is also
useful for development and demos.

### 4.1 Record detail page

- Display all fields from the Record and related models
- Show title page image if present
- Show related items: other works by the same author, other volumes in the
  same series (with gap indicators), items at the same location
- Show commentary chain links where data supports it (subject field analysis)
- "View source MARC" expandable section, rendered in tagged display format
  (field tag, indicators, subfield codes with values) — the standard
  human-readable MARC presentation familiar to librarians
- External identifier links (clickable LCCN, NLI links, VIAF links)
- Proper bidi rendering: `dir="rtl"` on Hebrew/Aramaic content blocks, `dir`
  auto-detection where script is mixed
- URL format: `/catalog/{record_id}/{slug}/`

### 4.2 Browse views

Each browse view is a paginated, alphabetical (or chronological) listing with
links to record detail pages.

- **Author browse:** `/browse/authors/` — grouped by Author, showing work
  count per author. Variant name forms shown together.
- **Title browse:** `/browse/titles/` — alphabetical listing across all
  languages. For mixed-script sort order, use ICU collation (via Python's
  `icu` library or SQLite ICU extension) or maintain a separate sort key
  field. At minimum, group by script (Hebrew titles together, Latin titles
  together) rather than interleaving by raw Unicode codepoint.
- **Subject browse:** `/browse/subjects/` — grouped by Subject heading, with
  record counts.
- **Publisher browse:** `/browse/publishers/`
- **Date browse:** `/browse/dates/` — by decade or century, useful for
  visualizing the collection's historical range.
- **Location browse:** `/browse/locations/` — grouped by Location label,
  showing what's shelved where.
- **Series browse:** `/browse/series/` — each series with its volumes listed,
  held/gap status indicated.

Each browse view should offer links to related views (e.g. from an author
page, link to subjects they appear under).

### 4.3 Search

- Search bar in the site navigation (accessible from every page)
- Full-text search across all indexed fields via FTS5
- Results page showing matching records with key fields highlighted
- Faceted filtering by author, subject, date range, location, language
  (progressive enhancement — start with basic search, add facets iteratively)
- Search works across languages: a query in Hebrew or romanized form should
  find the same record

### 4.4 Home page

- Search bar prominently placed
- Quick links to browse views
- Summary stats (total records, authors, recent additions)
- Keep it simple — this is the main entry point for community members

### 4.5 RTL and bidi rendering

Cross-cutting concern across all views:

- Use `dir="auto"` on text elements that may contain either LTR or RTL content
- Use `dir="rtl"` on blocks known to be Hebrew/Aramaic
- Tailwind's RTL utilities (`rtl:` variant) for layout adjustments
- Test with real Hebrew content — verify text alignment, punctuation placement,
  mixed-script lines

### 4.6 Typography

- Configure Tailwind with a type scale that accounts for RTL sizing (Hebrew
  text 1–2 sizes larger than Latin at the same visual weight)
- Choose fonts that cover Latin, Hebrew, and Aramaic well. System font stack
  as a baseline; consider a web font with strong Hebrew support if needed.
- Test readability on phone screens

**Deliverable:** A fully browsable, searchable catalog with all browse views
working, bidi rendering correct, and readable typography.

### Review gate: Phase 4

- All browse views render correctly with real data (seeded or from ingest
  testing)
- Record detail page shows all fields, related items, title page image, and
  expandable source MARC
- Browse views show correct counts, groupings, and pagination
- Series browse shows held volumes and gaps correctly
- Search returns relevant results for queries in Hebrew, English, and
  romanized forms
- Mixed-script pages render correctly: RTL alignment, punctuation placement,
  `dir` attributes present
- Typography: Hebrew text is readable and appropriately sized relative to
  Latin text
- All view tests pass

---

## Phase 5: Design polish and accessibility

**Goal:** The app meets WCAG 2.2 AA and looks good on all devices.

**Dependencies:** Phases 3 and 4 substantially complete.

**Note:** Accessibility should be considered throughout development, not just
in this phase. This phase is for a dedicated audit and polish pass.

### 5.1 WCAG 2.2 AA audit

- Contrast ratios on all text (both light and dark modes)
- Keyboard navigation: every interactive element reachable and operable
- Focus indicators visible and clear
- Form labels, error messages, ARIA attributes
- Screen reader testing (VoiceOver on macOS/iOS at minimum)
- Image alt text for title page scans

### 5.2 Mobile optimization

- Test all flows on phone-sized screens (especially ingest workflows)
- Touch targets at least 44x44px
- Camera interactions (barcode scan, title page photo) tested on iOS Safari
  and Android Chrome
- Image upload resize verified on mobile browsers

### 5.3 Dark mode verification

- All pages tested in both light and dark modes
- Contrast ratios pass in both modes
- No hard-coded colors that break in dark mode
- Title page images: consider a subtle border or background so they don't
  float against dark backgrounds

### 5.4 Visual coherence review

- Consistent spacing, alignment, and typographic hierarchy across all pages
- Dense pages (record detail, browse lists) reviewed for scannability
- Mixed-script pages (Hebrew/English side by side) reviewed for visual balance

**Deliverable:** Accessibility audit report with all issues resolved. App
tested on desktop and mobile in both themes.

### Review gate: Phase 5

- WCAG 2.2 AA automated audit passes (axe-core or pa11y, zero critical/serious
  issues)
- Keyboard navigation tested on all pages: every interactive element
  reachable, focus indicators visible
- Screen reader tested (VoiceOver): pages announce correctly, forms are
  labeled, images have alt text
- All pages pass contrast checks in both light and dark modes
- Mobile tested on real phones: ingest flows, browse views, search, record
  detail
- Touch targets meet minimum 44x44px
- Visual coherence: consistent spacing and hierarchy across all pages

---

## Phase 6: Deployment and operations

**Goal:** The app is running on a public server with SSL, backups, and
documented procedures.

**Dependencies:** Core functionality (Phases 0–4) complete. Can begin setup
in parallel with Phase 5.

**Platform: Fly.io** (PaaS). App runs as a Docker container on a Firecracker
microVM in the Ashburn (iad) region. SQLite and media files on an attached
persistent volume. SSL automatic. Public URL at `<app-name>.fly.dev`.

### 6.1 Fly.io setup

- `fly launch` to create the app in the iad region
- Create a 1GB persistent volume: `fly volumes create appdata --region iad --size 1`
- Configure `fly.toml` with volume mount, health check, and machine size
- Create `Dockerfile` with Python 3.13, uv, gunicorn
- Docker entrypoint script: run migrations, collect static files, start gunicorn
- Set secrets: `fly secrets set SECRET_KEY=... ANTHROPIC_API_KEY=...`
- First deploy: `fly deploy`, then `fly ssh console -C "python manage.py createsuperuser"`

### 6.2 GitHub Actions CD

- `.github/workflows/deploy.yml`: test → deploy pipeline
- Tests (pytest, ruff check, ruff format --check) run first
- Deploy only on push to main, only if tests pass
- `FLY_API_TOKEN` stored as GitHub repository secret
- `concurrency: deploy` prevents simultaneous deploys

### 6.3 Backups

- Fly.io daily volume snapshots (configure retention up to 60 days)
- Litestream for continuous SQLite WAL streaming to S3 (near-real-time backup)
- Media files included in the volume snapshots
- Document and test restore from both snapshot and Litestream

### 6.4 Safe update procedure

Push to main triggers: tests → build → deploy → entrypoint runs migrations →
gunicorn starts. Data safety:

- Volume persists across deploys (DB and media untouched by code changes)
- Migrations run in the entrypoint before gunicorn starts
- Non-destructive migrations only — review each migration for data safety
- Rollback: `fly deploy --image <previous-image>` reverts the code; restore
  DB from Litestream or volume snapshot if migration was destructive

### 6.5 Monitoring

- `/health/` endpoint (already implemented) checked by Fly.io's built-in
  health checks
- `fly logs` for log access
- Optional: external uptime monitoring

### 6.6 Deployment documentation

Write a deployment guide in `/docs` covering:

- Fly.io setup from scratch (fly launch, volumes, secrets)
- GitHub Actions CD configuration
- Backup configuration (Litestream + volume snapshots) and restore procedure
- Management commands (createsuperuser, load_test_data, cleanup_staging)
- Common maintenance tasks

**Deliverable:** App running at `<app-name>.fly.dev` with SSL, CD from
GitHub, continuous backups, and documented procedures.

### Review gate: Phase 6

- App accessible at the Fly.io URL over HTTPS
- Health check endpoint returns 200
- GitHub Actions pipeline: push to main runs tests then deploys
- Litestream backup running, verified restore
- Safe update tested: push a migration, verify existing data preserved
- `fly ssh console` works for management commands

---

## Phase 7: Documentation

**Goal:** A complete set of documentation for developers and system
maintainers.

**Dependencies:** Phases 0–6 substantially complete. Write docs against the
real, deployed system so they describe what actually exists. Developer docs
(getting started, project structure) can be started incrementally during
earlier phases; the dedicated documentation phase is for completing and
verifying the full set.

### 7.1 Developer documentation

Audience: someone setting up the project for local development or contributing
code.

- **Getting started:** clone, install dependencies, configure `.env`, run
  migrations, create a superuser, start the dev server
- **Project structure:** what each Django app does, where to find things
- **Architecture overview:** how the apps relate (sources → ingest → catalog),
  data flow from external catalogs to local records
- **Data model reference:** the models, their relationships, and key fields.
  Generated or maintained alongside the models.
- **SRU/VIAF integration:** how the external source clients work, the cascade
  mechanism, caching behavior, rate limiting
- **OCR integration:** how Claude Vision is used, the prompt, expected output,
  caching
- **Testing:** how to run tests, how fixtures work, how to run integration
  tests against live endpoints
- **Coding conventions:** linting, formatting, pre-commit hook, commit message
  style

### 7.2 System administration documentation

Audience: someone responsible for keeping the production system running.

- **Deployment guide:** setting up the production environment from scratch,
  step by step
- **Configuration reference:** every `.env` variable, what it does, what
  values are valid, which are required
- **Routine operations:** deploying updates (the safe update procedure),
  creating user accounts, setting/clearing the site-wide password
- **Backup and restore:** how backups work, where they go, how to verify
  them, how to restore from a backup (full procedure, tested)
- **Monitoring and troubleshooting:** health check endpoint, where to find
  logs, common issues and fixes
- **Upgrade guide:** how to apply upgrades, what to check after an upgrade,
  how to roll back

### 7.3 User-facing help

Audience: catalogers and community members using the app.

- Brief in-app help or a help page covering:
  - How to search the catalog
  - How to browse by author, title, subject, etc.
  - For catalogers: how to scan a barcode, photograph a title page, use
    manual entry, work with the review queue, add series volumes
- Keep it concise. The interface should be self-explanatory for most tasks;
  the help docs cover non-obvious workflows.

**Deliverable:** Complete documentation in `/docs`, built with Material for
MkDocs, covering developer setup, system administration, and basic user help.

---

## Final implementation quality gate

This gate verifies the implementation is complete and correct. Deployment
and documentation are separate concerns that proceed alongside or after.

- [ ] All tests pass (`uv run pytest`)
- [ ] Linting passes (`uv run ruff check .`)
- [ ] Format clean (`uv run ruff format --check .`)
- [ ] All implementation phase review gates completed (scaffolding, models,
      sources, ingest, views, polish)
- [ ] End-to-end test: scan a barcode, ingest a record, find it via browse
      and search, verify it displays correctly with title page image
- [ ] End-to-end test: photograph a Hebrew title page, OCR extracts metadata,
      search finds candidates, confirm a record, verify authority matching
      and series workflow
- [ ] End-to-end test: scan on phone via QR handoff, confirm on laptop via
      review queue
- [ ] WCAG 2.2 AA compliance verified
- [ ] Mobile tested on real devices (iOS Safari, Android Chrome)
- [ ] Simplicity review: assess the full codebase for redundant or overly
      complex code that could be simplified for easier maintenance
- [ ] Stakeholder walkthrough: demonstrate the system to the community contact
      and incorporate feedback

## Production readiness (separate from implementation quality)

- [ ] Production deployment is running with SSL, backups verified
- [ ] Restore procedure tested from production backup
- [ ] Documentation is complete and accurate (developer, sysadmin, user help)

---

## Parallelization summary

```
Phase 0: Scaffolding
  │
  ├──→ Phase 1: Catalog models ──┐
  │                               │
  └──→ Phase 2: Sources clients ──┤
       (no model dependency —     │
        returns data, doesn't     │
        write to DB)              │
                                  ▼
                    Phase 3: Ingest
                    (needs Phase 1 + Phase 2)
                                  │
                    ┌─────────────┤
                    ▼             ▼
      Phase 4: Catalog views    Phase 6: Deploy
      (needs Phase 1 + data)    (once hosting decided;
                    │            can overlap with
                    ▼            Phases 4–5)
          Phase 5: Polish
                    │
                    ▼
          Phase 7: Documentation
                    │
                    ▼
          Final review gate
```

Two people could work in parallel on Phases 1 and 2 (models and source
clients) after scaffolding is done. All of Phase 2 is model-independent — the
sources clients return parsed data; writing to the database is an ingest
concern (Phase 3). Deployment (Phase 6) can begin once the hosting platform
is chosen and enough of the app exists to deploy, independent of browse views
and polish.

---

## Testing strategy

Each phase should include tests for the code it produces:

- **Phase 1:** Model tests — creation, validation, ID generation, FTS5 search
- **Phase 2:** Client tests using saved XML responses from the experiment
  cache (no live network calls in tests). Integration tests against live
  endpoints can be marked and run separately.
- **Phase 3:** Ingest workflow tests — form submission, OCR mock (mock the
  Claude API call), authority matching logic, series creation
- **Phase 4:** View tests — page loads, correct data displayed, bidi
  attributes present, search returns expected results
- **Phase 5:** Accessibility tests — automated (axe-core or pa11y) plus manual
  checklist

Use the experiment's cached SRU/VIAF responses as test fixtures where
applicable. This avoids network dependency and provides known-good data.

Review gates at each phase boundary ensure quality before building on top of
previous work. The final review gate is a comprehensive end-to-end check
before production use.
