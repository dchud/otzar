"""End-to-end tests that the compiled stylesheet reaches the browser.

Tailwind generates `static/css/tailwind.css` by scanning the templates,
so the file is a product of the tree rather than a part of it and is not
under version control. That makes an absent stylesheet a plausible state
for a checkout to be in, and the rest of this suite would barely notice:
the markup is identical either way, and its assertions are about text,
structure and class attributes. Almost all of it passes against an
unstyled application, which looks like coverage and is not.

These tests fail instead, and name the reason.
"""

from pathlib import Path

import pytest
from django.conf import settings
from playwright.sync_api import expect

STYLESHEET = Path(settings.BASE_DIR) / "static" / "css" / "tailwind.css"

MISSING = (
    f"{STYLESHEET} does not exist. It is generated from the templates, "
    "not committed. Build it with `just tailwind` (or `uv run python "
    "manage.py tailwind build`) before running the browser tests."
)

STYLESHEET_LINK = 'link[rel="stylesheet"][href^="/static/css/tailwind.css"]'


@pytest.mark.django_db(transaction=True)
class TestCompiledStylesheet:
    def test_the_build_output_exists(self):
        assert STYLESHEET.is_file(), MISSING

    def test_the_page_links_a_stamped_stylesheet(self, page, live_server):
        """The link carries the cache-busting stamp, not a bare path.

        `versioned_static` falls back to the unstamped URL when the
        finder cannot locate the file, so a bare href is the signature
        of a stylesheet that was never built.
        """
        page.goto(live_server.url)

        link = page.locator(STYLESHEET_LINK)
        expect(link).to_have_count(1)
        href = link.get_attribute("href")
        assert "?v=" in href, MISSING
        assert href.rsplit("=", 1)[1].isdigit()

    def test_the_stylesheet_is_served(self, page, live_server):
        page.goto(live_server.url)

        href = page.locator(STYLESHEET_LINK).get_attribute("href")
        response = page.request.get(f"{live_server.url}{href}")

        assert response.status == 200
        body = response.text()
        assert "tailwindcss" in body
        assert len(body) > 10_000, "The stylesheet compiled to almost nothing"

    def test_the_utilities_apply_to_the_page(self, page, live_server):
        """A class written in a template has to take effect in a browser.

        The body carries Tailwind's own utilities, so a transparent
        background means the stylesheet did not load, and a non-zero
        margin means its base layer did not.
        """
        page.goto(live_server.url)

        style = page.evaluate(
            "() => {"
            "  const s = getComputedStyle(document.body);"
            "  return {background: s.backgroundColor, margin: s.marginTop};"
            "}"
        )

        assert style["background"] != "rgba(0, 0, 0, 0)"
        assert style["margin"] == "0px"
