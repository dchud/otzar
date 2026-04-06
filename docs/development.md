# Developer Documentation

## Getting started

1. Clone the repository and `cd` into it.

2. Install [uv](https://docs.astral.sh/uv/) if you don't have it already.

3. Install dependencies:

    ```bash
    uv sync
    ```

4. Copy the example environment file and configure it:

    ```bash
    cp .env.example .env
    ```

    At minimum, set `SECRET_KEY`. Generate one with:

    ```bash
    uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
    ```

    Set `ANTHROPIC_API_KEY` if you need title page OCR. The SRU endpoint URLs have sensible defaults and can be left blank for local development.

5. Run migrations and create an admin user:

    ```bash
    uv run python manage.py migrate
    uv run python manage.py createsuperuser
    ```

6. Start the development server:

    ```bash
    just dev
    ```

    The site is available at `http://localhost:8000`. The Django admin is at `/admin/`.

## Project structure

The project has three Django apps plus the `otzar` project package.

### `catalog`

The core app. Holds all bibliographic models (`Record`, `Author`, `Subject`, `Publisher`, `Series`, `Location`, `ExternalIdentifier`, `TitlePageImage`), full-text search (FTS5), browse views, and record detail/edit views.

Key files:

- `catalog/models.py` -- all catalog data models
- `catalog/search.py` -- FTS5 virtual table management and search functions
- `catalog/id_generation.py` -- record ID generation logic
- `catalog/home_views.py` -- homepage view
- `catalog/urls.py`, `catalog/search_urls.py`, `catalog/browse_urls.py` -- URL routing

### `sources`

External catalog integration. Contains clients for SRU-based library catalogs and VIAF authority lookups, MARC record parsing, and the search cascade engine.

Key files:

- `sources/sru.py` -- SRU client with pre-configured instances for NLI, LC, and VIAF
- `sources/viaf.py` -- VIAF authority search and enrichment
- `sources/marc.py` -- MARCXML parsing into structured bibliographic dicts
- `sources/cascade.py` -- search cascade engine and ISBN lookup

### `ingest`

Handles data input workflows: title page OCR via Claude Vision, scan staging/review, and the pipeline from raw input to catalog records.

Key files:

- `ingest/ocr.py` -- Claude Vision API integration for title page metadata extraction
- `ingest/models.py` -- `ScanResult` and `APIUsageLog` models
- `ingest/urls.py` -- ingest workflow URL routing

### `otzar` (project package)

- `otzar/settings.py` -- Django settings, loaded from `.env` via python-dotenv
- `otzar/urls.py` -- top-level URL configuration
- `otzar/middleware.py` -- site password middleware

## Architecture overview

Data flows through the system in this sequence:

1. **Input** -- A user provides bibliographic data in one of three ways: manual entry, ISBN/barcode scan, or title page image upload.

2. **OCR (if image)** -- The `ingest/ocr.py` module sends the image to Claude Vision, which returns structured metadata (title, author, publisher, place, date) as JSON. This metadata feeds into the next step.

3. **External catalog search** -- The `sources/cascade.py` module takes metadata (from OCR, ISBN, or manual input) and queries external catalogs. For ISBN lookups, it queries both NLI and LC directly. For metadata-based searches, it runs a cascade of progressively broader CQL queries, stopping at the first one that returns results. NLI uses `alma.*` indexes; LC uses `dc.*` and `cql.anywhere` indexes.

4. **MARC parsing** -- SRU responses contain MARCXML records. `sources/marc.py` extracts them from the SRU envelope using `mrrc` (a MARC record library), then parses standard fields (245 for title, 100 for author, 260/264 for publication info, 650 for subjects, etc.). It handles both the NLI pattern (Hebrew in primary fields) and the LC pattern (Hebrew in linked 880 fields).

5. **Candidate review** -- Parsed records from catalog searches are stored as candidates on a `ScanResult`. The user picks the best match or edits the data.

6. **Record creation** -- The selected candidate becomes a `Record` in the catalog, with related `Author`, `Subject`, `Publisher`, `ExternalIdentifier`, and other entities created as needed. The record is indexed for full-text search.

7. **VIAF enrichment** -- Author records can be enriched via `sources/viaf.py`, which searches the Virtual International Authority File to resolve VIAF IDs, variant name forms, and linked source IDs (NLI/J9U, LC).

## Data model

All models live in `catalog/models.py` except `ScanResult` and `APIUsageLog`, which are in `ingest/models.py`.

### Record

The central model. Holds a unique `record_id` (auto-generated with a configurable prefix), title (with optional romanized form), subtitle, publication date (both integer for sorting and display string), place of publication, language, source catalog (NLI or LC), and the original MARC data as JSON in `source_marc`. Linked to a creating user. Has M2M relationships to Author, Subject, Publisher, and Location.

### Author

Name and optional romanized name. Stores a `viaf_id` for authority linking and `variant_names` (JSON list) for alternate forms.

### Subject

A subject heading with optional romanized form and source indicator (LC, NLI, or local).

### Publisher

Name, optional romanized name, and place.

### Series and SeriesVolume

`Series` represents a named series with optional publisher link and total volume count. `SeriesVolume` is a join model linking a Series to a Record with a volume number and a `held` flag (whether the volume is in the collection).

### Location

A simple label for physical shelf/location within the collection. M2M with Record.

### ExternalIdentifier

Links a Record to external identifiers: ISBN, LCCN, NLI control number, VIAF ID, or OCLC number. Compound unique constraint on (record, type, value).

### TitlePageImage

An uploaded image of a book's title page, linked to a Record. Has a `staged` flag for images not yet associated with a confirmed record. Images are stored under `media/title-pages/`.

### ScanResult (ingest app)

A pending ingest workflow item. Tracks the scan type (ISBN or OCR), status (pending/confirmed/discarded), the ISBN or uploaded image, raw OCR output, candidate records from catalog search, which candidate was selected, and the final created Record. Linked to the scanning user.

### APIUsageLog (ingest app)

Tracks API calls (model, token counts) for cost monitoring.

## External source integration

### SRU client

`sources/sru.py` provides `SRUClient`, a dataclass-based HTTP client for SRU (Search/Retrieve via URL) endpoints. It uses `httpx` for requests with a configurable delay between calls (default 3 seconds, set via `SRU_REQUEST_DELAY`) to be polite to external servers.

Three pre-configured client instances are available:

- `nli_client` -- National Library of Israel (Alma SRU, version 1.2, with automatic quoting of `alma.*` index values)
- `lc_client` -- Library of Congress (version 1.1)
- `viaf_client` -- VIAF (version 1.1)

Endpoint URLs are configurable via environment variables (`SRU_NLI_URL`, `SRU_LC_URL`, `SRU_VIAF_URL`).

### VIAF client

`sources/viaf.py` provides `VIAFClient` for authority lookups. `search_by_author()` runs a cascade of query strategies: exact Hebrew heading, romanized name, broad keyword, and multi-word AND queries. Results are parsed into `VIAFCluster` objects containing VIAF IDs, main headings, source IDs, and variant name forms.

`viaf_enrich()` scores clusters by the presence of NLI (J9U) and LC source IDs and whether the query name appears in headings, returning the best match above a minimum threshold.

### Search cascade

`sources/cascade.py` defines data-driven cascades of CQL queries for NLI and LC. `NLI_CASCADE` has 7 steps (from most specific -- title+place+date -- to broadest -- title only). `LC_CASCADE` has 4 steps including a dynamic keyword builder for Hebrew titles.

`run_cascade()` iterates through steps, formats CQL templates with available metadata, skips steps where required fields are missing, and stops at the first step that returns parsed MARC records. Convenience functions `search_nli()` and `search_lc()` wrap this.

### Response caching

Django's file-based cache (configured in settings, stored at `DATA_DIR/cache`) is available for caching external API responses.

### ISBN lookup

`isbn_lookup()` in `sources/cascade.py` queries both NLI (`alma.isbn`) and LC (`bath.isbn`) for a given ISBN. Returns both result sets so the user can choose.

## OCR integration

`ingest/ocr.py` uses the Anthropic Python SDK to send title page images to Claude Vision.

The prompt instructs the model to:

- Read all Hebrew text on the page
- Extract 8 fields: title, subtitle, publisher, place, date, title_romanized, author, author_romanized
- Transliterate using ALA-LC Hebrew romanization rules
- Convert Hebrew gematria dates to Gregorian years
- Return plain Hebrew (no nikkud/vowel points)
- Return JSON only, with null for unreadable fields

The model is configurable via `CLAUDE_MODEL` (default: `claude-sonnet-4-6`). Response parsing handles markdown code fences and repairs Hebrew gershayim characters that break JSON parsing.

Requires `ANTHROPIC_API_KEY` in the environment.

## Search

### FTS5 setup

`catalog/search.py` manages a SQLite FTS5 virtual table (`catalog_fts`) with columns: `record_id` (unindexed, used as a key), `title`, `title_romanized`, `subtitle`, `authors`, `subjects`, and `notes`.

### Indexing

`index_record()` adds or updates a single record in the FTS index. It concatenates all author names (with romanized forms) and subject headings into single text fields. `reindex_all()` rebuilds the entire index. `remove_from_index()` deletes a single entry.

### Searching

`search()` runs an FTS5 MATCH query and returns `(record_id, rank)` tuples ordered by relevance. `search_records()` wraps this to return Django `Record` instances in rank order.

The FTS table is created lazily on first search via `ensure_fts_table()`.

## Testing

Run all tests:

```bash
just test
```

This runs `uv run pytest` with the Django settings module configured in `pyproject.toml`.

Pass arguments through to pytest:

```bash
just test -x              # stop on first failure
just test -k "test_marc"  # run only matching tests
```

### Fixtures and test data

Tests use cached XML responses from external catalogs (stored in the experiment cache) to avoid hitting live APIs. The `conftest.py` at the project root is minimal; fixtures are defined closer to their tests.

### Mocking external APIs

Tests that exercise SRU or VIAF logic should mock HTTP calls rather than hitting live endpoints. Use the cached response fixtures or mock `httpx.get` / the relevant client methods.

### Integration tests

Tests that require a live API key (e.g., OCR tests hitting Claude Vision) or network access should be marked and run separately to keep the default test suite fast and offline.

### Test data loading

`just load-test-data` runs a management command to load demo/test data into the database.

## Linting and formatting

Lint check (reports issues without changing files):

```bash
just lint
```

Auto-fix lint issues:

```bash
just lint-fix
```

Format code:

```bash
just fmt
```

Full CI check (tests + lint + format check):

```bash
just check
```

All linting and formatting uses [Ruff](https://docs.astral.sh/ruff/).

### Pre-commit hook

Opt in by running:

```bash
./scripts/setup-hooks.sh
```

This symlinks `scripts/pre-commit` into `.git/hooks/`. The hook runs `ruff format --check` and `ruff check` before each commit and blocks on failure, printing the commands to fix issues.

## Justfile commands

| Command | Description |
|---|---|
| `just dev` | Start the development server (`manage.py runserver`) |
| `just test [args]` | Run tests via pytest (args passed through) |
| `just lint` | Lint check with ruff |
| `just lint-fix` | Lint with auto-fix |
| `just fmt` | Format code with ruff |
| `just check` | Full CI check: tests, lint, format check |
| `just migrate` | Run database migrations |
| `just makemigrations [args]` | Create new migrations |
| `just shell` | Open Django shell |
| `just createsuperuser` | Create a Django superuser |
| `just tailwind` | Build Tailwind CSS |
| `just load-test-data` | Load test/demo data |
| `just cleanup-staging [days]` | Clean up old discarded scans (default: 30 days) |
