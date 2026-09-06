#!/usr/bin/env bash
# Pre-push check. Runs what CI runs, in the same order.
#
#   ./scripts/check.sh           everything
#   ./scripts/check.sh --quick   skips the e2e suite
set -euo pipefail

cd "$(dirname "$0")/.."

QUICK=0
[[ "${1:-}" == "--quick" ]] && QUICK=1

step() { printf '\n=== %s ===\n' "$1"; }

step "format"
uv run ruff format --check .

step "lint"
uv run ruff check .

step "process labels"
uv run python scripts/lint_process_labels.py

# The stylesheet is generated from the templates, not committed, so it
# has to be built before anything renders a page. Both suites depend on
# it: a unit test asserts the stylesheet URL carries a cache-busting
# stamp, which needs the file on disk, and the browser tests would
# otherwise run against an unstyled application and mostly pass.
# `--force` because the command's own freshness check watches only the
# source CSS, never the templates it scans for classes.
step "stylesheet"
uv run python manage.py tailwind build --force

step "unit tests"
uv run pytest --ignore=tests/e2e -q

if [[ $QUICK -eq 1 ]]; then
    printf '\nAll checks passed (e2e skipped).\n'
    exit 0
fi

step "e2e tests"
uv run pytest tests/e2e/ -q

printf '\nAll checks passed.\n'
