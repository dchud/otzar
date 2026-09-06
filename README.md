# otzar

A browsable, searchable, multilingual catalog for a shared collection of
books.

The collection this was built for is heavy in right-to-left scripts —
Hebrew, Aramaic, Yiddish — alongside English, and records commonly carry
both original-script and romanized forms of titles and names. Both forms
are stored, displayed and searched.

**otzar is written with agentic coding.** Nearly all of its code, tests
and documentation are produced by AI agents working from tickets, under
review. `CLAUDE.md` and `AGENTS.md` are the instructions those agents
work from, and they are as much a part of the project as the source. If
you are reading the code, that is the context it was written in.

## What it does

Cataloging a book means getting a bibliographic record with as little
typing as possible. There are three ways in:

- **Scan a barcode.** The ISBN is looked up simultaneously in the
  National Library of Israel, the Library of Congress and the Deutsche
  Nationalbibliothek over SRU. Candidate records are shown for review.
- **Photograph the title page.** The image goes to Claude Vision, which
  returns the title, author, publisher, place and date — handling Hebrew
  typography, ALA-LC romanization and gematria dates. The extracted
  fields are editable, then used to search the same catalogs through a
  cascade of progressively broader queries.
- **Type it in.** A form for records the catalogs do not have.

A phone can act as the camera for either scanning path. Scanning a QR
code on the desktop page signs the phone in to the same session; photos
taken there appear on the desktop for review, and either device can
trigger the lookup or discard the image.

Confirmed records keep the original MARC they came from, so nothing the
catalog sent is lost even where local fields are corrected.

Browse by author, title, subject, publisher, date, place, series or
shelf location. Search covers titles, authors, subjects, publishers,
places, notes and identifiers, in both scripts.

## Stack

Django 6 on Python 3.13, SQLite for both storage and full-text search
(FTS5), Tailwind CSS with HTMX and Alpine.js, pytest and Playwright for
tests, uv for dependencies, just as the task runner.

The scale it is built for: a few thousand records, a handful of
cataloguers. That assumption is deliberate and shapes the design —
there is no message queue, no separate search server, and no need for
one.

## Running it locally

```bash
uv sync
cp .env.example .env          # set SECRET_KEY and ANTHROPIC_API_KEY
just migrate
just createsuperuser
just dev
```

Title-page OCR needs an `ANTHROPIC_API_KEY`. Everything else works
without one.

To use a phone as the camera, `just lan` serves over HTTPS on the local
network, which browsers require before granting camera access. It
generates a certificate with `mkcert` on first run.

```bash
just check          # format, lint, unit and browser tests
just check-quick    # the same, without the browser tests
```

## Documentation

- `docs/user-guide.md` — cataloging and searching
- `docs/development.md` — architecture and how the pieces fit
- `docs/administration.md` — configuration, backups, maintenance commands

Issues are tracked in `.beads/` with [beads](https://github.com/Dicklesworthstone/beads_rust).

## License

MIT. See `LICENSE`.
