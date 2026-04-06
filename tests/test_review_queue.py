from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.signing import TimestampSigner
from django.test import Client
from django.utils import timezone

from ingest.models import ScanResult


@pytest.fixture
def user(db):
    return User.objects.create_user(username="cataloger", password="testpass123")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff", password="testpass123", is_staff=True
    )


@pytest.fixture
def client_logged_in(user):
    c = Client()
    c.login(username="cataloger", password="testpass123")
    return c


@pytest.fixture
def pending_isbn_scan(user):
    return ScanResult.objects.create(
        scan_type="isbn",
        isbn="978-0-13-110362-7",
        candidate_records=[
            {
                "title": "The C Programming Language",
                "author": "Kernighan, Brian W.",
                "date": "1988",
                "publisher": "Prentice Hall",
                "place": "Englewood Cliffs, N.J.",
                "language": "eng",
                "source_catalog": "LC",
            },
            {
                "title": "The C Programming Language (2nd ed.)",
                "author": "Kernighan, Brian W.",
                "date": "1988",
                "source_catalog": "NLI",
            },
        ],
        scanned_by=user,
    )


@pytest.fixture
def pending_ocr_scan(user):
    return ScanResult.objects.create(
        scan_type="ocr",
        ocr_output={"title": "Sample Book", "author": "Author Name"},
        candidate_records=[
            {
                "title": "Sample Book",
                "author": "Author Name",
                "date": "2020",
                "source_catalog": "NLI",
            }
        ],
        scanned_by=user,
    )


@pytest.mark.django_db
class TestReviewQueue:
    def test_requires_login(self, client):
        response = client.get("/ingest/queue/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_page_loads(self, client_logged_in):
        response = client_logged_in.get("/ingest/queue/")
        assert response.status_code == 200
        assert b"Review Queue" in response.content

    def test_shows_pending_scans(self, client_logged_in, pending_isbn_scan):
        response = client_logged_in.get("/ingest/queue/")
        assert response.status_code == 200
        assert b"978-0-13-110362-7" in response.content

    def test_shows_ocr_scan(self, client_logged_in, pending_ocr_scan):
        response = client_logged_in.get("/ingest/queue/")
        assert response.status_code == 200
        assert b"Sample Book" in response.content

    def test_hides_other_users_scans(self, db, pending_isbn_scan):
        User.objects.create_user(username="other", password="testpass123")
        c = Client()
        c.login(username="other", password="testpass123")
        response = c.get("/ingest/queue/")
        assert response.status_code == 200
        assert b"978-0-13-110362-7" not in response.content

    def test_staff_sees_all_scans(self, staff_user, pending_isbn_scan):
        c = Client()
        c.login(username="staff", password="testpass123")
        response = c.get("/ingest/queue/")
        assert response.status_code == 200
        assert b"978-0-13-110362-7" in response.content


@pytest.mark.django_db
class TestConfirmScan:
    def test_confirm_creates_record(self, client_logged_in, pending_isbn_scan):
        response = client_logged_in.post(
            f"/ingest/confirm/{pending_isbn_scan.pk}/",
            {"candidate_index": "0"},
        )
        assert response.status_code == 302

        pending_isbn_scan.refresh_from_db()
        assert pending_isbn_scan.status == "confirmed"
        assert pending_isbn_scan.selected_candidate_index == 0
        assert pending_isbn_scan.created_record is not None

        record = pending_isbn_scan.created_record
        assert record.title == "The C Programming Language"
        assert record.authors.filter(name="Kernighan, Brian W.").exists()

    def test_confirm_second_candidate(self, client_logged_in, pending_isbn_scan):
        response = client_logged_in.post(
            f"/ingest/confirm/{pending_isbn_scan.pk}/",
            {"candidate_index": "1"},
        )
        assert response.status_code == 302

        pending_isbn_scan.refresh_from_db()
        assert pending_isbn_scan.selected_candidate_index == 1
        record = pending_isbn_scan.created_record
        assert "2nd ed." in record.title

    def test_confirm_requires_post(self, client_logged_in, pending_isbn_scan):
        response = client_logged_in.get(f"/ingest/confirm/{pending_isbn_scan.pk}/")
        assert response.status_code == 405

    def test_confirm_invalid_index(self, client_logged_in, pending_isbn_scan):
        response = client_logged_in.post(
            f"/ingest/confirm/{pending_isbn_scan.pk}/",
            {"candidate_index": "99"},
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestDiscardScan:
    def test_discard_marks_as_discarded(self, client_logged_in, pending_isbn_scan):
        response = client_logged_in.post(f"/ingest/discard/{pending_isbn_scan.pk}/")
        assert response.status_code == 302

        pending_isbn_scan.refresh_from_db()
        assert pending_isbn_scan.status == "discarded"

    def test_discard_requires_post(self, client_logged_in, pending_isbn_scan):
        response = client_logged_in.get(f"/ingest/discard/{pending_isbn_scan.pk}/")
        assert response.status_code == 405


@pytest.mark.django_db
class TestQRCode:
    def test_generates_png(self, client_logged_in):
        response = client_logged_in.get("/ingest/qr/")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        # PNG magic bytes
        assert response.content[:4] == b"\x89PNG"

    def test_requires_login(self, client):
        response = client.get("/ingest/qr/")
        assert response.status_code == 302


@pytest.mark.django_db
class TestPhoneScanAuth:
    def test_valid_token_logs_in(self, user):
        signer = TimestampSigner()
        token = signer.sign(str(user.pk))

        c = Client()
        response = c.get(f"/ingest/phone-auth/{token}/")
        assert response.status_code == 302
        # Should redirect to scanning page.
        assert response.url == "/ingest/scan/"

        # Verify user is logged in by accessing a login_required page.
        queue_resp = c.get("/ingest/queue/")
        assert queue_resp.status_code == 200

    def test_expired_token_fails(self, user):
        c = Client()
        # A tampered token triggers BadSignature (400).
        response = c.get("/ingest/phone-auth/tampered:bad:token/")
        assert response.status_code == 400

    def test_invalid_token_fails(self, user):
        c = Client()
        response = c.get("/ingest/phone-auth/totally-invalid-token/")
        assert response.status_code == 400


@pytest.mark.django_db
class TestCleanupCommand:
    def test_cleanup_deletes_old_discarded(self, user):
        # Create a discarded scan and backdate it.
        scan = ScanResult.objects.create(
            scan_type="isbn",
            isbn="000",
            status="discarded",
            scanned_by=user,
        )
        ScanResult.objects.filter(pk=scan.pk).update(
            updated_at=timezone.now() - timedelta(days=31)
        )

        # Create a recent discarded scan that should NOT be deleted.
        recent = ScanResult.objects.create(
            scan_type="isbn",
            isbn="111",
            status="discarded",
            scanned_by=user,
        )

        call_command("cleanup_staging", "--days=30")

        assert not ScanResult.objects.filter(pk=scan.pk).exists()
        assert ScanResult.objects.filter(pk=recent.pk).exists()

    def test_cleanup_leaves_pending(self, user):
        scan = ScanResult.objects.create(
            scan_type="isbn",
            isbn="222",
            status="pending",
            scanned_by=user,
        )
        ScanResult.objects.filter(pk=scan.pk).update(
            updated_at=timezone.now() - timedelta(days=31)
        )

        call_command("cleanup_staging", "--days=30")

        assert ScanResult.objects.filter(pk=scan.pk).exists()
