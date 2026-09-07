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
class TestHeaderSearch:
    """The header carries its own search box, not just a link to
    /search/, so a query can be sent from wherever a reader lands."""

    def _search_box(self, page):
        return page.locator("header").get_by_label("Search the catalog")

    def test_search_box_is_present_on_every_page(
        self, page, live_server, sample_record
    ):
        for path in ["/", "/browse/", "/search/"]:
            page.goto(f"{live_server.url}{path}")
            expect(self._search_box(page)).to_be_visible()

    def test_search_box_meets_the_touch_target_size(self, page, live_server):
        page.goto(live_server.url)

        box = self._search_box(page).bounding_box()

        assert box["height"] >= 44

    def test_search_box_does_not_assume_left_to_right_input(
        self, page, live_server
    ):
        page.goto(live_server.url)

        expect(self._search_box(page)).to_have_attribute("dir", "auto")

    def test_submitting_from_the_home_page_header_lands_on_results(
        self, page, live_server, sample_record
    ):
        page.goto(live_server.url)

        self._search_box(page).fill("social life")
        self._search_box(page).press("Enter")

        expect(page).to_have_url(f"{live_server.url}/search/?q=social+life")
        expect(
            page.locator("text=The social life of information")
        ).to_be_visible()

    def test_search_box_is_reachable_at_phone_width(self, page, live_server):
        """base.html hides the Home/Browse/Ingest links below sm with
        no menu to reveal them again, so the search box does not live
        inside that same hidden block -- it stays visible here too."""
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(live_server.url)

        expect(self._search_box(page)).to_be_visible()

        # Not scrollWidth minus clientWidth. clientWidth excludes a
        # vertical scrollbar, and whether one takes layout width is a
        # property of the platform rather than of the page: Windows and
        # Linux draw a classic scrollbar that does, macOS, iOS and
        # Android draw an overlay one that does not. That subtraction
        # therefore reports which machine ran the test.
        #
        # Ask the layout instead. Any element whose right edge falls
        # outside the content box is real overflow on every platform,
        # and naming it is more use than a pixel count.
        offenders = page.evaluate("""() => {
            const limit = document.documentElement.clientWidth;
            return [...document.querySelectorAll('body *')]
                .map(el => ({el, r: el.getBoundingClientRect()}))
                .filter(({r}) => r.width > 0 && r.right > limit + 1)
                .map(({el, r}) => `${el.tagName.toLowerCase()}`
                    + `.${(el.className || '').toString().split(' ')[0]}`
                    + ` right=${Math.round(r.right)} limit=${limit}`)
                .slice(0, 5);
        }""")
        assert not offenders, (
            "content extends past the viewport: " + "; ".join(offenders)
        )


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
