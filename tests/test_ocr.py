import io
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from ingest.ocr import _parse_vision_json, extract_metadata_from_image


@pytest.fixture
def user(db):
    return User.objects.create_user(username="cataloger", password="testpass123")


@pytest.fixture
def client_logged_in(user):
    c = Client()
    c.login(username="cataloger", password="testpass123")
    return c


SAMPLE_OCR_RESPONSE = {
    "title": "\u05de\u05e9\u05e0\u05d4 \u05ea\u05d5\u05e8\u05d4",
    "subtitle": None,
    "author": "\u05e8\u05de\u05d1\u05dd",
    "publisher": None,
    "place": "\u05d5\u05d9\u05dc\u05e0\u05d0",
    "date": "1862",
    "title_romanized": "Mishneh Torah",
    "author_romanized": "Maimonides",
}


class TestParseVisionJson:
    def test_plain_json(self):
        result = _parse_vision_json('{"title": "test", "date": "1900"}')
        assert result == {"title": "test", "date": "1900"}

    def test_markdown_fenced_json(self):
        text = '```json\n{"title": "test"}\n```'
        result = _parse_vision_json(text)
        assert result == {"title": "test"}

    def test_invalid_json_returns_none(self):
        result = _parse_vision_json("not json at all")
        assert result is None

    def test_gershayim_repair(self):
        # Hebrew double-quote (gershayim) between Hebrew chars
        text = '{"title": "\u05e8\u05de\u05d1"\u05dd"}'
        result = _parse_vision_json(text)
        assert result is not None
        assert "\u05f4" in result["title"]


class TestExtractMetadataFromImage:
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""})
    def test_no_api_key_returns_none(self):
        result = extract_metadata_from_image(b"fake image bytes")
        assert result is None

    @patch("ingest.ocr.anthropic.Anthropic")
    @patch.dict(
        "os.environ", {"ANTHROPIC_API_KEY": "test-key", "CLAUDE_MODEL": "test-model"}
    )
    def test_successful_extraction(self, mock_anthropic_cls):
        import json

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(SAMPLE_OCR_RESPONSE))]
        mock_client.messages.create.return_value = mock_message

        result = extract_metadata_from_image(b"fake image bytes")

        assert result is not None
        assert result["title"] == "\u05de\u05e9\u05e0\u05d4 \u05ea\u05d5\u05e8\u05d4"
        assert result["date"] == "1862"
        assert result["title_romanized"] == "Mishneh Torah"

        # Verify API was called with the right model
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "test-model"

    @patch("ingest.ocr.anthropic.Anthropic")
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_api_error_returns_none(self, mock_anthropic_cls):
        import anthropic

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="rate limit",
            request=MagicMock(),
            body=None,
        )

        result = extract_metadata_from_image(b"fake image bytes")
        assert result is None

    @patch("ingest.ocr.anthropic.Anthropic")
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_malformed_response_returns_none(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="This is not JSON at all")]
        mock_client.messages.create.return_value = mock_message

        result = extract_metadata_from_image(b"fake image bytes")
        assert result is None


@pytest.mark.django_db
class TestTitlePageScanView:
    def test_requires_login(self, client):
        response = client.get("/ingest/scan-title/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_page_loads(self, client_logged_in):
        response = client_logged_in.get("/ingest/scan-title/")
        assert response.status_code == 200
        assert b"Scan title page" in response.content
        assert b'accept="image/*"' in response.content


@pytest.mark.django_db
class TestTitlePageUploadView:
    def test_requires_login(self, client):
        response = client.post("/ingest/upload-title/")
        assert response.status_code == 302

    def test_rejects_get(self, client_logged_in):
        response = client_logged_in.get("/ingest/upload-title/")
        assert response.status_code == 405

    def test_no_image_error(self, client_logged_in):
        response = client_logged_in.post("/ingest/upload-title/")
        assert response.status_code == 200
        assert b"No image uploaded" in response.content

    @patch("ingest.views.extract_metadata_from_image")
    def test_successful_upload(self, mock_ocr, client_logged_in, tmp_path, settings):
        settings.BASE_DIR = tmp_path
        mock_ocr.return_value = SAMPLE_OCR_RESPONSE

        image = io.BytesIO(b"fake jpeg data")
        image.name = "test.jpg"

        response = client_logged_in.post(
            "/ingest/upload-title/",
            {"image": image},
            format="multipart",
        )

        assert response.status_code == 200
        assert b"Extracted metadata" in response.content
        assert (
            "\u05de\u05e9\u05e0\u05d4 \u05ea\u05d5\u05e8\u05d4".encode()
            in response.content
        )
        assert b"Mishneh Torah" in response.content
        mock_ocr.assert_called_once()

    @patch("ingest.views.extract_metadata_from_image")
    def test_ocr_failure(self, mock_ocr, client_logged_in, tmp_path, settings):
        settings.BASE_DIR = tmp_path
        mock_ocr.return_value = None

        image = io.BytesIO(b"fake jpeg data")
        image.name = "test.jpg"

        response = client_logged_in.post(
            "/ingest/upload-title/",
            {"image": image},
            format="multipart",
        )

        assert response.status_code == 200
        assert b"OCR could not extract metadata" in response.content

    @patch("ingest.views.search_lc")
    @patch("ingest.views.search_nli")
    def test_search_cascade(self, mock_nli, mock_lc, client_logged_in):
        from sources.cascade import CascadeResult

        mock_nli.return_value = CascadeResult(
            query_used="test",
            step="title",
            records=[{"title": "Test Book", "source_catalog": "NLI"}],
            total_hits=1,
        )
        mock_lc.return_value = CascadeResult()

        response = client_logged_in.post(
            "/ingest/upload-title/",
            {
                "action": "search",
                "title": "\u05de\u05e9\u05e0\u05d4 \u05ea\u05d5\u05e8\u05d4",
                "title_romanized": "Mishneh Torah",
                "date": "1862",
                "author": "",
                "author_romanized": "",
                "subtitle": "",
                "publisher": "",
                "place": "",
            },
        )

        assert response.status_code == 200
        mock_nli.assert_called_once()
        mock_lc.assert_called_once()
