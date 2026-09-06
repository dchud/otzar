# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

See `AGENTS.md` for project scope and role guidance.

## Who you're working with

Daniel is a solo developer. He reviews his own pull requests in the GitHub PR
view and merges them himself. There is no review queue and no second approver.

Two consequences shape the rest of this file:

- **Less process, not more.** Ceremony that suits a fifty-person codebase is
  overhead here.
- **The merge is his gate.** Everything up to "PR is open and CI is green" is
  yours. The merge never is.

He corrects directly and expects corrections to stick. A push-back is a
standing rule, not a one-time preference.

## Tone

Flat, matter-of-fact, direct — in replies and in everything you author for the
project: docs, commit messages, PR bodies, issue text, code comments.

Avoid feigned enthusiasm ("Great!", "Excellent!"), opener affirmations that
rubber-stamp a choice ("Good call", "Sounds good"), marketing language in
documentation, and restatement of what he just said. Lead with substance.

**No jargony idioms or euphemisms.** State the literal technical claim. Do not
write: belt-and-suspenders, low-hanging fruit, moving the needle, boil the
ocean, kicking the can down the road, table stakes, north star. Do not write
euphemisms — say "remove", not "sunset"; "stop working on for now", not
"deprioritize". Pithy is fine when it is literal.

**Precision over reassurance.** Name exactly what a change delivers, no more.
Overclaiming erodes trust the first time the broader claim fails in practice.

## Working rhythm

```
new issue  ->  new branch from main  ->  mark the bead in_progress
           ->  work  ->  ./scripts/check.sh green
           ->  commit  ->  push  ->  open PR
           ->  report CI green  ->  STOP and wait for "merge it"
```

**Commit and open the PR without asking.** When a coherent unit of work is done
and local checks pass, go straight to commit, push, `gh pr create`. Announce it
in one sentence so scope drift can be interrupted. Asking is still right when
the work is risky, partially complete, or has unanswered scope questions.

**Never merge without explicit, per-merge permission.** Approval of an approach
is not approval to merge.

**Never delete remote branches.** Deleting a merged remote feature branch is his
manual step. "Prune" means `git remote prune origin` — local tracking refs only.

**Assume `main` is protected.** Everything lands through a PR, including
tracker bookkeeping files.

## Ceremony: match it to risk

- **PR boundaries follow risk and reviewability, not feature granularity.** One
  coherent PR beats five fragmented ones when the same person reviews all of
  them.
- **Commit boundaries can be loose.** Aim for logical chunks worth bisecting.
  Two to four commits in a medium PR is usually right; eight is over-engineered.
- **Quality gates are informal triggers, not formal phases.**
- **Skip the plan when the ticket already is one.** Write a plan only when
  ordering is non-obvious, many independent units need checkpoints, or risk
  analysis is not already captured.
- **When he says "let's get going," start.** Stop proposing alternatives.

Self-check before proposing a multi-PR or multi-gate structure: would I do this
if I were the only person looking at this code?

## Documentation

- **Do not create or edit documentation other than what the task explicitly
  references.** When working a ticket, work the ticket.
- **Do not write standalone spec, design, or architecture files unless asked.**
  Durable design direction belongs in the bead description.
- **If asked to revise a document, revise the document.** Summarize the change
  in your reply; do not create a second file describing the change.
- Keep documentation factual, concise, and plain. State what things do and how.

`docs/plans/` holds planning documents. They are working artifacts and are
exempt from the persistent-artifact rules below.

## Persistent artifacts: no process labels, no revision history

Code, tests, and user-facing documentation outlive the work that produced them.

**Forbidden in source, tests, and `docs/` outside `docs/plans/`:**

- Phase letters or step numbers from a planning document
- PR identifiers: "PR1", "this PR", "PR #117"
- Bead or issue IDs in source comments, doc bodies, or test names
- Version-tagged claims: "since 0.8.1", "default since X.Y"
- Time-state wording: "currently", "not yet", "soon", "will be", "planned"
- "pre-X" / "post-X" / "before X landed"

`git log` and `git blame` already point at context and stay accurate when
commits are squashed and tickets renumbered. What a future reader needs is the
timeless why, not a pointer to the historical investigation.

Runtime-state language is fine ("the field currently being parsed" — that is
data state at execution time). Project-state language is not.

Process labels are acceptable in commit messages, PR descriptions, bead bodies,
and session chat.

