"""End-to-end tests for the repository link and build indicator."""

import pytest
from playwright.sync_api import expect

from otzar.build_info import GITHUB_URL, BuildInfo

REPO_LINK = "otzar on GitHub, opens in a new tab"


@pytest.mark.django_db(transaction=True)
class TestRepositoryLink:
    def test_header_links_to_the_repository(self, page, live_server):
        page.goto(live_server.url)

        link = page.get_by_role("link", name=REPO_LINK)
        expect(link).to_have_attribute("href", GITHUB_URL)
        expect(link).to_have_attribute("target", "_blank")
        expect(link).to_have_attribute("rel", "noopener")

    def test_the_mark_is_inline_svg(self, page, live_server):
        page.goto(live_server.url)

        mark = page.get_by_role("link", name=REPO_LINK).locator("svg")
        expect(mark).to_have_count(1)
        assert mark.get_attribute("aria-hidden") == "true"

    def test_the_link_meets_the_touch_target_size(self, page, live_server):
        page.goto(live_server.url)

        box = page.get_by_role("link", name=REPO_LINK).bounding_box()

        assert box["height"] >= 44
        assert box["width"] >= 44

    def test_the_link_appears_on_every_page(
        self, page, live_server, sample_record
    ):
        for path in ["/", "/browse/", "/search/"]:
            page.goto(f"{live_server.url}{path}")
            expect(page.get_by_role("link", name=REPO_LINK)).to_be_visible()


@pytest.mark.django_db(transaction=True)
class TestBuildIndicator:
    def test_footer_links_the_commit_to_github(
        self, page, live_server, settings
    ):
        settings.BUILD_INFO = BuildInfo(
            commit="abc1234", branch="fix/leader-default", version="v0.1.0"
        )

        page.goto(live_server.url)

        commit = page.locator('footer a[href$="/commit/abc1234"]')
        expect(commit).to_have_text("abc1234")
        expect(commit).to_have_attribute("target", "_blank")
        expect(page.locator("footer")).to_contain_text(
            "branch fix/leader-default"
        )
        expect(page.locator("footer")).to_contain_text("version v0.1.0")

    def test_footer_omits_an_absent_branch_and_version(
        self, page, live_server, settings
    ):
        settings.BUILD_INFO = BuildInfo(commit="abc1234")

        page.goto(live_server.url)

        footer = page.locator("footer")
        expect(footer).to_contain_text("abc1234")
        expect(footer).not_to_contain_text("branch")
        expect(footer).not_to_contain_text("version")

    def test_footer_renders_without_git_metadata(
        self, page, live_server, settings
    ):
        """A tree with no git metadata shows a footer and no commit."""
        settings.BUILD_INFO = None
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto(live_server.url)

        expect(page.locator("footer")).to_contain_text("otzar")
        expect(page.locator('footer a[href*="/commit/"]')).to_have_count(0)
        expect(page.get_by_role("link", name=REPO_LINK)).to_be_visible()
        assert errors == [], f"Console errors in the footer: {errors}"
