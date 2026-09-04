"""Tests for the git identity the footer reports."""

import subprocess

import pytest

from otzar import build_info
from otzar.context_processors import site_chrome


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A checkout with one commit on the default branch."""
    root = tmp_path / "checkout"
    root.mkdir()
    git(root, "init", "-q", "-b", build_info.DEFAULT_BRANCH)
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    git(root, "commit", "-q", "--allow-empty", "-m", "first")
    return root


def test_reports_the_short_head_commit(repo):
    info = build_info.resolve(repo)

    assert info is not None
    assert info.commit == git(repo, "rev-parse", "HEAD")[:7]


def test_default_branch_is_not_named(repo):
    """Every deployable commit comes from it, so naming it says nothing."""
    assert build_info.resolve(repo).branch is None


def test_other_branches_are_named(repo):
    git(repo, "checkout", "-q", "-b", "fix/leader-default")

    assert build_info.resolve(repo).branch == "fix/leader-default"


def test_detached_head_names_no_branch(repo):
    git(repo, "checkout", "-q", "--detach")

    assert build_info.resolve(repo).branch is None


def test_untagged_checkout_has_no_version(repo):
    assert build_info.resolve(repo).version is None


def test_a_reachable_tag_becomes_the_version(repo):
    git(repo, "tag", "v0.1.0")

    assert build_info.resolve(repo).version == "v0.1.0"


def test_commit_links_to_the_commit_on_github(repo):
    info = build_info.resolve(repo)

    assert info.commit_url == (
        f"https://github.com/dchud/otzar/commit/{info.commit}"
    )


def test_tree_without_git_metadata_reports_nothing(tmp_path):
    export = tmp_path / "export"
    export.mkdir()

    assert build_info.resolve(export) is None


def test_tree_inside_another_checkout_reports_nothing(repo):
    """An unpacked tree is not the repository it happens to sit in."""
    unpacked = repo / "unpacked"
    unpacked.mkdir()

    assert build_info.resolve(unpacked) is None


def test_missing_git_command_reports_nothing(repo, monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(build_info.subprocess, "run", no_git)

    assert build_info.resolve(repo) is None


def test_slow_git_reports_nothing(repo, monkeypatch):
    def hangs(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=5)

    monkeypatch.setattr(build_info.subprocess, "run", hangs)

    assert build_info.resolve(repo) is None


def test_context_carries_the_repository_url(settings):
    settings.BUILD_INFO = None

    context = site_chrome(request=None)

    assert context["github_url"] == "https://github.com/dchud/otzar"
    assert context["build_info"] is None


def test_context_carries_the_build_resolved_at_startup(settings):
    settings.BUILD_INFO = build_info.BuildInfo(commit="abc1234")

    assert site_chrome(request=None)["build_info"].commit == "abc1234"
