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

<!-- br-agent-instructions-v1 -->

---

## Beads Workflow Integration

This project uses [beads_rust](https://github.com/Dicklesworthstone/beads_rust) (`br`/`bd`) for issue tracking. Issues are stored in `.beads/` and tracked in git.

### Essential Commands

```bash
# View ready issues (unblocked, not deferred)
br ready              # or: bd ready

# List and search
br list --status=open # All open issues
br show <id>          # Full issue details with dependencies
br search "keyword"   # Full-text search

# Create and update
br create --title="..." --description="..." --type=task --priority=2
br update <id> --status=in_progress
br close <id> --reason="Completed"
br close <id1> <id2>  # Close multiple issues at once

# Sync with git
br sync --flush-only  # Export DB to JSONL
br sync --status      # Check sync status
```

### Workflow Pattern

1. **Start**: Run `br ready` to find actionable work
2. **Claim**: Use `br update <id> --status=in_progress`
3. **Work**: Implement the task
4. **Complete**: Use `br close <id>`
5. **Sync**: Always run `br sync --flush-only` at session end

### Key Concepts

- **Dependencies**: Issues can block other issues. `br ready` shows only unblocked work.
- **Priority**: P0=critical, P1=high, P2=medium, P3=low, P4=backlog (use numbers 0-4, not words)
- **Types**: task, bug, feature, epic, chore, docs, question
- **Blocking**: `br dep add <issue> <depends-on>` to add dependencies

### Session Protocol

**Before ending any session, run this checklist:**

```bash
git status              # Check what changed
git add <files>         # Stage code changes
br sync --flush-only    # Export beads changes to JSONL
git commit -m "..."     # Commit everything
git push                # Push to remote
```

### Best Practices

- Check `br ready` at session start to find available work
- Update status as you work (in_progress → closed)
- Create new issues with `br create` when you discover tasks
- Use descriptive titles and set appropriate priority/type
- Always sync before ending session

<!-- end-br-agent-instructions -->
