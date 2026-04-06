# otzar — Application plan

## Purpose

otzar is a catalog application for a small community library. The collection
spans thousands of volumes in multiple languages (English, Hebrew, Aramaic,
Yiddish, and others). The app helps the community know what they have, find
where things are, and relate items to each other.

## Users and access

- **Browsing and searching are open.** Any community member (or visitor) can
  use the catalog without logging in.
- **Cataloging requires an account.** In the short term, one or two people will
  do most of the data entry. The app should support a small group (2–3)
  cataloging simultaneously, e.g. during a work session covering different
  sections of the collection.
- The site may be placed behind a site-wide password for general web exposure
  control, separate from cataloger accounts.
- Django's built-in auth and admin cover the cataloger access needs. The admin
  interface should make it straightforward for an admin to create new user
  accounts and to set or clear a site-wide password for public browse/search
  access.

## Multilingual support

The collection includes significant material in right-to-left scripts (Hebrew,
Aramaic, Yiddish). RTL rendering, search, and navigation must work seamlessly
alongside LTR content. The interface itself is primarily English.

Records from external catalogs will often include both original-script and
romanized forms of titles, authors, and subjects. The app should store and
display both.

## Catalog browsing

Multiple browse views into the collection:

- **Author browse** — alphabetical, with variant name forms grouped
- **Title browse** — alphabetical across languages
- **Subject browse** — by subject headings from catalog records
- **Publisher browse**
- **Date browse** — by publication date, useful for understanding the
  collection's historical range
- **Location browse** — by physical location (floor, room, shelf), showing
  what's where
- **Series browse** — multi-volume sets grouped together, with indication of
  which volumes are held and any gaps

Where possible, browse views should surface relationships: other items by the
same author, other commentaries on the same base text, other volumes in the
same series, and items shelved nearby.

## Catalog search

Start with SQLite FTS5 for full-text search across all languages. Users can
search by any field (title, author, subject, etc.) or across all fields.

Known limitation: FTS5 does not handle Hebrew morphology (prefix particles,
construct forms). For a clean catalog with both Hebrew and romanized forms,
basic token matching should be adequate at this scale.

If search quality proves insufficient, add a lightweight dedicated search
service (e.g. Meilisearch or Typesense) without changing the data layer.

SQLite should be configured with WAL mode (write-ahead logging) and a busy
timeout so that concurrent reads and a small number of simultaneous writes
(e.g. 2–3 catalogers scanning at once) work without "database is locked"
errors. This is adequate for the expected scale. If concurrent write
contention becomes a real problem, PostgreSQL is the natural next step.

## Data input (ingest)

Three methods for adding items to the catalog, all usable from a phone
browser. The cataloging interface should be mobile-friendly — catalogers will
be standing at shelves with their phones, not sitting at desks.

### ISBN/barcode scan

For modern books with barcodes. The cataloger uses their phone camera via the
browser to scan a barcode. A JavaScript barcode library (e.g. QuaggaJS or the
browser-native Barcode Detection API) reads the ISBN from the camera feed. The
app then searches external catalogs (NLI, LC) by ISBN to retrieve a full
bibliographic record.

### Title page photograph + OCR

For older materials without ISBNs. The cataloger photographs the title page
with their phone. The image uploads to the server (resized client-side to
~1500px for speed and efficiency). The app sends it to Claude Vision, which
extracts structured metadata: title, author, publisher, place, date, and
romanized forms. This metadata drives a search cascade against external
catalogs to find matching records.

### Manual entry

For items where neither barcode nor OCR produces a match, or for adding
metadata not present in external records. A form for entering bibliographic
fields directly.

### Ingest flow

The three methods are not mutually exclusive. A typical flow might be: scan a
barcode, find no match, photograph the title page, get partial OCR results,
then fill in remaining fields manually. The ingest interface should make it
easy to move between methods for a single item without losing work.

When a search returns matching records (whether from ISBN lookup or OCR-driven
cascade), the cataloger sees a summary list of candidates. Each candidate
shows key fields (title, author, date, publisher) with an option to expand
full details — including the source MARC record — so the cataloger can
compare and select the best match confidently.

### Cross-device workflow

Catalogers may switch between a laptop (for reviewing and confirming records)
and a phone (for scanning barcodes and title pages). To make this easy:

- **Laptop → phone:** The ingest page shows a QR code linking directly to
  the phone scanning interface, pre-authenticated with the cataloger's
  session or a short-lived token. No URL typing or separate login.
