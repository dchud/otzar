# Plan: Extract experimental code into otzar

## Source

The directory `../learn/z3950` contains experimental scripts for searching
library catalogs and extracting metadata from Hebrew title page images. This
plan describes what to bring into otzar and how to organize it.

## What to extract

### Core: SRU catalog searching (`sru.py`)

The experimental `sru.py` provides HTTP-based SRU search against three
catalogs, XML response parsing, and MARC record extraction. Port this into a
Django app.

**Catalogs:**

- National Library of Israel (NLI) — Alma SRU 1.2, `alma.*` indexes
- Library of Congress (LC) — SRU 1.1 via Z39.50 MetaProxy, Dublin Core / Bath
  indexes
- VIAF — SRU authority search, returns clusters linking names across libraries

**Key behaviors to preserve:**

- Response caching (keyed on query parameters) to avoid redundant network
  requests
- Polite request delays (3–5 seconds between requests)
- MARC namespace registration so ElementTree serialization works cleanly
- Handling of NLI's phrase-quoting requirement (`alma.title="..."`)

### Core: MARC record parsing

The experimental code uses the `mrrc` library (0.7.4+) to parse MARC XML
records from SRU responses. Key operations:

- Extract fields: 245 (title), 100 (author), 260/264 (publication), 008
  (language/date), 020 (ISBN)
- Handle 880 fields (alternate script linkage) — LC stores Hebrew in 880
  fields linked to romanized primary fields
- Handle NLI's pattern of Hebrew directly in primary fields

The app stores the original MARC record as a source copy (the source of
truth) and extracts key values into normalized Django models. See the data
model approach in `docs/plans/app-plan.md` under "MARC records."

### Core: VIAF enrichment

`experiment_viaf.py` searches VIAF by author name to find authority clusters
that link identifiers across libraries (VIAF ID, NLI J9U number, LCCN). This
enrichment step improves downstream NLI/LC search precision.

**Key behaviors to preserve:**

- Search cascade: exact Hebrew heading → romanized heading → broad keyword →
  multi-keyword AND
- Cluster matching logic (normalize, check headings/variants/titles)
- Extraction of J9U ID and LCCN from matched clusters

### Core: Claude Vision OCR for title pages

`scan_title_page.py` sends title page images to Claude's vision API and
extracts structured metadata (title, author, publisher, place, date, romanized
forms). This is the primary OCR path.

**Key behaviors to preserve:**

- Structured JSON output schema (title, subtitle, author, publisher, place,
  date, romanized forms)
- Prompt design: no nikkud, preserve RTL order, ALA-LC romanization, Hebrew
  gematria date conversion
- Response caching keyed on image content hash + model + prompt version
- Model selection (currently Sonnet performs best for Hebrew)

### Core: Search cascade logic

Both the NLI and LC searches use a cascade pattern: start with the most
specific query (title + place + date), then progressively broaden. The cascade
stops at the first query that returns results.

**NLI cascade** (7 queries): title+place+date → title+publisher+date →
title+place → title+publisher → title+date → keywords+date → title alone

**LC cascade** (4 queries): romanized title+date → Hebrew title+date →
romanized title → multi-keyword AND

This pattern should be preserved as a general mechanism, not hard-coded per
catalog.

## What to leave behind

- **HTML comparison viewer** (`build_viewer.py`) — experiment reporting tool
- **Ground truth JSON and batch experiment runners** — test harness for
  evaluating OCR accuracy across models
- **MARC metadata backfiller** — one-off script to re-process cached results

## Open questions (defer for now)

- **Record scoring/ranking:** The experiments have a weighted scoring system
  (title 40%, date 30%, author 20%, place 10%) for ranking search results. We
  may want something like this but the design depends on how search results are
  presented to users.
- **Image preprocessing:** The experimental code has a 7-stage pipeline (EXIF
  correction, downscale, grayscale, CLAHE, content-area cropping, deskew,
  sharpen) before Tesseract OCR. Claude Vision may handle raw images well
  enough to skip most of this. Worth testing before committing to the
  complexity.
- **Tesseract OCR:** Used as a fallback/complement to Claude Vision. May not be
  needed if Claude Vision is sufficient. Keep as a possibility but don't port
  now.
- **MARC-to-Django model mapping:** The overall approach is decided (store
  source MARC, extract into normalized models), but the specific model schema
  is not yet designed.

## Suggested Django app structure

```
otzar/
├── catalog/          # catalog data models, views for browsing/searching
├── sources/          # SRU client, VIAF client, search cascade logic, caching
├── ingest/           # data input: manual entry, identifier lookup, OCR
```

- `sources` holds the external bibliographic source integration (NLI, LC, VIAF
  SRU clients) and is used by both `catalog` (identifier-based lookup) and
  `ingest` (OCR-driven search). The name distinguishes it from searching the
  local catalog.
- `ingest` holds the Claude Vision OCR integration and the different data input
  paths.
- `catalog` holds the bibliographic data models and user-facing views.

This is a starting point. The boundaries may shift as we build.

## Dependencies to add

From the experimental `pyproject.toml`, otzar will need:

- `anthropic` — Claude API (vision OCR)
- `httpx` or `requests` — HTTP for SRU/VIAF queries (pick one)
- `mrrc` — MARC record parsing
- `python-dotenv` — already implied by CLAUDE.md

Not needed initially: `opencv-python-headless`, `pillow`, `pytesseract`,
`python-bidi` (these support image preprocessing and Tesseract, which are
deferred).

## Extraction order

See `docs/plans/implementation-plan.md` for the full phased build plan. In
summary, the experimental code maps to implementation phases as follows:

- `sru.py` → Phase 2 (sources app: SRU client, MARC parser, caching)
- `experiment_viaf.py` → Phase 2 (sources app: VIAF client)
- `scan_title_page.py` (Claude Vision OCR) → Phase 3 (ingest app)
- Search cascade logic → Phase 2 (sources app: cascade engine)

The sources app (Phase 2) and catalog models (Phase 1) can be built in
parallel. The sources clients return parsed data without writing to the
database — storage happens in Phase 3 (ingest).
