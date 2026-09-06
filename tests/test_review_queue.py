import html as html_module
import re
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.signing import TimestampSigner
from django.test import Client

from ingest.models import ScanResult


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="cataloger", password="testpass123"
    )


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


@pytest.fixture
def rich_scan(user):
    """A scan whose candidate fills every column the row can show."""
    return ScanResult.objects.create(
        scan_type="isbn",
        isbn="978-3-438-05228-5",
        candidate_records=[
            {
                "title": "Biblia Hebraica Stuttgartensia",
                "title_alternate": "Torah, Neviim u-Khetuvim",
                "author": "Elliger, Karl",
                "additional_authors": ["Rudolph, Wilhelm"],
                "date": "1994-2003",
                "publisher": "Deutsche Bibelgesellschaft",
                "place": "Stuttgart",
                "language": "ger",
                "series_title": "Biblia Hebraica",
                "series_volume": "4",
                "subjects": ["Bible. Old Testament -- Criticism"],
                "isbn": "9783438052285",
                "lccn": "75950123",
                "oclc": "12345678",
                "lc_classification": "BS715 1994",
                "dewey_classification": "221.44",
                "source_catalog": "NLI",
            }
        ],
        scanned_by=user,
    )


@pytest.fixture
def empty_isbn_scan(user):
    return ScanResult.objects.create(
        scan_type="isbn",
        isbn="9780000000000",
        candidate_records=[],
        scanned_by=user,
    )