- **Phone → laptop:** Scans land in a review queue rather than requiring
  immediate confirmation on the phone. The cataloger scans a batch of books
  on their phone, then reviews candidate matches on their laptop where it's
  easier to compare records on a larger screen.
- **Review queue:** A "pending review" list visible on any device, showing
  scanned items with their candidate matches. Supports the group workflow —
  multiple people scanning on phones while one person reviews and confirms
  at a laptop.

### Series workflow

When a cataloger identifies a volume as part of a series, the app should use
what it knows about that series (title, publisher, author, number of volumes)
to streamline ingest of subsequent volumes. For example:

- After finding volume 1 of a 13-volume set, the cataloger can indicate "I
  have all 13" or "I have volumes 1, 3, 5, 7" without repeating the full
  search cycle for each.
- The app uses known series metadata to bias searches for additional volumes
  and to maintain consistent cataloging across the set.
- Sets can be represented with gaps — "we hold 4 of 10 volumes" — visible in
  browse views.

## External sources

The app queries external bibliographic sources via the SRU protocol and VIAF
authority service. This is the `sources` Django app.

### Catalogs

- **National Library of Israel (NLI)** — primary source for Hebrew-language
  materials. SRU 1.2 via Alma, `alma.*` indexes.
- **Library of Congress (LC)** — broad coverage, romanized forms. SRU 1.1 via
  Z39.50 MetaProxy.
- **VIAF** — authority clusters linking names and identifiers across libraries.
  Used to enrich search precision (e.g. finding NLI's J9U identifier for an
  author, then searching NLI by authority ID).

### Search cascade

Searches use a cascade pattern: start with the most specific query (e.g.
title + place + date), then progressively broaden until results are found.
This pattern should be a general mechanism, not hard-coded per catalog.

### Caching and rate limiting

External query responses are cached to avoid redundant network requests.
Requests are rate-limited (3–5 second delays) to be respectful to remote
servers.

### MARC records

External catalogs return MARC records. The app uses the `mrrc` library to
parse them. Key fields: 245 (title), 100 (author), 260/264 (publication),
008 (language/date), 020 (ISBN), 880 (alternate script).

The app stores the original MARC record (as retrieved from the external
catalog) as a source copy — this is the source of truth. Key values are
extracted into normalized Django models (separate Author, Subject, Publisher,
Series models with foreign keys) to drive browse views, search, and
relationships. If a field needs correcting, the normalized data can diverge
from the source record, but the original is always available for reference.

## Physical item tracking

Each catalog record can have one or more physical locations. Locations are
freeform text defined by the community (e.g. "Floor 1, Room B, Shelf 4a").
The app stores and displays them but does not impose a location scheme.

Browse and search results can be filtered or grouped by location. Where
possible, the app surfaces items shelved nearby — useful for finding related
materials or returning items to the right place.

A structured location hierarchy (building → floor → room → shelf → section)
can be layered in later if the community develops a more formal scheme.

## Relationships between items

- **Author/authority** — items grouped by author, with variant name forms
  (Hebrew, romanized, etc.) linked via authority data from VIAF/NLI. The app
  includes lightweight authority management: on ingest, it checks whether the
  author from a new record matches or nearly matches an existing author in the
  catalog, using VIAF cluster data to identify variant spellings and
  transliterations. When a near-match is found, the cataloger is prompted to
  confirm ("this looks like the same author as these 14 other items") or
  create a new entry. This keeps the catalog consistent without requiring the
  cataloger to know authority control rules. The same approach can extend to
  subjects and series titles over time.
- **Subject** — items sharing subject headings from catalog records.
- **Series/sets** — multi-volume works linked together, with volume numbering
  and gap tracking.
- **Commentary chains** — where catalog record data supports it (e.g. subject
  fields referencing a base text), link commentaries to the texts they
  comment on.
- **Shelf proximity** — items at the same or nearby locations, useful for
  physical browsing ("you're looking for this; here's what's next to it").

## Design and accessibility

### Standards

WCAG 2.2 AA compliance throughout. This includes contrast ratios, keyboard
navigation, screen reader support, focus indicators, and form labeling.

### Visual approach

Clean, modern, and readable. Generous whitespace. Screen space can be used
fully when showing dense information (e.g. a record detail page with many
fields) but the layout must be visually coherent and easy to scan — not
cluttered.

### Typography

Font sizes should be comfortable by default, with no squinting required.
RTL text (Hebrew, Aramaic, Yiddish) typically needs to be 1–2 sizes larger
than Latin text at the same visual weight. The typographic system should
account for this so mixed-script pages read naturally.

### Language and tone

