# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

**otzar** is a web application for individuals, groups, or small organizations to build a browsable, searchable, multi-lingual catalog. It uses library standards (MARC records, SRU) to search and extract bibliographic information from reputable sources.

Data input methods: manual entry, search by standard identifiers (ISBN/UPC), or OCR from scanned title page images.

See `AGENTS.md` for approach philosophy and role guidance.

## Documentation Style

Keep all documentation factual, concise, and plain. State what things do and how. No promotional language or hype.

## Technical Stack

- **Django 6+** — admin views for maintenance, db migrations
- **Tailwind CSS** — styling
- **HTMX + Alpine.js** — interactivity
- **SQLite** — database backend and search
- **pytest** — testing
- **Justfile** — task runner
- **Material for MkDocs** — documentation (in `/docs`)

## Development Environment

- **Python 3.13** with **uv** for environment and dependency management
- Always use the project virtual environment through uv (e.g., `uv run`, `uv pip install`)
- Configuration via `.env` file (loaded with python-dotenv); see `.env.example`
- **Never write to `/tmp` or execute code outside this working directory.** Use the project-local `tmp/` directory (gitignored) for scratch files and intermediate data.

# Tests

```bash
uv run pytest --ignore=tests/e2e   # unit tests only (fast)
uv run pytest tests/e2e/            # end-to-end browser tests (Playwright)
uv run pytest                       # everything
```

## Testing requirements

Any change that affects what users see or do **must** include or update an
end-to-end Playwright test in `tests/e2e/`. This includes:

- New pages or views
- Changes to existing page content or layout
- New or modified user workflows (ingest, browse, search, auth)
- Bug fixes for issues that a user would encounter in a browser
- Changes to navigation, links, or URL routing

Unit tests (`tests/`) cover internal logic: models, search indexing,
SRU/VIAF clients, MARC parsing, form validation. E2e tests (`tests/e2e/`)
cover the experience from a browser: can a user actually complete the
workflow?

When in doubt, add both.

# Linting & formatting

```bash
uv run ruff check . # Lint check
uv run ruff check --fix . # Lint with auto-fix
uv run ruff format . # Format code
```

## Pre-commit Hook

Opt in by running `./scripts/setup-hooks.sh`. This symlinks `scripts/pre-commit` into `.git/hooks/`. The hook runs `ruff format --check` and `ruff check` and blocks the commit on failure, printing fix commands.

## Issue Tracking

Uses beads_rust (`br` command). Issues stored in `.beads/`.

```bash
br ready                              # Find unblocked work
br update <id> --status=in_progress   # Claim work
br close <id>                         # Complete work
br sync --flush-only                  # Export to JSONL (run at session end)
```

Priority uses numbers 0-4 (P0=critical through P4=backlog), not words.

### Elevating beads to GitHub issues

Some beads are worth surfacing as public GitHub issues (for visibility, CI, or review). When asked to elevate a bead (e.g., "elevate bd-XXXX"):

1. `br show XXXX` — read the bead title and body
2. `gh issue create` — use the bead title; body includes the bead content plus a `Bead: bd-XXXX` reference line at the end
3. `br comments add XXXX "Elevated to GitHub issue #N: <url>"` — cross-reference back on the bead

Elevation creates the GitHub issue only. It does not start work or create a branch.

### Working on elevated beads

When starting work on an elevated bead:

1. `git checkout main && git pull` — ensure main is up to date
2. `git checkout -b bd-XXXX-short-description` — clean feature branch named after the bead
3. Work and commit on the branch, referencing the bead ID in commit messages

### Completing elevated beads

When work is ready:

1. Push the branch and create a PR referencing both the bead and the GitHub issue (use `Closes #N` in the PR body so the issue auto-closes on merge)
2. The bead stays open until the PR is merged — do not close early
3. After merge: `br close XXXX` and `br sync --flush-only`

When closing any bead that has a GitHub issue comment (elevated or not), check whether the GitHub issue also needs closing. If the PR used `Closes #N`, it's already handled.
