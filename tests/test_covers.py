"""Tests for the Open Library Covers API client."""

from io import StringIO
from unittest.mock import MagicMock, patch

import httpx
import pytest

from sources.covers import fetch_cover_url


@pytest.fixture
def record_with_ids(db):
    """Create a Record with ISBN, OCLC, and LCCN identifiers."""
    from catalog.models import ExternalIdentifier, Record

    record = Record(title="Test Book")
    record.save()
    ExternalIdentifier.objects.create(
        record=record, identifier_type="ISBN", value="9780123456789"
    )
    ExternalIdentifier.objects.create(
        record=record, identifier_type="OCLC", value="12345678"
    )
    ExternalIdentifier.objects.create(
        record=record, identifier_type="LCCN", value="2020123456"
    )
    return record


@pytest.fixture
def record_no_ids(db):
    """Create a Record with no external identifiers."""
    from catalog.models import Record

    record = Record(title="No IDs Book")
    record.save()
    return record


def _mock_head_response(content_length):
    """Create a mock httpx response with a given Content-Length."""
    resp = MagicMock()
    resp.headers = {"content-length": str(content_length)}
    return resp


class TestFetchCoverUrl:
    @patch("sources.covers.httpx.head")
    def test_isbn_found(self, mock_head, record_with_ids):
        """ISBN lookup returns a valid cover (Content-Length > threshold)."""
        mock_head.return_value = _mock_head_response(5000)

        result = fetch_cover_url(record_with_ids)

        assert result == "https://covers.openlibrary.org/b/isbn/9780123456789-M.jpg"
        assert mock_head.call_count == 1

    @patch("sources.covers.httpx.head")
    def test_isbn_placeholder_falls_through_to_oclc(self, mock_head, record_with_ids):
        """ISBN returns 1x1 pixel, OCLC returns a real cover."""
        mock_head.side_effect = [
            _mock_head_response(43),  # ISBN: placeholder
            _mock_head_response(8000),  # OCLC: real cover
        ]

        result = fetch_cover_url(record_with_ids)

        assert result == "https://covers.openlibrary.org/b/oclc/12345678-M.jpg"
        assert mock_head.call_count == 2

    @patch("sources.covers.httpx.head")
    def test_all_placeholders_returns_empty(self, mock_head, record_with_ids):
        """All identifiers return 1x1 pixel placeholder."""
        mock_head.return_value = _mock_head_response(43)

        result = fetch_cover_url(record_with_ids)

        assert result == ""
        assert mock_head.call_count == 3  # ISBN, OCLC, LCCN

    def test_no_identifiers_returns_empty(self, record_no_ids):
        """Record with no identifiers returns empty string immediately."""
        result = fetch_cover_url(record_no_ids)
        assert result == ""

    @patch("sources.covers.httpx.head")
    def test_timeout_returns_empty(self, mock_head, record_with_ids):
        """HTTP timeout is handled gracefully, returns empty string."""
        mock_head.side_effect = httpx.TimeoutException("timed out")

        result = fetch_cover_url(record_with_ids)

        assert result == ""

    @patch("sources.covers.httpx.head")
    def test_timeout_on_isbn_tries_oclc(self, mock_head, record_with_ids):
        """Timeout on ISBN still tries OCLC."""
        mock_head.side_effect = [
            httpx.TimeoutException("timed out"),  # ISBN
            _mock_head_response(5000),  # OCLC
        ]

        result = fetch_cover_url(record_with_ids)

        assert result == "https://covers.openlibrary.org/b/oclc/12345678-M.jpg"


class TestFetchCoversCommand:
    @patch("sources.covers.httpx.head")
    def test_dry_run(self, mock_head, record_with_ids):
        """Dry run lists records without making HTTP requests."""
        from django.core.management import call_command

        out = StringIO()
        call_command("fetch_covers", "--dry-run", stdout=out)

        output = out.getvalue()
        assert "Dry run" in output
        assert record_with_ids.record_id in output
        mock_head.assert_not_called()

    @patch("sources.covers.httpx.head")
    @patch("sources.covers.time.sleep")
    def test_fetches_and_saves(self, mock_sleep, mock_head, record_with_ids):
        """Command fetches covers and saves them to records."""
        from django.core.management import call_command

        mock_head.return_value = _mock_head_response(5000)

        out = StringIO()
        call_command("fetch_covers", stdout=out)

        record_with_ids.refresh_from_db()
        assert record_with_ids.cover_url != ""
        assert "1 covers found" in out.getvalue()

    @patch("sources.covers.httpx.head")
    @patch("sources.covers.time.sleep")
    def test_skips_records_with_covers(self, mock_sleep, mock_head, record_with_ids):
        """Records that already have cover_url are skipped."""
        from django.core.management import call_command

        record_with_ids.cover_url = "https://example.com/cover.jpg"
        record_with_ids.save(update_fields=["cover_url"])

        out = StringIO()
        call_command("fetch_covers", stdout=out)

        assert "0 records checked" in out.getvalue()
        mock_head.assert_not_called()