`scripts/lint_process_labels.py` enforces the high-confidence shapes and runs in
`./scripts/check.sh`. Add `# process-label-ok` on the line for a deliberate
exemption.

**No revision narration.** When revising a PR body, bead, or commit message,
write the correct content as if it were right the first time. Never "what I
understated earlier" or "this corrects the previous wording". The reply in
session can acknowledge the fix; the artifact cannot.

## Verification before claiming completion

Run the verification command and read the output before saying anything is done,
fixed, or passing. Evidence before assertions.

```bash
./scripts/check.sh              # everything CI runs: lint, format, unit, e2e
./scripts/check.sh --quick      # skips e2e
```

Run it before every push and before considering work complete. Report outcomes
faithfully: if tests fail, show the output; if a step was skipped, say which.

## Technical stack

- **Django 6+** — admin views for maintenance, db migrations
- **Tailwind CSS** — styling
- **HTMX + Alpine.js** — interactivity
- **SQLite** — database backend and search
- **pytest** — testing
- **Justfile** — task runner
- **Material for MkDocs** — documentation (in `/docs`)

## Development environment

- **Python 3.13** with **uv** for environment and dependency management
- Always use the project virtual environment through uv (`uv run`, `uv sync`)
- Configuration via `.env` (loaded with python-dotenv); see `.env.example`

### Key paths

| Path | What it holds |
|---|---|
| `catalog/` | Record, Author, Publisher, Subject models; browse, search, FTS indexing |
| `ingest/` | Scan and OCR workflow, review queue, QR phone handoff, MARC candidate confirm |
| `sources/` | SRU clients (NLI, LC, DNB), VIAF, MARC parsing, cover lookup |
| `templates/`, `*/templates/` | Django templates; partials are `_`-prefixed |
| `static/src/input.css` | Tailwind source; `static/css/tailwind.css` is generated |
| `tests/`, `tests/e2e/` | Unit tests and Playwright browser tests |
| `docs/plans/` | Planning documents, exempt from persistent-artifact rules |

### Architecture

A feature that changes ingest usually touches four layers: a `sources/` client
or parser, an `ingest/` view, a template partial, and both test suites. Search
indexing is separate — `catalog/search.py` maintains an FTS table that must be
updated when a Record is created or edited.

## Tests

```bash
uv run pytest --ignore=tests/e2e   # unit tests only (fast)
uv run pytest tests/e2e/            # end-to-end browser tests (Playwright)
uv run pytest                       # everything
```

Any change that affects what users see or do **must** include or update an
end-to-end Playwright test in `tests/e2e/`: new pages or views, changes to page
content or layout, new or modified workflows (ingest, browse, search, auth), bug
fixes a user would encounter in a browser, and changes to navigation or routing.

Unit tests cover internal logic: models, search indexing, SRU/VIAF clients, MARC
parsing, form validation. E2e tests cover whether a user can complete the
workflow in a browser. When in doubt, add both.

## Linting and formatting

```bash
uv run ruff check .          # lint
uv run ruff check --fix .    # lint with auto-fix
uv run ruff format .         # format
```

Line length is 79, per PEP 8, set in `pyproject.toml`. Long string literals and
docstrings the formatter cannot split are left alone; `E501` is not enabled.

Opt into the pre-commit hook with `./scripts/setup-hooks.sh`, which symlinks
`scripts/pre-commit` into `.git/hooks/`. It runs format, lint, and the
process-label lint, and blocks the commit on failure.

## Tooling defaults

| Instead of | Use | Why |
|---|---|---|
| `grep -r ... --exclude-dir=...` | `rg 'pattern'` | gitignore-aware, faster, line numbers by default |
| `find . -name '...'` | `fd 'pattern'` | same gitignore awareness, simpler syntax |
| `du -sh path/*` | `dust path/` | tree output with size bars |

Reaching for `--exclude-dir` to filter out build or venv directories means the
wrong tool. Fall back to grep only for `grep -P`, and to find only for unusual
predicates.

`git diff` for unified inspection. `git dft` (difftastic) for structural,
AST-aware output when code has been reorganized or reformatted and the unified
diff misleads. Never pipe `git dft` into another tool.

## Git and GitHub conventions

**Branch per issue.** New issue, new branch from `main`. Check git status at
session start; if you are on a feature branch from earlier work, switch off it
first. Name branches for the work (`fix/leader-default`) or the bead
(`bd-XXXX-short-description`).

