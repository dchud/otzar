"""Git identity of the checkout the site is running from.

The footer names the commit the running process was started from, so a
bug report can be tied to code rather than to a date. The value cannot
change while the process lives, so it is resolved once, at startup, and
never inside a request.

A container image carries no git metadata: ``.dockerignore`` leaves
``.git`` out of the build. The image build passes the commit it was
built from as ``GIT_COMMIT``, and that is read before git is asked.

A tree with neither -- an image built without the argument, a source
tarball -- has nothing to report and reports nothing. Showing an
approximate commit would be worse than showing none.
"""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

GITHUB_URL = "https://github.com/dchud/otzar"

# Naming this branch in the footer would carry no information: it is
# where the deployable code lives. Any other branch is worth seeing.
DEFAULT_BRANCH = "main"

_TIMEOUT_SECONDS = 5

# The length git abbreviates a checkout's commit to, applied to
# GIT_COMMIT too so the footer shows the same form either way.
_SHORT_LENGTH = 7

_COMMIT_PATTERN = re.compile(r"[0-9a-f]{7,40}")


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


def from_environment(environ=os.environ) -> BuildInfo | None:
    """Return the commit named by ``GIT_COMMIT``, if it names one.

    A value that is not a hexadecimal commit is ignored rather than
    shown: the footer turns it into a link, and a link to a commit that
    does not exist is the approximate answer this module avoids.
    """
    value = environ.get("GIT_COMMIT", "").strip().lower()
    if not _COMMIT_PATTERN.fullmatch(value):
        return None
    return BuildInfo(commit=value[:_SHORT_LENGTH])


def resolve(root: Path | str, environ=os.environ) -> BuildInfo | None:
    """Read the git identity of the running code.

    ``GIT_COMMIT`` in *environ* is used when it is set; otherwise the
    checkout at *root* is asked. Returns None when neither answers.
    """
    from_env = from_environment(environ)
    if from_env is not None:
        return from_env

    root = Path(root)
    # git searches upwards for a repository. Without this check, a source
    # tree unpacked inside an unrelated checkout would report that
    # repository's commit as its own.
    if not (root / ".git").exists():
        return None

    commit = _git(root, "rev-parse", f"--short={_SHORT_LENGTH}", "HEAD")
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
