"""Tests for the versioned static URL tag."""

from django.template import Context, Template


def render(path):
    return Template(
        "{% load static_version %}{% versioned_static '" + path + "' %}"
    ).render(Context({}))


def test_url_carries_a_version_stamp():
    """A rebuilt stylesheet must not be served from a stale cache."""
    url = render("css/tailwind.css")
    assert url.startswith("/static/css/tailwind.css?v=")
    assert url.rsplit("=", 1)[1].isdigit()


def test_stamp_follows_the_file(tmp_path, settings):
    """Touching the file changes the URL."""
    asset = tmp_path / "probe.css"
    asset.write_text("body{}")
    settings.STATICFILES_DIRS = [str(tmp_path)]

    first = render("probe.css")
    import os

    os.utime(asset, (1_700_000_000, 1_700_000_000))
    second = render("probe.css")

    assert first != second
    assert second.endswith("?v=1700000000")


def test_missing_file_falls_back_to_the_plain_url():
    assert render("css/does-not-exist.css") == "/static/css/does-not-exist.css"
