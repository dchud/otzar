import io
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from ingest.models import staging_image_path
from ingest.ocr import _parse_vision_json, extract_metadata_from_image


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="cataloger", password="testpass123"
    )


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
        "os.environ",
        {"ANTHROPIC_API_KEY": "test-key", "CLAUDE_MODEL": "test-model"},
    )
    def test_reads_past_a_leading_thinking_block(self, mock_anthropic_cls):
        """Thinking models put a reasoning block ahead of the answer."""
        import json

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(type="thinking", thinking="Reading the page..."),
            MagicMock(type="text", text=json.dumps(SAMPLE_OCR_RESPONSE)),
        ]
        mock_client.messages.create.return_value = mock_message

        result = extract_metadata_from_image(b"fake image bytes")

        assert result == SAMPLE_OCR_RESPONSE

    @patch("ingest.ocr.anthropic.Anthropic")
    @patch.dict(
        "os.environ",
        {"ANTHROPIC_API_KEY": "test-key", "CLAUDE_MODEL": "test-model"},
    )
    def test_successful_extraction(self, mock_anthropic_cls):
        import json

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(type="text", text=json.dumps(SAMPLE_OCR_RESPONSE))
        ]
        mock_client.messages.create.return_value = mock_message

        result = extract_metadata_from_image(b"fake image bytes")

        assert result is not None
        assert (
            result["title"]
            == "\u05de\u05e9\u05e0\u05d4 \u05ea\u05d5\u05e8\u05d4"
        )
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
        mock_message.content = [
            MagicMock(type="text", text="This is not JSON at all")
        ]
        mock_client.messages.create.return_value = mock_message

        result = extract_metadata_from_image(b"fake image bytes")
        assert result is None


