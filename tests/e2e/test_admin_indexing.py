"""End-to-end tests for admin edits reaching the search index."""

import pytest
from django.contrib.auth.models import User
from playwright.sync_api import expect

from catalog.models import Author, Record
from catalog.search import ensure_fts_table, index_record
from tests.e2e.conftest import login


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="testadmin", password="testpass123", email="a@example.com"
    )


@pytest.fixture
def indexed_record(db, admin_user):
    ensure_fts_table()
    author = Author.objects.create(name="Halevi, Yehudah")
    record = Record.objects.create(title="Sefer ha-Kuzari")
    record.authors.add(author)
    index_record(record)
    return record


@pytest.mark.django_db(transaction=True)
class TestAdminEditsReachSearch:
    """A cataloger fixing a record in the admin expects search to agree.

    Search reads a separate index rather than the records themselves,
    so an admin edit that stops at the database leaves the catalog
    findable only under text it no longer holds, with nothing on either
    page to say so.
    """

    def test_a_retitled_record_is_found_under_its_new_title(
        self, page, live_server, indexed_record
    ):
        login(page, live_server)
        page.goto(
            f"{live_server.url}/admin/catalog/record/"
            f"{indexed_record.pk}/change/"
        )
        page.fill("#id_title", "Sefer ha-Zohar")
        page.click('input[name="_save"]')
        page.wait_for_url(f"{live_server.url}/admin/catalog/record/")

        page.goto(f"{live_server.url}/search/?q=Zohar")
        expect(page.locator("text=Sefer ha-Zohar")).to_be_visible()

        page.goto(f"{live_server.url}/search/?q=Kuzari")
        expect(page.locator("text=No results")).to_be_visible()

    def test_a_renamed_author_is_searchable_on_their_records(
        self, page, live_server, indexed_record
    ):
        author = indexed_record.authors.first()
        login(page, live_server)
        page.goto(
            f"{live_server.url}/admin/catalog/author/{author.pk}/change/"
        )
        page.fill("#id_name", "Judah Halevi")
        page.click('input[name="_save"]')
        page.wait_for_url(f"{live_server.url}/admin/catalog/author/")

        page.goto(f"{live_server.url}/search/?q=Judah")
        expect(page.locator("text=Sefer ha-Kuzari")).to_be_visible()