@pytest.fixture
def empty_ocr_scan(user):
    return ScanResult.objects.create(
        scan_type="ocr",
        ocr_output={
            "title": "Sefer ha-Zohar",
            "subtitle": "",
            "publisher": "Romm",
            "place": "Vilna",
            "date": "1882",
            "title_romanized": "Sefer ha-Zohar",
            "author": "",
            "author_romanized": "",
        },
        candidate_records=[],
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

    def test_confirm_second_candidate(
        self, client_logged_in, pending_isbn_scan
    ):
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
        response = client_logged_in.get(
            f"/ingest/confirm/{pending_isbn_scan.pk}/"
        )
        assert response.status_code == 405

    def test_confirm_invalid_index(self, client_logged_in, pending_isbn_scan):
        response = client_logged_in.post(
            f"/ingest/confirm/{pending_isbn_scan.pk}/",
            {"candidate_index": "99"},
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestDiscardScan:
    def test_discard_marks_as_discarded(
        self, client_logged_in, pending_isbn_scan
    ):
        response = client_logged_in.post(
            f"/ingest/discard/{pending_isbn_scan.pk}/"
        )
        assert response.status_code == 302

        pending_isbn_scan.refresh_from_db()
        assert pending_isbn_scan.status == "discarded"

    def test_discard_requires_post(self, client_logged_in, pending_isbn_scan):
        response = client_logged_in.get(
            f"/ingest/discard/{pending_isbn_scan.pk}/"
        )
        assert response.status_code == 405


@pytest.mark.django_db
class TestQRCode:
    def test_generates_png(self, client_logged_in):
        response = client_logged_in.get("/ingest/qr/")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        # PNG magic bytes
        assert response.content[:4] == b"\x89PNG"

    def test_target_title_generates_png(self, client_logged_in):
        response = client_logged_in.get("/ingest/qr/?target=title")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"

    def test_unknown_target_rejected(self, client_logged_in):
        response = client_logged_in.get("/ingest/qr/?target=bogus")
        assert response.status_code == 400

    def test_requires_login(self, client):
        response = client.get("/ingest/qr/")
        assert response.status_code == 302


@pytest.mark.django_db
class TestPhoneScanAuth:
    def test_legacy_token_defaults_to_isbn(self, user):
        # A legacy token (just user_pk, no target) should still work and
        # redirect to the ISBN scanner for backwards compatibility.
        signer = TimestampSigner()
        token = signer.sign(str(user.pk))

        c = Client()
        response = c.get(f"/ingest/phone-auth/{token}/")
        assert response.status_code == 302
        assert response.url == "/ingest/scan/"
        assert c.session.get("phone_scan_target") == "isbn"

        queue_resp = c.get("/ingest/queue/")
        assert queue_resp.status_code == 200

    def test_isbn_target_redirects_to_isbn_scan(self, user):
        signer = TimestampSigner()
        token = signer.sign(f"{user.pk}:isbn")

        c = Client()
        response = c.get(f"/ingest/phone-auth/{token}/")
        assert response.status_code == 302
        assert response.url == "/ingest/scan/"
        assert c.session.get("phone_scan_target") == "isbn"

    def test_title_target_redirects_to_title_page_scan(self, user):
        signer = TimestampSigner()
        token = signer.sign(f"{user.pk}:title")

        c = Client()
        response = c.get(f"/ingest/phone-auth/{token}/")
        assert response.status_code == 302
        assert response.url == "/ingest/scan-title/"
        assert c.session.get("phone_scan_target") == "title"

    def test_unknown_target_rejected(self, user):
        signer = TimestampSigner()
        token = signer.sign(f"{user.pk}:bogus")

        c = Client()
        response = c.get(f"/ingest/phone-auth/{token}/")
        assert response.status_code == 400

    def test_expired_token_fails(self, user):
        c = Client()
        # A tampered token triggers BadSignature (400).
        response = c.get("/ingest/phone-auth/tampered:bad:token/")
        assert response.status_code == 400

    def test_invalid_token_fails(self, user):
        c = Client()
        response = c.get("/ingest/phone-auth/totally-invalid-token/")
        assert response.status_code == 400


def _queue_html(client):
    response = client.get("/ingest/queue/")
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
class TestQueueRows:
    """Every column a cataloger needs to judge a match reads in the row.

    The queue used to show a candidate count and nothing else, so
    telling a right match from a wrong one meant opening each scan.
    """

    def test_row_names_title_and_author(self, client_logged_in, rich_scan):
        html = _queue_html(client_logged_in)
        assert "Biblia Hebraica Stuttgartensia" in html
        assert "Elliger, Karl" in html

    def test_row_shows_date_publisher_and_place(
        self, client_logged_in, rich_scan
    ):
        html = _queue_html(client_logged_in)
        assert "1994-2003" in html
        assert "Deutsche Bibelgesellschaft" in html
        assert "Stuttgart" in html

    def test_row_shows_series_and_volume(self, client_logged_in, rich_scan):
        html = _queue_html(client_logged_in)
        assert "Biblia Hebraica" in html
        assert "vol. 4" in html

    def test_row_shows_identifiers_and_source(
        self, client_logged_in, rich_scan
    ):
        html = _queue_html(client_logged_in)
        assert "ISBN 9783438052285" in html
        assert "LCCN 75950123" in html
        assert "OCLC 12345678" in html
        assert "NLI" in html

    def test_row_no_longer_leads_with_a_bare_count(
        self, client_logged_in, rich_scan
    ):
        html = _queue_html(client_logged_in)
        assert "1 candidate" not in html


@pytest.mark.django_db
class TestExpandedRow:
    """The expanded row carries the field set the record would receive."""

    def test_expansion_lists_additional_authors(
        self, client_logged_in, rich_scan
    ):
        assert "Rudolph, Wilhelm" in _queue_html(client_logged_in)

    def test_expansion_lists_subjects(self, client_logged_in, rich_scan):
        html = _queue_html(client_logged_in)
        assert "Bible. Old Testament -- Criticism" in html

    def test_expansion_names_the_language(self, client_logged_in, rich_scan):
        assert "German" in _queue_html(client_logged_in)

    def test_expansion_shows_every_identifier(
        self, client_logged_in, rich_scan
    ):
        html = _queue_html(client_logged_in)
        assert "BS715 1994" in html
        assert "221.44" in html

    def test_confirm_sits_inside_the_expansion(
        self, client_logged_in, rich_scan
    ):
        html = _queue_html(client_logged_in)
        assert f'action="/ingest/confirm/{rich_scan.pk}/"' in html
        assert "Confirm" in html

    def test_see_full_record_posts_to_select_candidate(
        self, client_logged_in, rich_scan
    ):
        html = _queue_html(client_logged_in)
        assert 'action="/ingest/select-candidate/"' in html
        assert "See full record" in html
        assert f'name="scan_id" value="{rich_scan.pk}"' in html

    def test_see_full_record_json_survives_the_round_trip(
        self, client_logged_in, rich_scan
    ):
        """The candidate JSON has to parse after the browser reads it back."""
        html = _queue_html(client_logged_in)
        match = re.search(
            r'<textarea name="candidate_data"[^>]*>(.*?)</textarea>',
            html,
            re.S,
        )
        assert match, "no candidate payload in the row"

        response = client_logged_in.post(
            "/ingest/select-candidate/",
            {
                "candidate_data": html_module.unescape(match.group(1)),
                "scan_id": str(rich_scan.pk),
                "candidate_index": "0",
            },
        )
        assert response.status_code == 302
        assert response.url == "/ingest/confirm/"

        confirm = client_logged_in.get("/ingest/confirm/")
        assert b"Biblia Hebraica Stuttgartensia" in confirm.content
        assert b"Rudolph, Wilhelm" in confirm.content


@pytest.mark.django_db
class TestZeroCandidateScans:
    """A scan that matched nothing says so where the user is looking."""

    def test_says_so_at_the_top_level(self, client_logged_in, empty_isbn_scan):
        assert "No matching records found" in _queue_html(client_logged_in)

    def test_shows_no_candidate_table(self, client_logged_in, empty_isbn_scan):
        html = _queue_html(client_logged_in)
        assert "Publisher · place" not in html
        assert "Title / author" not in html

    def test_isbn_scan_offers_the_search_again(
        self, client_logged_in, empty_isbn_scan
    ):
        html = _queue_html(client_logged_in)
        assert 'hx-post="/ingest/isbn-lookup/"' in html
        assert 'name="isbn" value="9780000000000"' in html
        assert "Search again" in html

    def test_ocr_scan_offers_the_search_again(
        self, client_logged_in, empty_ocr_scan
    ):
        html = _queue_html(client_logged_in)
        assert 'hx-post="/ingest/upload-title/"' in html
        assert 'name="action" value="search"' in html
        assert f'name="scan_id" value="{empty_ocr_scan.pk}"' in html
        assert 'name="title" value="Sefer ha-Zohar"' in html
        assert 'name="place" value="Vilna"' in html

    def test_offers_discard(self, client_logged_in, empty_isbn_scan):
        html = _queue_html(client_logged_in)
        assert f'action="/ingest/discard/{empty_isbn_scan.pk}/"' in html


@pytest.mark.django_db
class TestRepeatIsbnSearch:
    """Searching again from the queue updates the scan already there.

    Without this the queue grows a second pending row for the same
    book every time the user retries, and the first one stays behind
    with its empty candidate list.
    """

    RESULT = {
        "nli_records": [{"title": "Found on the second pass"}],
        "lc_records": [],
    }

    @patch("ingest.views.isbn_lookup")
    def test_reuses_the_scan_it_was_launched_from(
        self, mock_lookup, client_logged_in, empty_isbn_scan
    ):
        mock_lookup.return_value = self.RESULT
        before = ScanResult.objects.count()

        response = client_logged_in.post(
            "/ingest/isbn-lookup/",
            {
                "isbn": empty_isbn_scan.isbn,
                "scan_id": str(empty_isbn_scan.pk),
            },
        )
        assert response.status_code == 200
        assert ScanResult.objects.count() == before

        empty_isbn_scan.refresh_from_db()
        assert (
            empty_isbn_scan.candidate_records[0]["title"]
            == "Found on the second pass"
        )

    @patch("ingest.views.isbn_lookup")
    def test_lookup_without_a_scan_still_creates_one(
        self, mock_lookup, client_logged_in
    ):
        mock_lookup.return_value = self.RESULT
        before = ScanResult.objects.count()

        client_logged_in.post("/ingest/isbn-lookup/", {"isbn": "123"})

        assert ScanResult.objects.count() == before + 1

    @patch("ingest.views.isbn_lookup")
    def test_will_not_write_another_users_scan(
        self, mock_lookup, client_logged_in, db
    ):
        mock_lookup.return_value = self.RESULT
        other = User.objects.create_user(
            username="stranger", password="testpass123"
        )
        theirs = ScanResult.objects.create(
            scan_type="isbn",
            isbn="9780000000000",
            candidate_records=[],
            scanned_by=other,
        )

        client_logged_in.post(
            "/ingest/isbn-lookup/",
            {"isbn": theirs.isbn, "scan_id": str(theirs.pk)},
        )

        theirs.refresh_from_db()
        assert theirs.candidate_records == []
