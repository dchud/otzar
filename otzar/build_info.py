"""Git identity of the checkout the site is running from.

The footer names the commit the running process was started from, so a
bug report can be tied to code rather than to a date. The value cannot
change while the process lives, so it is resolved once, at startup, and
never inside a request.

A tree with no git metadata -- an image built from an export, a source
tarball -- has nothing to report and reports nothing. Showing an
approximate commit would be worse than showing none.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

GITHUB_URL = "https://github.com/dchud/otzar"

# Naming this branch in the footer would carry no information: it is
# where the deployable code lives. Any other branch is worth seeing.
DEFAULT_BRANCH = "main"

_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class BuildInfo:
    """Git identity of a checkout, as the footer shows it."""

    commit: str
    branch: str | None = None
    version: str | None = None

    @property
    def commit_url(self) -> str:
        return f"{GITHUB_URL}/commit/{self.commit}"


def _git(root: Path, *args: str) -> str | None:
    """Return the stripped stdout of a git command run against *root*.

    Returns None for every failure -- git missing, the command failing,
    empty output -- because the caller treats them all the same way.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def resolve(root: Path | str) -> BuildInfo | None:
    """Read the git identity of the checkout at *root*.

    Returns None when *root* is not a checkout or git cannot answer.
    """
    root = Path(root)
    # git searches upwards for a repository. Without this check, a source
    # tree unpacked inside an unrelated checkout would report that
    # repository's commit as its own.
    if not (root / ".git").exists():
        return None

    commit = _git(root, "rev-parse", "--short=7", "HEAD")
    if not commit:
        return None

    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    # A detached HEAD answers "HEAD", which names nothing a reader can
    # use; the commit already says where the code came from.
    if branch in (DEFAULT_BRANCH, "HEAD"):
        branch = None

    # Without --always this fails when no tag is reachable, which is the
    # answer wanted: an untagged checkout has no version to show.
    version = _git(root, "describe", "--tags")

    return BuildInfo(commit=commit, branch=branch, version=version)