The interface assumes literate, educated users who are comfortable with
library research. Use clear, plain labels. Avoid unnecessary jargon — prefer
"author" over "main entry," "related works" over "added entries" — but don't
oversimplify where precision matters. If a field comes from a MARC record,
the display label should make sense to a non-librarian.

### Theming

Support light and dark modes. Default to the system preference
(`prefers-color-scheme`). Users can override if desired. Tailwind's dark
mode utilities handle this.

## Record identifiers and URLs

Each catalog record gets an internal ID: a configurable short prefix (default
`otzar-`) followed by a base62-encoded sequence (e.g. `otzar-3f8a`). This ID
is the primary identifier used in file paths, internal references, and APIs.
The prefix is configurable by admins so different communities can use their
own.

Catalog URLs include both the stable ID and a human-readable slug derived from
the title and/or author, e.g. `/catalog/otzar-3f8a/mishneh-torah-rambam/` for
a romanized slug or a Hebrew equivalent. Slugs support Unicode (Hebrew,
Aramaic, etc.) — modern browsers and the IRI spec handle this natively. The
app resolves records by the ID; the slug is cosmetic.

External identifiers (LCCN, NLI control number, ISBN, VIAF ID) are stored as
fields on the record, not used as primary keys.

Record detail pages should include an option to view the full source MARC
record. Useful for knowledgeable users and for debugging.

## Image storage and lifecycle

Title page scans are stored in a date-and-record-based path:
`media/title-pages/YYYY/MM/DD/{record-id}.jpg`. This avoids flat directories
and makes S3 sync straightforward.

Title page images are attached to catalog records as permanent assets, viewable
when browsing the catalog. Images from scans that don't result in a catalog
match go to a staging area (`media/staging/`) and are cleaned up periodically.

## Deployment and operations

### Hosting

Fly.io PaaS in the Ashburn (iad) region. The app runs as a Docker container
on a Firecracker microVM with a persistent NVMe volume for SQLite and media
files. SSL is automatic. Public URL at `<app-name>.fly.dev`. Estimated cost
~$3.50–6/month.

Continuous deployment via GitHub Actions: push to main runs tests, then
deploys automatically.

### Backups

Fly.io daily volume snapshots (configurable retention up to 60 days) plus
Litestream for continuous SQLite WAL streaming to S3. Media files are
included in volume snapshots. Restore procedure documented and tested.

### Safe updates

The app will be in active use while development continues. Updates must not
destroy existing data:

- The persistent volume survives deploys — DB and media are not touched by
  code changes.
- Migrations run automatically in the Docker entrypoint before gunicorn starts.
- Database migrations must be non-destructive. Review each migration with
  data safety in mind.
- Rollback: redeploy the previous image or restore from Litestream/snapshot.

### Deployment documentation

A deployment guide covering: platform setup, deploy procedure, backup and
restore, SSL management, and common maintenance tasks. Stored in `/docs`.

## Django app structure

```
otzar/
├── catalog/     # data models, browse views, search
├── sources/     # SRU clients (NLI, LC), VIAF client, caching, rate limiting
├── ingest/      # data input: barcode scan, title page OCR, manual entry
```

## Technical stack

- Python 3.13, Django 6+, SQLite
- Tailwind CSS, HTMX, Alpine.js
- Claude Vision API (OCR)
- mrrc (MARC parsing)
- Pytest, Justfile, Material for MkDocs

## Build order

1. **Django project scaffolding** — project setup, settings, initial migration,
   admin configuration, basic templates and Tailwind/HTMX integration.
2. **catalog models** — the core data models (Record, Author, Subject,
   Publisher, Series, Location) need to exist before sources or ingest can
   store anything. Start with the schema; views come later.
3. **sources** — SRU and VIAF clients, caching. Testable independently by
   running queries. Stores retrieved MARC records against catalog models.
4. **ingest** — Claude Vision OCR, barcode scanning, manual entry forms.
   Depends on sources for post-input catalog lookup and catalog models for
   storage.
5. **catalog views** — browse views, search, record detail pages. Built once
   there is real data to display from steps 3–4.

The extraction plan in `docs/plans/extract-from-experiments.md` covers the
details of porting experimental code into the sources and ingest apps.

## Deferred features

These are not needed now but are worth keeping in mind for future design
decisions:

- **Bulk import** — importing records from spreadsheets or exported files.
  Possible future need but no immediate requirement.
- **Circulation** — the community does not plan to track lending. A minimal
  checkout/return model could be added later if they change their minds.
- **Printing/export** — shelf lists, labels, or catalog export (MARCXML, CSV).
  No immediate need.
