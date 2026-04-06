import pytest
from django.test import Client

from catalog.models import Author, Record
from catalog.search import ensure_fts_table, index_record


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def fts_index():
    ensure_fts_table()


@pytest.mark.django_db
class TestCatalogSearchView:
    def test_search_page_loads(self, client):
        """GET /search/ returns 200 with the search form."""
        response = client.get("/search/")
        assert response.status_code == 200
        assert b"Search the Catalog" in response.content

    def test_empty_query_shows_form_only(self, client):
        """Empty query shows search form without results section."""
        response = client.get("/search/?q=")
        assert response.status_code == 200
        assert b"Search the Catalog" in response.content
        assert b"result" not in response.content.lower()

    def test_search_with_results(self, client, fts_index):
        """Search with matching query returns results."""
        record = Record.objects.create(
            title="Mishneh Torah", title_romanized="Mishneh Torah"
        )
        author = Author.objects.create(name="Maimonides")
        record.authors.add(author)
        index_record(record)

        response = client.get("/search/?q=Mishneh")
        assert response.status_code == 200
        content = response.content.decode()
        assert "1 result" in content
        assert "Mishneh Torah" in content
        assert record.record_id in content

    def test_search_no_matches(self, client, fts_index):
        """Search with no matches shows 'no results' message."""
        response = client.get("/search/?q=xyznonexistent")
        assert response.status_code == 200
        content = response.content.decode()
        assert "No results found" in content
        assert "xyznonexistent" in content

    def test_search_hebrew_title(self, client, fts_index):
        """Search finds records by Hebrew title."""
        record = Record.objects.create(
            title="\u05de\u05e9\u05e0\u05d4 \u05ea\u05d5\u05e8\u05d4"
        )
        index_record(record)

        response = client.get("/search/?q=\u05de\u05e9\u05e0\u05d4")
        assert response.status_code == 200
        content = response.content.decode()
        assert "1 result" in content

    def test_search_by_author(self, client, fts_index):
        """Search finds records by author name."""
        record = Record.objects.create(title="Guide for the Perplexed")
        author = Author.objects.create(
            name="\u05e8\u05de\u05d1\u05dd", name_romanized="Maimonides"
        )
        record.authors.add(author)
        index_record(record)

        response = client.get("/search/?q=Maimonides")
        assert response.status_code == 200
        content = response.content.decode()
        assert "1 result" in content
        assert "Guide for the Perplexed" in content

    def test_multiple_results(self, client, fts_index):
        """Search returning multiple results shows correct count."""
        for i in range(3):
            record = Record.objects.create(title=f"Torah volume {i}")
            index_record(record)

        response = client.get("/search/?q=Torah")
        assert response.status_code == 200
        content = response.content.decode()
        assert "3 results" in content