@pytest.mark.django_db
class TestTitlePageScanView:
    def test_requires_login(self, client):
        response = client.get("/ingest/scan-title/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_desktop_view(self, client_logged_in):
        response = client_logged_in.get("/ingest/scan-title/")
        assert response.status_code == 200
        assert b"Scan title page" in response.content
        assert b'accept="image/*"' in response.content
        # Desktop view shows the QR handoff sidebar.
        assert b"Capture on your phone" in response.content
        assert b"target=title" in response.content
        # Polling pane is wired up.
        assert b'id="title-page-results"' in response.content
        assert b"Waiting for photos" in response.content

    def test_phone_view(self, user, client_logged_in):
        # Switch the session to phone-mode. phone_scan_auth always sets
        # both keys; the layout follows phone_scanner, and the target
        # only chooses the post-auth redirect.
        session = client_logged_in.session
        session["phone_scanner"] = True
        session["phone_scan_target"] = "title"
        session.save()

        response = client_logged_in.get("/ingest/scan-title/")
        assert response.status_code == 200
        assert b"Title page capture" in response.content
        # No QR sidebar in phone mode.
        assert b"Capture on your phone" not in response.content
        # Capture form and poll pane are present.
        assert b'accept="image/*"' in response.content
        assert b'id="title-page-results"' in response.content


@pytest.mark.django_db
class TestTitlePageUploadView:
    def test_requires_login(self, client):
        response = client.post("/ingest/upload-title/")
        assert response.status_code == 302

    def test_rejects_get(self, client_logged_in):
        response = client_logged_in.get("/ingest/upload-title/")
        assert response.status_code == 405

    @patch("ingest.views.extract_metadata_from_image")
    def test_upload_defers_ocr(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        settings.MEDIA_ROOT = str(tmp_path)

        image = io.BytesIO(b"fake jpeg data")
        image.name = "test.jpg"

        response = client_logged_in.post(
            "/ingest/upload-title/",
            {"image": image},
            format="multipart",
        )

        assert response.status_code == 200
        # Card is rendered so the user can preview and trigger OCR.
        assert b"Run OCR" in response.content
        # OCR is NOT invoked at upload time.
        mock_ocr.assert_not_called()

        from ingest.models import ScanResult

        scans = ScanResult.objects.filter(scan_type="ocr")
        assert scans.count() == 1
        scan = scans.first()
        assert scan.status == "awaiting_ocr"
        assert scan.ocr_output is None
        assert scan.image  # ImageField populated

    def test_retake_does_not_reuse_a_discarded_image_url(
        self, client_logged_in, tmp_path, settings
    ):
        """A retake gets its own URL, not the discarded photo's.

        Phone captures all arrive named image.jpg. Discarding deletes the
        stored file and frees that name, so a name derived from the upload
        puts the next photo on the URL the browser already has cached for
        the discarded one, and both devices keep showing the old image.
        """
        from ingest.models import ScanResult

        settings.MEDIA_ROOT = str(tmp_path)

        def upload(payload):
            image = io.BytesIO(payload)
            image.name = "image.jpg"
            client_logged_in.post(
                "/ingest/upload-title/", {"image": image}, format="multipart"
            )
            return ScanResult.objects.filter(scan_type="ocr").latest("id")

        first = upload(b"first photo")
        first_name = first.image.name

        client_logged_in.post(f"/ingest/scan-title/{first.pk}/discard/")
        first.refresh_from_db()
        assert not first.image

        second = upload(b"second photo")
        assert second.image.name != first_name

    def test_two_uploads_of_one_filename_get_distinct_urls(
        self, client_logged_in, tmp_path, settings
    ):
        """Two live scans never share a URL either."""
        from ingest.models import ScanResult

        settings.MEDIA_ROOT = str(tmp_path)
        for payload in (b"photo one", b"photo two"):
            image = io.BytesIO(payload)
            image.name = "image.jpg"
            client_logged_in.post(
                "/ingest/upload-title/", {"image": image}, format="multipart"
            )

        names = list(
            ScanResult.objects.filter(scan_type="ocr").values_list(
                "image", flat=True
            )
        )
        assert len(names) == 2
        assert len(set(names)) == 2

    def test_upload_no_image_keeps_no_scan(self, client_logged_in):
        response = client_logged_in.post("/ingest/upload-title/")
        assert response.status_code == 200
        assert b"No image uploaded" in response.content
        from ingest.models import ScanResult

        assert not ScanResult.objects.filter(scan_type="ocr").exists()

    def _upload_scan(self, client_logged_in, tmp_path, settings):
        """Helper: upload a fake image and return the resulting ScanResult."""
        from ingest.models import ScanResult

        settings.MEDIA_ROOT = str(tmp_path)
        image = io.BytesIO(b"fake jpeg data")
        image.name = "test.jpg"
        client_logged_in.post(
            "/ingest/upload-title/",
            {"image": image},
            format="multipart",
        )
        return ScanResult.objects.filter(scan_type="ocr").first()

    @patch("ingest.views.extract_metadata_from_image")
    def test_run_ocr_happy_path(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        mock_ocr.return_value = SAMPLE_OCR_RESPONSE
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        assert response.status_code == 200
        assert b"Extracted metadata" in response.content
        assert "משנה תורה".encode() in response.content
        assert b"Mishneh Torah" in response.content

        scan.refresh_from_db()
        assert scan.status == "pending"
        assert scan.ocr_output == SAMPLE_OCR_RESPONSE
        mock_ocr.assert_called_once()

    @patch("ingest.views.extract_metadata_from_image")
    def test_run_ocr_can_be_re_run_on_pending(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """Re-running OCR on a scan whose status moved to pending (because
        an earlier run produced unusable metadata) re-extracts and replaces."""
        first = {**SAMPLE_OCR_RESPONSE, "title": "first attempt"}
        second = {**SAMPLE_OCR_RESPONSE, "title": "second attempt"}
        mock_ocr.side_effect = [first, second]

        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")
        scan.refresh_from_db()
        assert scan.ocr_output["title"] == "first attempt"

        # Same endpoint, scan now in 'pending' — re-runs cleanly.
        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")
        assert response.status_code == 200

        scan.refresh_from_db()
        assert scan.status == "pending"
        assert scan.ocr_output["title"] == "second attempt"
        assert mock_ocr.call_count == 2

    @patch("ingest.views.extract_metadata_from_image")
    def test_run_ocr_returns_409_when_image_discarded(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        client_logged_in.post(f"/ingest/scan-title/{scan.pk}/discard/")

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")
        assert response.status_code == 409
        mock_ocr.assert_not_called()

    @patch("ingest.views.extract_metadata_from_image")
    def test_run_ocr_handles_extraction_failure(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        mock_ocr.return_value = None
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")
        assert response.status_code == 200
        assert b"OCR could not extract metadata" in response.content

        scan.refresh_from_db()
        assert scan.status == "awaiting_ocr"
        assert scan.ocr_output is None

    @patch("ingest.views.extract_metadata_from_image")
    def test_failure_response_carries_no_second_image(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """The failure notice is a message, not another copy of the card.

        The card already sits in the poll pane, so returning a card into
        the metadata pane put the same photo on screen twice, under a
        duplicated element id.
        """
        mock_ocr.return_value = None
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        assert b"OCR could not extract metadata" in response.content
        assert b"Try OCR again" in response.content
        assert b"<img" not in response.content
        assert (
            f'id="title-page-card-{scan.pk}"'.encode() not in response.content
        )

    @patch("ingest.views.extract_metadata_from_image")
    def test_run_ocr_failure_after_success_resets_to_awaiting(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """If a re-run produces no metadata, the scan returns to
        awaiting_ocr so the queue card surfaces it again."""
        mock_ocr.side_effect = [SAMPLE_OCR_RESPONSE, None]
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")
        client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        scan.refresh_from_db()
        assert scan.status == "awaiting_ocr"
        assert scan.ocr_output is None

    @patch("ingest.views.extract_metadata_from_image")
    def test_run_ocr_response_includes_retry_and_discard_buttons(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        mock_ocr.return_value = SAMPLE_OCR_RESPONSE
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")
        assert b"Re-run OCR" in response.content
        assert b"Discard" in response.content

    def test_run_ocr_rejects_non_owner(
        self, client_logged_in, tmp_path, settings
    ):
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        User.objects.create_user(username="other", password="testpass123")
        c = Client()
        c.login(username="other", password="testpass123")

        response = c.post(f"/ingest/scan-title/{scan.pk}/ocr/")
        assert response.status_code == 403

    def test_run_ocr_requires_post(self, client_logged_in, tmp_path, settings):
        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        response = client_logged_in.get(f"/ingest/scan-title/{scan.pk}/ocr/")
        assert response.status_code == 405

    def test_discard_removes_image_and_marks_row(
        self, client_logged_in, tmp_path, settings
    ):
        import os

        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        image_path = scan.image.path
        assert os.path.exists(image_path)

        response = client_logged_in.post(
            f"/ingest/scan-title/{scan.pk}/discard/"
        )
        assert response.status_code == 200
        assert response.content == b""

        scan.refresh_from_db()
        assert scan.status == "discarded"
        assert not scan.image
        assert not os.path.exists(image_path)

    def test_discard_is_idempotent(self, client_logged_in, tmp_path, settings):
        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        client_logged_in.post(f"/ingest/scan-title/{scan.pk}/discard/")

        # Second call should still return 200, not raise.
        response = client_logged_in.post(
            f"/ingest/scan-title/{scan.pk}/discard/"
        )
        assert response.status_code == 200

    def test_discard_tolerates_missing_file(
        self, client_logged_in, tmp_path, settings
    ):
        import os

        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        # Manually remove the file from disk while leaving the DB row alone.
        os.remove(scan.image.path)

        response = client_logged_in.post(
            f"/ingest/scan-title/{scan.pk}/discard/"
        )
        assert response.status_code == 200
        scan.refresh_from_db()
        assert scan.status == "discarded"

    def test_discard_rejects_non_owner(
        self, client_logged_in, tmp_path, settings
    ):
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        User.objects.create_user(username="other", password="testpass123")
        c = Client()
        c.login(username="other", password="testpass123")

        response = c.post(f"/ingest/scan-title/{scan.pk}/discard/")
        assert response.status_code == 403

    def test_discard_requires_post(self, client_logged_in, tmp_path, settings):
        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        response = client_logged_in.get(
            f"/ingest/scan-title/{scan.pk}/discard/"
        )
        assert response.status_code == 405


@pytest.mark.django_db
class TestTitlePagePoll:
    def _upload(self, c, tmp_path, settings):
        from ingest.models import ScanResult

        settings.MEDIA_ROOT = str(tmp_path)
        image = io.BytesIO(b"fake jpeg data")
        image.name = "p.jpg"
        c.post("/ingest/upload-title/", {"image": image}, format="multipart")
        return ScanResult.objects.filter(scan_type="ocr").first()

    def test_requires_login(self, client):
        response = client.get("/ingest/scan-title/poll/")
        assert response.status_code == 302

    def test_empty_state(self, client_logged_in):
        response = client_logged_in.get("/ingest/scan-title/poll/")
        assert response.status_code == 200
        assert b"Waiting for photos" in response.content

    def test_returns_owner_awaiting_scans(
        self, client_logged_in, user, tmp_path, settings
    ):
        scan = self._upload(client_logged_in, tmp_path, settings)
        response = client_logged_in.get("/ingest/scan-title/poll/")
        assert response.status_code == 200
        assert f"title-page-card-{scan.pk}".encode() in response.content

    def test_excludes_other_users_scans(self, user, tmp_path, settings):
        from ingest.models import ScanResult

        settings.MEDIA_ROOT = str(tmp_path)
        # Other user uploads a scan.
        other = User.objects.create_user(
            username="other", password="testpass123"
        )
        c_other = Client()
        c_other.login(username="other", password="testpass123")
        image = io.BytesIO(b"fake jpeg data")
        image.name = "x.jpg"
        c_other.post(
            "/ingest/upload-title/", {"image": image}, format="multipart"
        )
        other_scan = ScanResult.objects.filter(scanned_by=other).first()

        # Owner sees only their own scans (none in this case).
        c = Client()
        c.login(username="cataloger", password="testpass123")
        response = c.get("/ingest/scan-title/poll/")
        assert response.status_code == 200
        assert (
            f"title-page-card-{other_scan.pk}".encode() not in response.content
        )
        assert b"Waiting for photos" in response.content

    def test_excludes_pending_without_ocr_output(
        self, client_logged_in, tmp_path, settings
    ):
        # A scan in 'pending' state with no ocr_output is a degenerate
        # state, but defend against it: only pending+ocr_output cards
        # should appear in the title-page poll.
        scan = self._upload(client_logged_in, tmp_path, settings)
        scan.status = "pending"
        scan.save(update_fields=["status"])

        response = client_logged_in.get("/ingest/scan-title/poll/")
        assert f"title-page-card-{scan.pk}".encode() not in response.content
        assert b"Waiting for photos" in response.content

    def test_includes_pending_with_ocr_output(
        self, client_logged_in, tmp_path, settings
    ):
        # Scans where OCR has succeeded but the user hasn't confirmed a
        # candidate yet must still appear so they can be resumed or
        # discarded. The card has a "Continue editing" affordance instead
        # of "Run OCR".
        scan = self._upload(client_logged_in, tmp_path, settings)
        scan.status = "pending"
        scan.ocr_output = {"title": "Some title"}
        scan.save(update_fields=["status", "ocr_output"])

        response = client_logged_in.get("/ingest/scan-title/poll/")
        assert f"title-page-card-{scan.pk}".encode() in response.content
        assert b"Continue editing" in response.content
        assert b"Run OCR" not in response.content

    def test_edit_metadata_endpoint_returns_form(
        self, client_logged_in, tmp_path, settings
    ):
        scan = self._upload(client_logged_in, tmp_path, settings)
        scan.status = "pending"
        scan.ocr_output = {
            "title": "Some title",
            "title_romanized": "Some Title",
        }
        scan.save(update_fields=["status", "ocr_output"])

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/edit/")
        assert response.status_code == 200
        assert b"Extracted metadata" in response.content
        assert b"Some Title" in response.content
        # Form has the retry/discard buttons too.
        assert b"Re-run OCR" in response.content
        assert b"Discard" in response.content

    def test_edit_metadata_409_when_no_ocr(
        self, client_logged_in, tmp_path, settings
    ):
        scan = self._upload(client_logged_in, tmp_path, settings)
        # awaiting_ocr (no ocr_output yet)
        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/edit/")
        assert response.status_code == 409

    def test_edit_metadata_rejects_non_owner(
        self, client_logged_in, tmp_path, settings
    ):
        scan = self._upload(client_logged_in, tmp_path, settings)
        scan.status = "pending"
        scan.ocr_output = {"title": "x"}
        scan.save(update_fields=["status", "ocr_output"])

        User.objects.create_user(username="other", password="testpass123")
        c = Client()
        c.login(username="other", password="testpass123")
        response = c.post(f"/ingest/scan-title/{scan.pk}/edit/")
        assert response.status_code == 403

    def test_staff_sees_all_awaiting(self, user, tmp_path, settings):
        from ingest.models import ScanResult

        settings.MEDIA_ROOT = str(tmp_path)
        # Non-staff user uploads.
        c_user = Client()
        c_user.login(username="cataloger", password="testpass123")
        image = io.BytesIO(b"fake jpeg data")
        image.name = "p.jpg"
        c_user.post(
            "/ingest/upload-title/", {"image": image}, format="multipart"
        )
        scan = ScanResult.objects.filter(scanned_by=user).first()

        # Staff user sees the user's scan in their poll.
        User.objects.create_user(
            username="admin", password="testpass123", is_staff=True
        )
        c_staff = Client()
        c_staff.login(username="admin", password="testpass123")
        response = c_staff.get("/ingest/scan-title/poll/")
        assert f"title-page-card-{scan.pk}".encode() in response.content

    @patch("ingest.views.search_lc")
    @patch("ingest.views.search_nli")
    def test_search_cascade(self, mock_nli, mock_lc, client_logged_in):
        from sources.cascade import CascadeResult

        mock_nli.return_value = CascadeResult(
            query_used="test",
            step="title",
            records=[
                {
                    "title": "Test Book",
                    "author": "Some Author",
                    "date": "1900",
                    "publisher": "Some Press",
                    "place": "Jerusalem",
                    "isbn": "123",
                    "source_catalog": "NLI",
                }
            ],
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
        # Candidates render fully \u2014 title, author, date, publisher, ISBN
        # all visible. Guards against the bug where the OCR cascade-search
        # path passed raw candidates instead of {"data": ..., "json": ...}
        # so every cell rendered empty.
        assert b"Test Book" in response.content
        assert b"Some Author" in response.content
        assert b"1900" in response.content
        assert b"Some Press" in response.content
        assert b"Jerusalem" in response.content
        assert b"ISBN 123" in response.content
        assert b"NLI" in response.content


class TestOCRLease:
    """A run of OCR is visible to every device, not just the clicking one.

    The spinner on the button is driven by htmx's .htmx-request class,
    which only ever lands in the browser that started the request. The
    other device polls, renders from the database, and saw a row still
    in awaiting_ocr — an idle, clickable Run OCR button inviting a
    second call to the vision API on the same image.

    ``ocr_started_at`` is that missing shared state, held as a lease
    rather than a status so a process that dies mid-call cannot strand
    the row: the lease simply ages out.
    """

    def _upload_scan(self, client_logged_in, tmp_path, settings):
        from ingest.models import ScanResult

        settings.MEDIA_ROOT = str(tmp_path)
        image = io.BytesIO(b"fake jpeg data")
        image.name = "test.jpg"
        client_logged_in.post(
            "/ingest/upload-title/",
            {"image": image},
            format="multipart",
        )
        return ScanResult.objects.filter(scan_type="ocr").first()

    @patch("ingest.views.extract_metadata_from_image")
    def test_lease_is_held_while_extraction_runs(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """The lease must be visible to a concurrent reader mid-call.

        Asserting after the response returns would prove nothing — the
        lease is cleared by then. The check has to happen while the
        vision call is in flight, which is what a polling second device
        is doing.
        """
        from ingest.models import ScanResult

        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        seen = {}

        def observe(_image_bytes):
            fresh = ScanResult.objects.get(pk=scan.pk)
            seen["ocr_started_at"] = fresh.ocr_started_at
            return SAMPLE_OCR_RESPONSE

        mock_ocr.side_effect = observe
        client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        assert seen["ocr_started_at"] is not None

    @patch("ingest.views.extract_metadata_from_image")
    def test_lease_released_on_success(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        mock_ocr.return_value = SAMPLE_OCR_RESPONSE
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        scan.refresh_from_db()
        assert scan.ocr_started_at is None

    @patch("ingest.views.extract_metadata_from_image")
    def test_lease_released_when_extraction_returns_none(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        mock_ocr.return_value = None
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        scan.refresh_from_db()
        assert scan.ocr_started_at is None

    @patch("ingest.views.extract_metadata_from_image")
    def test_lease_released_when_extraction_raises(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """An exception must not strand the row behind a held lease."""
        mock_ocr.side_effect = RuntimeError("vision API exploded")
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        with pytest.raises(RuntimeError):
            client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        scan.refresh_from_db()
        assert scan.ocr_started_at is None

    @patch("ingest.views.extract_metadata_from_image")
    def test_second_run_rejected_while_lease_is_live(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """The other device's click must not spend a second API call."""
        from django.utils import timezone

        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        scan.ocr_started_at = timezone.now()
        scan.save(update_fields=["ocr_started_at"])

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        assert response.status_code == 409
        mock_ocr.assert_not_called()

    @patch("ingest.views.extract_metadata_from_image")
    def test_run_proceeds_once_lease_has_aged_out(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """A crashed run leaves a lease behind; it must not be permanent."""
        from datetime import timedelta

        from django.utils import timezone

        mock_ocr.return_value = SAMPLE_OCR_RESPONSE
        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        scan.ocr_started_at = timezone.now() - timedelta(minutes=5)
        scan.save(update_fields=["ocr_started_at"])

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        assert response.status_code == 200
        mock_ocr.assert_called_once()

    def test_poll_card_shows_reading_state_while_lease_live(
        self, client_logged_in, tmp_path, settings
    ):
        """This is the whole point: the second device sees the run."""
        from django.utils import timezone

        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        scan.ocr_started_at = timezone.now()
        scan.save(update_fields=["ocr_started_at"])

        response = client_logged_in.get("/ingest/scan-title/poll/")

        assert f"title-page-card-{scan.pk}".encode() in response.content
        assert b"Reading..." in response.content
        assert b"disabled" in response.content

    def test_poll_card_offers_run_ocr_when_no_lease(
        self, client_logged_in, tmp_path, settings
    ):
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        response = client_logged_in.get("/ingest/scan-title/poll/")

        assert f"title-page-card-{scan.pk}".encode() in response.content
        assert b"Run OCR" in response.content


class TestSearchProgress:
    """The catalog search takes 7-12s and said so in passing grey text.

    ``SRU_REQUEST_DELAY`` sleeps before each SRU request and the search
    queries two catalogs, so the wait is long enough that a static
    "Searching..." beside the button reads as though nothing is
    happening. The button carries its own state, as Run OCR already
    does, and the detail beside it names the catalogs being queried.
    """

    def _upload_scan(self, client_logged_in, tmp_path, settings):
        from ingest.models import ScanResult

        settings.MEDIA_ROOT = str(tmp_path)
        image = io.BytesIO(b"fake jpeg data")
        image.name = "test.jpg"
        client_logged_in.post(
            "/ingest/upload-title/",
            {"image": image},
            format="multipart",
        )
        return ScanResult.objects.filter(scan_type="ocr").first()

    @patch("ingest.views.extract_metadata_from_image")
    def test_search_button_carries_its_own_busy_state(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        mock_ocr.return_value = SAMPLE_OCR_RESPONSE
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")
        body = response.content.decode()

        assert "Search catalogs" in body
        # The busy label sits inside the button, not in a detached span.
        button = body[body.index("Search catalogs") - 900 :]
        assert "btn-idle" in button
        assert "btn-busy" in button
        assert "Searching..." in button

    @patch("ingest.views.extract_metadata_from_image")
    def test_search_detail_names_the_catalogs_queried(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """One request covers both catalogs, so the browser cannot know
        which is in flight. It can honestly say which will be asked."""
        mock_ocr.return_value = SAMPLE_OCR_RESPONSE
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")
        body = response.content.decode()

        assert "NLI" in body
        assert "Library of Congress" in body

    @patch("ingest.views.extract_metadata_from_image")
    def test_no_detached_search_spinner_remains(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """The old grey span beside the button is gone, not doubled up."""
        mock_ocr.return_value = SAMPLE_OCR_RESPONSE
        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")
        body = response.content.decode()

        assert body.count("Searching...") == 1


class TestOCRLeaseRaces:
    """The lease has to hold under the races it exists to prevent."""

    def _upload_scan(self, client_logged_in, tmp_path, settings):
        from ingest.models import ScanResult

        settings.MEDIA_ROOT = str(tmp_path)
        image = io.BytesIO(b"fake jpeg data")
        image.name = "test.jpg"
        client_logged_in.post(
            "/ingest/upload-title/",
            {"image": image},
            format="multipart",
        )
        return ScanResult.objects.filter(scan_type="ocr").first()

    def test_lease_cannot_be_taken_twice(
        self, client_logged_in, tmp_path, settings
    ):
        """Checking then setting leaves a window; claiming must be one
        statement the database arbitrates."""
        from ingest.views import _take_ocr_lease

        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        assert _take_ocr_lease(scan) is True
        assert _take_ocr_lease(scan) is False

    def test_stale_lease_can_be_reclaimed(
        self, client_logged_in, tmp_path, settings
    ):
        from datetime import timedelta

        from django.utils import timezone

        from ingest.views import _take_ocr_lease

        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        scan.ocr_started_at = timezone.now() - timedelta(minutes=5)
        scan.save(update_fields=["ocr_started_at"])

        assert _take_ocr_lease(scan) is True

    @patch("ingest.views.extract_metadata_from_image")
    def test_discard_during_run_is_not_undone(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """The row is read before a 5-9 second call and written after.

        A discard from the other device lands in between, and writing
        the result back resurrected the scan as a card with no image
        whose only button always 409s.
        """
        from ingest.models import ScanResult

        scan = self._upload_scan(client_logged_in, tmp_path, settings)

        def discard_midway(_image_bytes):
            ScanResult.objects.filter(pk=scan.pk).update(
                status="discarded", image=""
            )
            return SAMPLE_OCR_RESPONSE

        mock_ocr.side_effect = discard_midway
        client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        scan.refresh_from_db()
        assert scan.status == "discarded"
        assert not scan.ocr_output

    @patch("ingest.views.extract_metadata_from_image")
    def test_busy_response_is_renderable(
        self, mock_ocr, client_logged_in, tmp_path, settings
    ):
        """htmx does not swap 4xx bodies by default, so a bare string
        409 left the other device's click doing nothing at all."""
        from django.utils import timezone

        scan = self._upload_scan(client_logged_in, tmp_path, settings)
        scan.ocr_started_at = timezone.now()
        scan.save(update_fields=["ocr_started_at"])

        response = client_logged_in.post(f"/ingest/scan-title/{scan.pk}/ocr/")

        assert response.status_code == 409
        assert b"already running" in response.content
        assert b"<" in response.content, "409 body must be renderable HTML"
        mock_ocr.assert_not_called()

    def test_upload_and_poll_return_the_same_cards(
        self, client_logged_in, tmp_path, settings
    ):
        """The comment on title_page_upload claims these are
        interchangeable; they were not, so an already-OCR'd card
        vanished on upload and came back on the next poll."""
        from ingest.models import ScanResult

        done = self._upload_scan(client_logged_in, tmp_path, settings)
        done.status = "pending"
        done.ocr_output = SAMPLE_OCR_RESPONSE
        done.save(update_fields=["status", "ocr_output"])

        image = io.BytesIO(b"second photo")
        image.name = "test.jpg"
        upload = client_logged_in.post(
            "/ingest/upload-title/", {"image": image}, format="multipart"
        )
        poll = client_logged_in.get("/ingest/scan-title/poll/")

        new = ScanResult.objects.filter(status="awaiting_ocr").first()
        for pk in (done.pk, new.pk):
            marker = f"title-page-card-{pk}".encode()
            assert marker in upload.content, f"upload dropped card {pk}"
            assert marker in poll.content, f"poll dropped card {pk}"


class TestStagingImagePath:
    """The stored name has to describe the bytes that are stored.

    Everything reaching this field is JPEG: the capture form re-encodes
    what it can decode, and submits the original only when it is already
    JPEG.
    """

    def test_png_name_is_renamed(self):
        path = staging_image_path(None, "screenshot.png")
        assert path.endswith(".jpg")

    def test_heic_name_is_renamed(self):
        path = staging_image_path(None, "IMG_0042.HEIC")
        assert path.endswith(".jpg")

    def test_extensionless_name_is_named(self):
        path = staging_image_path(None, "image")
        assert path.endswith(".jpg")

    def test_jpeg_names_are_kept(self):
        assert staging_image_path(None, "photo.jpg").endswith(".jpg")
        assert staging_image_path(None, "photo.JPEG").endswith(".jpeg")

    def test_each_upload_gets_its_own_name(self):
        first = staging_image_path(None, "image.jpg")
        second = staging_image_path(None, "image.jpg")
        assert first != second
        assert first.startswith("staging/")
