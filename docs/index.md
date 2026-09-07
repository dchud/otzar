# otzar

A browsable, searchable, multilingual catalog for a shared collection of
books.

The collection this was built for is heavy in right-to-left scripts —
Hebrew, Aramaic, Yiddish — alongside English, and records commonly carry
both original-script and romanized forms of titles and names. Both forms
are stored, displayed and searched.

## Where to start

**[User guide](user-guide.md)** — cataloging a book by barcode, by
photographing its title page, or by typing it in; the review queue; and
browsing and searching what is in the catalog.

**[Administration](administration.md)** — configuration, environment
variables, backups and restores, and the maintenance commands.

**[Development](development.md)** — the architecture, how the pieces fit
together, and how to run the tests.

**[MARC in practice](marc-in-practice.md)** — what the National Library
of Israel, the Library of Congress and the Deutsche Nationalbibliothek
actually send, measured across 1,027 records rather than inferred from
the format documentation. Written for anyone deciding which fields to
read, and for catalogers curious about what a small catalog makes of
their records.

## How it is built

Cataloging a book means getting a bibliographic record with as little
typing as possible. A barcode scan looks the ISBN up in three national
catalogs at once over SRU. A photograph of the title page goes to a
vision model that returns title, author, publisher, place and date,
handling Hebrew typography, ALA-LC romanization and gematria dates. A
form covers what the catalogs do not have.

otzar is written with agentic coding: nearly all of its code, tests and
documentation are produced by AI agents working from tickets, under
review. `CLAUDE.md` and `AGENTS.md` in the repository are the
instructions those agents work from, and they are as much a part of the
project as the source.

The source is at [github.com/dchud/otzar](https://github.com/dchud/otzar)
and is MIT licensed.
