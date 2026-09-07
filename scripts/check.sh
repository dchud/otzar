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

# The regular persona is the default and reports only findings with a
# minimal false-positive rate. The pedantic persona reports the same
# findings against this repository's workflows -- it adds nothing here
# -- so there is no case for the noisier set.
step "workflow lint"
uv run zizmor .github/workflows/

# `--strict` turns MkDocs warnings into failures, which is what CI does.
# It catches a link to a file that is not in the built site: a page that
# was renamed, or one whose target is present on disk but excluded from
# the repository, where a local build succeeds and CI does not. This runs
# in the quick pass too, since a documentation-only change reaches no
# other gate here.
step "docs"
uv run mkdocs build --strict

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
