"""Tests for the Open Library Covers API client and the storage it
feeds.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

import httpx
import pytest

from catalog.models import RecordCover
from sources.covers import CoverResult, fetch_cover


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


def _mock_get_response(body_size):
    """Create a mock httpx response with a given body size."""
    resp = MagicMock()
    resp.content = b"\xff" * body_size
    return resp


class TestFetchCover:
    @patch("sources.covers.httpx.get")
    def test_isbn_found(self, mock_get, record_with_ids):
        """ISBN lookup returns a valid cover (body > threshold)."""
        mock_get.return_value = _mock_get_response(5000)

        result = fetch_cover(record_with_ids)

        assert (
            result.url
            == "https://covers.openlibrary.org/b/isbn/9780123456789-M.jpg"
        )
        assert result.content == b"\xff" * 5000
        assert bool(result) is True
        assert mock_get.call_count == 1

    @patch("sources.covers.httpx.get")
    def test_isbn_placeholder_falls_through_to_oclc(
        self, mock_get, record_with_ids
    ):
        """ISBN returns 1x1 pixel, OCLC returns a real cover."""
        mock_get.side_effect = [
            _mock_get_response(43),  # ISBN: placeholder
            _mock_get_response(8000),  # OCLC: real cover
        ]

        result = fetch_cover(record_with_ids)

        assert (
            result.url
            == "https://covers.openlibrary.org/b/oclc/12345678-M.jpg"
        )
        assert mock_get.call_count == 2

    @patch("sources.covers.httpx.get")
    def test_all_placeholders_returns_empty(self, mock_get, record_with_ids):
        """All identifiers return 1x1 pixel placeholder."""
        mock_get.return_value = _mock_get_response(43)

        result = fetch_cover(record_with_ids)

        assert bool(result) is False
        assert result.url == ""
        assert result.content == b""
        assert mock_get.call_count == 3  # ISBN, OCLC, LCCN

    def test_no_identifiers_returns_empty(self, record_no_ids):
        """Record with no identifiers returns an empty result immediately."""
        result = fetch_cover(record_no_ids)
        assert bool(result) is False

    @patch("sources.covers.httpx.get")
    def test_timeout_returns_empty_and_does_not_raise(
        self, mock_get, record_with_ids
    ):
        """HTTP timeout is handled gracefully, returns an empty result."""
        mock_get.side_effect = httpx.TimeoutException("timed out")

        result = fetch_cover(record_with_ids)

        assert bool(result) is False

    @patch("sources.covers.httpx.get")
    def test_timeout_on_isbn_tries_oclc(self, mock_get, record_with_ids):
        """Timeout on ISBN still tries OCLC."""
        mock_get.side_effect = [
            httpx.TimeoutException("timed out"),  # ISBN
            _mock_get_response(5000),  # OCLC
        ]

        result = fetch_cover(record_with_ids)

        assert (
            result.url
            == "https://covers.openlibrary.org/b/oclc/12345678-M.jpg"
        )

    @patch("sources.covers.httpx.get")
    def test_http_error_returns_empty_and_does_not_raise(
        self, mock_get, record_with_ids
    ):
        """A mid-download failure is handled gracefully, not raised."""
        mock_get.side_effect = httpx.ReadError("connection reset")

        result = fetch_cover(record_with_ids)

        assert bool(result) is False


class TestCoverResult:
    def test_falsy_when_empty(self):
        assert bool(CoverResult()) is False

    def test_falsy_with_url_but_no_content(self):
        assert bool(CoverResult(url="https://example.com/x.jpg")) is False

    def test_truthy_with_url_and_content(self):
        assert bool(CoverResult(url="https://example.com/x.jpg", content=b"x"))


class TestRecordCoverStore:
    def test_stores_bytes_and_source_url(self, record_with_ids):
        cover = RecordCover.store(
            record_with_ids,
            "https://covers.openlibrary.org/b/isbn/9780123456789-M.jpg",
            b"\xff\xd8fake jpeg bytes",
        )

        assert cover.source_url == (
            "https://covers.openlibrary.org/b/isbn/9780123456789-M.jpg"
        )
        assert cover.image.read() == b"\xff\xd8fake jpeg bytes"
        assert record_with_ids.cover == cover

    def test_replaces_an_existing_cover(self, record_with_ids):
        RecordCover.store(
            record_with_ids, "https://example.com/old.jpg", b"old bytes"
        )
        cover = RecordCover.store(
            record_with_ids, "https://example.com/new.jpg", b"new bytes"
        )

        assert RecordCover.objects.filter(record=record_with_ids).count() == 1
        assert cover.source_url == "https://example.com/new.jpg"
        assert cover.image.read() == b"new bytes"


class TestFetchCoversCommand:
    @patch("sources.covers.httpx.get")
    def test_dry_run(self, mock_get, record_with_ids):
        """Dry run lists records without fetching covers."""
        from django.core.management import call_command

        out = StringIO()
        call_command("fetch_covers", "--dry-run", stdout=out)

        output = out.getvalue()
        assert "Dry run" in output
        assert record_with_ids.record_id in output
        mock_get.assert_not_called()

    @patch("sources.covers.httpx.get")
    @patch("sources.covers.time.sleep")
    def test_fetches_and_stores(self, mock_sleep, mock_get, record_with_ids):
        """Command fetches covers and stores them via Django's storage API."""
        from django.core.management import call_command

        mock_get.return_value = _mock_get_response(5000)

        out = StringIO()
        call_command("fetch_covers", stdout=out)

        record_with_ids.refresh_from_db()
        assert record_with_ids.cover is not None
        assert record_with_ids.cover.image.read() == b"\xff" * 5000
        assert "1 covers found" in out.getvalue()

    @patch("sources.covers.httpx.get")
    @patch("sources.covers.time.sleep")
    def test_placeholder_stores_nothing(
        self, mock_sleep, mock_get, record_with_ids
    ):
        """A 43-byte placeholder response is not stored as a cover."""
        from django.core.management import call_command

        mock_get.return_value = _mock_get_response(43)

        out = StringIO()
        call_command("fetch_covers", stdout=out)

        assert not RecordCover.objects.filter(record=record_with_ids).exists()
        assert "0 covers found" in out.getvalue()

    @patch("sources.covers.httpx.get")
    @patch("sources.covers.time.sleep")
    def test_skips_records_with_a_stored_cover(
        self, mock_sleep, mock_get, record_with_ids
    ):
        """Records that already have a stored cover are not re-fetched."""
        from django.core.management import call_command

        RecordCover.store(
            record_with_ids, "https://example.com/cover.jpg", b"already here"
        )

        out = StringIO()
        call_command("fetch_covers", stdout=out)

        assert "0 records checked" in out.getvalue()
        mock_get.assert_not_called()
