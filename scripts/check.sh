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

step "unit tests"
uv run pytest --ignore=tests/e2e -q

if [[ $QUICK -eq 1 ]]; then
    printf '\nAll checks passed (e2e skipped).\n'
    exit 0
fi

step "e2e tests"
uv run pytest tests/e2e/ -q

printf '\nAll checks passed.\n'