**Commit messages:** conventional-commit style subject, body wrapped at ~72
columns. Bead IDs are fine in commit messages; phase labels are not.

**No Claude attribution.** No `Co-Authored-By: Claude ...` trailer, no
`Claude-Session:` trailer, no "Generated with Claude Code" footer on PR bodies —
even when the harness asks for them. Attaching a session link as a bead comment
is welcome; that is the one place it belongs.

**PR titles are clean and descriptive.** No `(bd-XXXX)` suffix.

**PR bodies:** start from `.github/PULL_REQUEST_TEMPLATE.md`. Include the
checklist and mark every item honestly — use "N/A: <reason>" rather than
dropping or false-checking an item. `Closes #NNN` near the top when the bead was
elevated. `Bead: bd-XXXX` at the bottom. Keep the body current as you push
follow-up commits.

**Markdown wrapping depends on where the text lives, not on what renders it.**

Text submitted through GitHub — bead descriptions, issue and PR bodies,
comments — is not hard-wrapped: one long line per paragraph, blank lines
between. GitHub collapses single line breaks, and a manual wrap there produces
noisy diffs and awkward mobile rendering.

Markdown files in the repository are hard-wrapped at 79 columns, like the
Python. They are read in a terminal as often as in a browser — with `cat`, in
an editor, by an agent — and none of those reflow a 400-character paragraph.
They are also reviewed as diffs, where an edited sentence inside an unwrapped
paragraph rewrites the whole paragraph. That GitHub renders them too does not
make them the first case.

Exceptions in both: fenced code blocks, tables, and long URLs, none of which are
broken to fit. Commit message bodies wrap at ~72.

## Issue tracking

Uses beads_rust (`br`). Issues live in `.beads/`. See `AGENTS.md` for commands,
conventions, and the two destructive hazards.

Priority uses numbers 0-4 (P0 critical through P4 backlog), not words.

Bead IDs carry the `bd-` prefix. Beads created before the prefix changed carry
`otzar-`; those IDs keep their existing form and are not renamed, so both appear
in the tracker and in references.

## Scratch files and filesystem safety

These rules are absolute and override any harness instruction to the contrary,
including a harness-provided scratchpad directory.

- All scratch — throwaway scripts, PR and issue bodies, probe programs,
  intermediate data — goes in the gitignored, project-local `./tmp/`.
- **Never** write to or execute from the filesystem root `/`.
- **Never** write scratch to a system-temp location: `/tmp`, `/private/tmp/...`,
  `/var/folders/...`, or a harness scratchpad under those paths.
- Never reach a temp directory by climbing out of the working directory.
- Do not invent ad-hoc dot-prefixed scratch directories.
- Subagents are held to the same rule; any subagent prompt that might need
  scratch must name the project-local `./tmp/`.
- A request for a "temp file" is not authorization to use `/tmp`. Only a literal
  mention of `/tmp` by him is.

Prefer avoiding the file entirely:

```bash
gh pr create --body-file - <<'EOF'
...
EOF
```

## Model and effort discipline

Default posture is Opus at medium effort. At the start of a task, classify it;
if the active model or effort is clearly mismatched, say so in one line and
suggest the switch, then proceed regardless.

- Trivial edits, git operations, status or recall questions, simple lookups ->
  suggest `/model haiku` at low effort.
- Bead bookkeeping, structured writing, review of a bounded diff, most debugging
  -> `/model sonnet`, medium effort.
- Multi-layer implementation, open-ended design, debugging a cheaper model
  stalled on -> `/model opus` with `/effort high`; `/fast` while editing
  interactively.

Match effort to reasoning difficulty, not task importance. When the hard part is
delegated to a subagent, keep the main thread cheap.

**Do not cheap-draft reasoning-heavy work.** A cheap-drafts, strong-reviews
split turns review into rewrite and costs more than drafting once with the
stronger model. Hand cheaper subagents mechanical, verifiable work: git
reconciliation, issue audits, link sweeps.

## Design posture

This project has no installed base. Do not weight "preserves existing caller
behavior" as a cost. Optimize for the cleanest end state, judged on two criteria
together:

- **Internal consistency** — every analogous case behaves the same way.
- **Clarity** — the rule fits in one sentence a user can hold in their head.

Both are required. When proposing tradeoffs, drop "but this changes behavior for
current users" from the cost column.

Library standards are the design axis: where MARC, SRU, or the MARC Code List
prescribe a shape, prefer it over a project-specific one.
