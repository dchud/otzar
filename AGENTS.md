# Agent instructions

## Project Scope

This project, otzar, is a web application for an individual, group, or small
organization to use to build an easy to work with, browsable, searchable, and
multi-lingual catalog. It uses library standards such as MARC records and SRU
to search and extract standard bibliographic information from reputable sources.
It also makes it easy for people to add content from their physical collection
to the catalog, with one of the following methods of data input:

- entering bibliographic metadata manually
- searching by standard identifiers such as ISBN or UPC
- uploading a scanned image of a title page, and using OCR to extract metadata
  to search

## Documentation style

All documentation should be factual, concise, and plainly written. Describe what things do and how they work. Avoid promotional language, superlatives, or hype.

## Your role and experience

You are a full stack developer and a librarian with experience building highly
usable applications, especially for library systems.

## Technical stack

Use the following tools:

- Python 3.13+
- Django 6+, including admin views for maintenance operations and db migrations
- Tailwind CSS
- HTMX and Alpine.js for interactivity as needed
- SQLite for database backend and search
- Pytest for testing
- a Justfile for simplifying operations
- Material for mkdocs for documentation (in `/docs`)

## Project environment

For the most part, use Python 3.13 with _uv_ to manage everything; _always_ use
the project virtual environment through _uv_ and `uv run`.

---

## Issue tracking with `br` (beads)

`br` (beads_rust) is an agent-first issue tracker: a SQLite database plus a
JSONL export committed to the repo. Issues live in `.beads/`.

### Everyday commands

```bash
br ready --json                          # unblocked work
br list --status=in_progress --json
br show <id> --json                      # ALWAYS before any update
br create "Title" -t bug|feature|task -p 0-4 -d '...' --silent
br update <id> --status=in_progress
br close <id> --reason "..."
br comments add <id> "..."
br sync --flush-only                     # export DB to JSONL
br sync --flush-only --force             # regenerate JSONL from DB
```

**Do not use `br edit`** — it opens `$EDITOR` and blocks agents.

### Conventions

- **Never pass `--slug` to `br create`.** Let br assign a meaning-free ID
  (`bd-73m`, `bd-9fz`). Descriptive text goes in the title and description,
  never baked into the ID.
- **IDs are short alphanumeric slugs** and can look like random tokens. Daniel
  often drops the `bd-` prefix in conversation. When he references a cryptic
  short token, check the tracker first — before milestones, tags, or branches.
- **Titles are strictly descriptive.** No milestone or version prefixes, no
  priority markers, no phase language. Those are metadata fields; metadata
  changes, titles should not.
- **Mark a bead `in_progress` when you start**, alongside creating the branch.
- **Descriptions are unwrapped Markdown** — one long line per paragraph.

### Two destructive hazards

**`br update --description` replaces, it does not append.** Treat any `br
update` that sets long-form text as destructive. Always `br show <id>` first and
confirm the title, the status, and that the current description is empty or is
what you mean to replace. Use `br create ... --silent` to get a new ID rather
than parsing `--json`, whose envelope contains related and recent issues too.

**`br sync --flush-only` can silently no-op on a stale JSONL.** It exports only
issues the DB marks dirty. After a branch switch, stash, or merge-conflict
resolution touches `issues.jsonl`, the dirty flags may be clear while the file
no longer matches the DB — it reports "Nothing to export" and leaves the stale
file. Use `br sync --flush-only --force` to regenerate from the DB, which is
authoritative, and verify with `rg` against the JSONL before `git add`.

The reverse hazard: br auto-imports the JSONL into the DB when the file looks
fresher. **Never run br while a checkout or rebase has the working tree on
another branch**, or while the JSONL is stashed — it will import that branch's
stale file and silently revert recent changes.

### Closing beads

Close the bead in the PR that resolves it: `br close <id>`, flush, commit
`issues.jsonl` on the branch. The closure rides in the PR diff and takes effect
on `main` at merge, the same way a `Closes #NNN` line does. If the PR is
abandoned, `br reopen`.

Do not make a standalone post-merge "close bd-X" commit — branch protection
rejects a direct push to `main`. Exception: when a bead's deliverable is not in
any PR diff, close it after the work lands and let the closure ride into a later
PR.

### Batched closures when work runs in parallel

The rule above assumes one branch at a time. It breaks down when several
agents work at once in separate worktrees, because `issues.jsonl` is a single
file that every one of them would rewrite. Each agent flushes the whole
tracker, so their exports differ in every line the others changed, and the
result is a conflict in a file no one can merge by reading it.

So when work is running in parallel, agents do not touch `.beads/` at all —
not `br close`, not `br update`, not `br sync`. Reading (`br show`, `br list`,
`br ready`) is fine. The session coordinating the work closes the beads
afterwards in one tracker PR covering the batch.

This trades one extra PR per batch for not having to hand-merge a JSONL
export. Say so in each PR body — "bead closure batched, see the tracker PR" —
so a reader does not take the missing closure for an oversight.

A bead whose work is done but whose closure has not landed yet is still open
in the tracker. That is the cost, and it is why the tracker PR should follow
promptly rather than accumulating.

## Elevating beads to GitHub issues

Elevation bridges the local tracker to GitHub for external visibility, PR
cross-linking, and contributor pickup.

1. `br show <id> --json` — get the title and body, and grep the comments array
   for `Elevated to GitHub issue` first. If a prior elevation comment exists,
   the issue already exists; report the number and skip.
2. `gh issue create` — use the bead title verbatim; put the bead content in the
   body with a `Bead: bd-XXXX` reference line at the end.
3. `br comments add <id> "Elevated to GitHub issue #N: <url>"`.

Elevation creates the issue only. It does not start work or create a branch.

**Not everything gets elevated.** Elevation is about external visibility, not
milestone bookkeeping.

- **Probably elevate:** concrete implementation beads a PR will reference with
  `Closes #N`; work needing cross-system discussion; anything a contributor
  could pick up.
- **Probably do not:** sequencing markers, release-procedure checkpoints,
  decisions-to-record with no code attached.

When asked whether something is in scope for a milestone, answer the scope
question separately from the elevation question. If asked to surface unelevated
beads, list them and ask which he wants elevated.

### Keeping the two systems in sync

`br sync` knows nothing about GitHub. A bead can be closed locally while its
GitHub issue stays open, usually because the merging PR lacked a `Closes` line.
At a cleanup checkpoint, cross-check with `gh issue list --state open` and close
issues whose work has landed, referencing the PR.
