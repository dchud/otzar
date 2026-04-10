from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def user(db):
    return User.objects.create_user(username="cataloger", password="testpass123")


@pytest.fixture
def client_logged_in(user):
    c = Client()
    c.login(username="cataloger", password="testpass123")
    return c


MOCK_RESULTS = {
    "nli_records": [
        {
            "title": "Test Book",
            "title_alternate": "ספר מבחן",
            "author": "Test Author",
            "author_alternate": None,
            "publisher": "Test Press",
            "place": "Jerusalem",
            "date": "2020",
            "language": "heb",
            "isbn": "9781234567890",
            "subjects": ["Testing"],
            "series_title": None,
            "series_volume": None,
        }
    ],
    "lc_records": [
        {
            "title": "Test Book (LC)",
            "title_alternate": None,
            "author": "Test Author",
            "author_alternate": None,
            "publisher": "LC Press",
            "place": "Washington",
            "date": "2020",
            "language": "eng",
            "isbn": "9781234567890",
            "subjects": [],
            "series_title": None,
            "series_volume": None,
        }
    ],
    "dnb_records": [
        {
            "title": "Test Book (DNB)",
            "title_alternate": None,
            "author": "Test Author",
            "author_alternate": None,
            "publisher": "DNB Verlag",
            "place": "Frankfurt",
            "date": "2020",
            "language": "ger",
            "isbn": "9781234567890",
            "subjects": [],
            "series_title": None,
            "series_volume": None,
        }
    ],
}


@pytest.mark.django_db
class TestIsbnScan:
    def test_requires_login(self, client):
        response = client.get("/ingest/scan/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_page_loads(self, client_logged_in):
        response = client_logged_in.get("/ingest/scan/")
        assert response.status_code == 200
        assert b"Scan ISBN" in response.content
        assert b"isbn-input" in response.content


@pytest.mark.django_db
class TestIsbnLookup:
    def test_requires_login(self, client):
        response = client.post("/ingest/isbn-lookup/", {"isbn": "9781234567890"})
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_get_not_allowed(self, client_logged_in):
        response = client_logged_in.get("/ingest/isbn-lookup/")
        assert response.status_code == 405

    def test_empty_isbn(self, client_logged_in):
        response = client_logged_in.post("/ingest/isbn-lookup/", {"isbn": ""})
        assert response.status_code == 200
        assert b"Please enter an ISBN" in response.content

    @patch("ingest.views.isbn_lookup")
    def test_returns_candidates(self, mock_lookup, client_logged_in):
        mock_lookup.return_value = MOCK_RESULTS
        response = client_logged_in.post(
            "/ingest/isbn-lookup/", {"isbn": "9781234567890"}
        )
        assert response.status_code == 200
        assert b"Test Book" in response.content
        assert b"Test Book (LC)" in response.content
        assert b"Test Book (DNB)" in response.content
        assert b"NLI" in response.content
        assert b"LC" in response.content
        assert b"DNB" in response.content
        assert b"Use this record" in response.content
        mock_lookup.assert_called_once_with("9781234567890")

    @patch("ingest.views.isbn_lookup")
    def test_no_results(self, mock_lookup, client_logged_in):
        mock_lookup.return_value = {
            "nli_records": [],
            "lc_records": [],
            "dnb_records": [],
        }
        response = client_logged_in.post("/ingest/isbn-lookup/", {"isbn": "0000000000"})
        assert response.status_code == 200
        assert b"No records found" in response.content

    @patch("ingest.views.isbn_lookup")
    def test_handles_error(self, mock_lookup, client_logged_in):
        mock_lookup.side_effect = Exception("Connection timeout")
        response = client_logged_in.post(
            "/ingest/isbn-lookup/", {"isbn": "9781234567890"}
        )
        assert response.status_code == 200
        assert b"error occurred" in response.content
