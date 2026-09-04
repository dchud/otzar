#!/usr/bin/env python3
"""Fail on process labels in artifacts that outlive the work.

Code, tests and user-facing docs get read long after the branch that
produced them is gone. A bead ID or a PR number in them points at
context that git history already carries and keeps more accurately,
and it goes stale the moment a ticket is renumbered or a commit is
squashed.

Only high-confidence shapes are checked. Bare issue numbers are not:
this catalog is full of MARC field references (245, 650, 880) that a
`#NNN` rule would flag constantly. Bare version numbers and the word
"phase" are not checked either, for the same reason.

Put `process-label-ok` in a comment on the line to exempt it.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Planning documents are working artifacts; they are allowed to name
# beads, PRs and the order work happens in. Generated and vendored
# trees are not ours to lint.
EXCLUDED_DIRS = {
    ".beads",
    ".git",
    ".venv",
    ".django_tailwind_cli",
    ".playwright-mcp",
    "__pycache__",
    "migrations",
    "node_modules",
    "staticfiles",
    "tmp",
}
EXCLUDED_PATHS = {
    Path("docs/plans"),
    Path("static/css/tailwind.css"),
    Path("CHANGELOG.md"),
    # The instruction files define these conventions, so they have to
    # quote the shapes they forbid.
    Path("CLAUDE.md"),
    Path("AGENTS.md"),
}
SUFFIXES = {".py", ".html", ".md", ".css", ".js", ".yml", ".yaml", ".toml"}

EXEMPTION = "process-label-ok"

CHECKS = [
    (
        re.compile(r"\bbd-[a-z0-9]{3,}\b", re.I),
        "bead ID",
    ),
    (
        re.compile(r"\bPR\s*#\s*\d+|\bPR\d+\b|\bthis PR\b", re.I),
        "PR reference",
    ),
    (
        re.compile(
            r"\b(?:since|as of|flipped in|changed in|default since)\s+"
            r"v?\d+\.\d+",
            re.I,
        ),
        "version-tagged claim",
    ),
    (
        re.compile(r"\b(?:pre|post)-(?:PR|release|merge|migration)\b", re.I),
        "stage-relative wording",
    ),
]


def candidate_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        rel = path.relative_to(ROOT)
        if EXCLUDED_DIRS & set(rel.parts):
            continue
        if any(
            rel == excluded or excluded in rel.parents
            for excluded in EXCLUDED_PATHS
        ):
            continue
        yield path, rel


def main():
    failures = []
    for path, rel in candidate_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, start=1):
            if EXEMPTION in line:
                continue
            for pattern, label in CHECKS:
                match = pattern.search(line)
                if match:
                    failures.append(
                        f"{rel}:{number}: {label} {match.group(0).strip()!r}"
                    )

    if failures:
        print("Process labels found in persistent artifacts:\n")
        for failure in failures:
            print(f"  {failure}")
        print(
            f"\n{len(failures)} finding(s). These belong in commit "
            "messages, PR bodies or bead descriptions, not in code, "
            "tests or user-facing docs."
        )
        print(f"Add a '{EXEMPTION}' comment on the line to exempt it.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
