from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from catalog.models import Record


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


@pytest.mark.django_db
class TestManualEntry:
    def test_requires_login(self, client):
        response = client.get("/ingest/new/")
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_form_loads(self, client_logged_in):
        response = client_logged_in.get("/ingest/new/")
        assert response.status_code == 200
        assert b"Add a new record" in response.content

    def test_create_record(self, client_logged_in):
        response = client_logged_in.post(
            "/ingest/new/",
            {
                "title": "Test Book",
                "title_romanized": "",
                "subtitle": "",
                "date_of_publication": "2020",
                "date_of_publication_display": "",
                "place_of_publication": "New York",
                "language": "eng",
                "notes": "",
                "author_name": "Test Author",
                "author_name_romanized": "",
                "publisher_name": "Test Publisher",
                "publisher_place": "New York",
                "location_label": "Shelf A",
            },
        )
        assert response.status_code == 302
        record = Record.objects.get(title="Test Book")
        assert record.record_id.startswith("otzar-")
        assert record.created_by.username == "cataloger"
        assert record.authors.count() == 1
        assert record.publishers.count() == 1
        assert record.locations.count() == 1

    def test_create_hebrew_record(self, client_logged_in):
        response = client_logged_in.post(
            "/ingest/new/",
            {
                "title": "משנה תורה",
                "title_romanized": "Mishneh Torah",
                "subtitle": "",
                "date_of_publication": "",
                "date_of_publication_display": "",
                "place_of_publication": "",
                "language": "heb",
                "notes": "",
                "author_name": "רמבם",
                "author_name_romanized": "Maimonides",
                "publisher_name": "",
                "publisher_place": "",
                "location_label": "",
            },
        )
        assert response.status_code == 302
        record = Record.objects.get(title="משנה תורה")
        assert record.slug == "mishneh-torah"
        author = record.authors.first()
        assert author.name == "רמבם"

    def test_create_minimal_record(self, client_logged_in):
        response = client_logged_in.post(
            "/ingest/new/",
            {
                "title": "Minimal",
                "title_romanized": "",
                "subtitle": "",
                "date_of_publication": "",
                "date_of_publication_display": "",
                "place_of_publication": "",
                "language": "",
                "notes": "",
                "author_name": "",
                "author_name_romanized": "",
                "publisher_name": "",
                "publisher_place": "",
                "location_label": "",
            },
        )
        assert response.status_code == 302
        record = Record.objects.get(title="Minimal")
        assert record.authors.count() == 0

    def test_invalid_form_redisplays(self, client_logged_in):
        response = client_logged_in.post(
            "/ingest/new/",
            {"title": ""},  # title is required
        )
        assert response.status_code == 200
        assert b"correct the errors" in response.content


@pytest.mark.django_db
class TestEditRecord:
    def test_edit_loads_existing_data(self, client_logged_in, user):
        record = Record.objects.create(title="Original Title", created_by=user)
        response = client_logged_in.get(f"/ingest/edit/{record.record_id}/")
        assert response.status_code == 200
        assert b"Original Title" in response.content
        assert b"Edit record" in response.content

    def test_edit_saves_changes(self, client_logged_in, user):
        record = Record.objects.create(title="Original", created_by=user)
        response = client_logged_in.post(
            f"/ingest/edit/{record.record_id}/",
            {
                "title": "Updated Title",
                "title_romanized": "",
                "subtitle": "",
                "date_of_publication": "",
                "date_of_publication_display": "",
                "place_of_publication": "",
                "language": "",
                "notes": "",
                "author_name": "",
                "author_name_romanized": "",
                "publisher_name": "",
                "publisher_place": "",
                "location_label": "",
            },
        )
        assert response.status_code == 302
        record.refresh_from_db()
        assert record.title == "Updated Title"


@pytest.mark.django_db
class TestIngestModeNav:
    """Ingest route is a per-item choice, so it belongs on every page.

    The three ways in already existed as cards on /ingest/, but choosing
    one meant navigating back there between items. On a phone it was
    worse than that: base.html hides the whole nav below the sm
    breakpoint, so a phone that landed on a scan page had no way out of
    it at all.
    """

    @pytest.mark.parametrize(
        "url",
        ["/ingest/scan/", "/ingest/scan-title/", "/ingest/new/"],
    )
    def test_every_ingest_page_offers_all_three_routes(
        self, client_logged_in, url
    ):
        response = client_logged_in.get(url)
        body = response.content.decode()

        assert 'id="ingest-mode-nav"' in body
        assert 'href="/ingest/scan/"' in body
        assert 'href="/ingest/scan-title/"' in body
        assert 'href="/ingest/new/"' in body

    @pytest.mark.parametrize(
        "url,label",
        [
            ("/ingest/scan/", "Scan barcode"),
            ("/ingest/scan-title/", "Title page"),
            ("/ingest/new/", "Enter manually"),
        ],
    )
    def test_current_route_is_marked_current(
        self, client_logged_in, url, label
    ):
        response = client_logged_in.get(url)
        body = response.content.decode()

        marker = 'aria-current="page"'
        assert marker in body
        # The marked link is the one for this page, not another.
        segment = body[body.index(marker) : body.index(marker) + 400]
        assert label in segment

    def test_nav_reaches_phone_mode_title_page(self, client_logged_in):
        """The bar is the phone's only navigation, so it must render
        in the streamlined capture view too."""
        session = client_logged_in.session
        session["phone_scanner"] = True
        session["phone_scan_target"] = "title"
        session.save()

        response = client_logged_in.get("/ingest/scan-title/")
        body = response.content.decode()

        assert b"Title page capture" in response.content
        assert 'id="ingest-mode-nav"' in body
        assert 'href="/ingest/scan/"' in body

    def test_phone_that_authed_for_barcode_gets_phone_title_layout(
        self, client_logged_in
    ):
        """Tapping "Title page" on a phone that scanned the barcode QR
        must not drop it into the desktop layout.

        phone_scan_auth sets both phone_scanner and phone_scan_target,
        but the target only ever meant "where to redirect after auth".
        Keying the layout off it served the desktop QR sidebar to a
        phone the moment the user switched routes.
        """
        session = client_logged_in.session
        session["phone_scanner"] = True
        session["phone_scan_target"] = "isbn"
        session.save()

        response = client_logged_in.get("/ingest/scan-title/")

        assert b"Title page capture" in response.content
        assert b"Capture on your phone" not in response.content

    def test_desktop_session_still_gets_desktop_layout(self, client_logged_in):
        response = client_logged_in.get("/ingest/scan-title/")
        assert b"Scan title page" in response.content
        assert b"Capture on your phone" in response.content


@pytest.mark.django_db
class TestCandidateRecordCreation:
    """Both confirm paths must build the same record from a candidate.

    /ingest/confirm/ (reached from the cascade results) and the queue's
    "Use this" each had their own copy of the record-building code, and
    they had drifted: the queue path set neither source_marc nor
    date_of_publication_display, so a MARC date that will not parse as
    an integer was stored by one path and dropped by the other.
    """

    CANDIDATE = {
        "title": "Biblia Hebraica Stuttgartensia /",
        "title_alternate": "Torah, Nevi'im u-Khetuvim",
        "author": "Elliger, Karl",
        "date": "1994-2003",
        "publisher": "Deutsche Bibelgesellschaft",
        "place": "Stuttgart",
        "language": "ger",
        "source_catalog": "NLI",
        "source_marc": {"leader": "00000nam a2200000 a 4500"},
        "subjects": ["Bible. Old Testament -- Criticism"],
        "additional_authors": ["Rudolph, Wilhelm"],
        "isbn": "9783438052285",
        "lccn": "75950123",
    }

    def _fields(self, record):
        return {
            "title": record.title,
            "title_romanized": record.title_romanized,
            "date_of_publication": record.date_of_publication,
            "date_display": record.date_of_publication_display,
            "place": record.place_of_publication,
            "language": record.language,
            "source_catalog": record.source_catalog,
            "source_marc": record.source_marc,
            "authors": sorted(a.name for a in record.authors.all()),
            "publishers": sorted(p.name for p in record.publishers.all()),
            "subjects": sorted(s.heading for s in record.subjects.all()),
            "identifiers": sorted(
                (i.identifier_type, i.value)
                for i in record.external_identifiers.all()
            ),
        }

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_queue_confirm_matches_review_page_confirm(
        self, _cover, client_logged_in, user
    ):
        from ingest.models import ScanResult

        # Path A: the review page at /ingest/confirm/.
        session = client_logged_in.session
        session["candidate"] = self.CANDIDATE
        session.save()
        client_logged_in.post("/ingest/confirm/")
        via_review = Record.objects.order_by("-id").first()

        # Path B: the queue's "Use this".
        scan = ScanResult.objects.create(
            scan_type="isbn",
            status="pending",
            candidate_records=[self.CANDIDATE],
            scanned_by=user,
        )
        client_logged_in.post(
            f"/ingest/confirm/{scan.pk}/", {"candidate_index": "0"}
        )
        scan.refresh_from_db()
        via_queue = scan.created_record

        assert via_queue is not None
        assert self._fields(via_queue) == self._fields(via_review)

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_queue_confirm_keeps_an_unparseable_date(
        self, _cover, client_logged_in, user
    ):
        """The case that was silently losing data.

        "1994-2003" is not an int, so the queue path stored no year and
        no display string -- the date simply vanished from the record.
        """
        from ingest.models import ScanResult

        scan = ScanResult.objects.create(
            scan_type="isbn",
            status="pending",
            candidate_records=[self.CANDIDATE],
            scanned_by=user,
        )
        client_logged_in.post(
            f"/ingest/confirm/{scan.pk}/", {"candidate_index": "0"}
        )

        scan.refresh_from_db()
        record = scan.created_record
        assert record.get_date_display(), "the date was dropped entirely"
        assert "1994" in record.get_date_display()


@pytest.mark.django_db
class TestScanClosedOnConfirm:
    """Choosing a candidate has to close the scan that produced it.

    Both entry points into `_candidates.html` create or carry a
    ScanResult, and the "Use" button routes through select_candidate ->
    confirm_candidate, which knew nothing about it. The scan stayed
    pending forever: title-page scans reappeared in the Incoming photos
    pane on every poll tick, and ISBN lookups piled up in the review
    queue, both already catalogued.
    """

    CANDIDATE = {
        "title": "Mishneh Torah",
        "author": "Maimonides",
        "date": "1862",
        "publisher": "Romm",
        "place": "Vilna",
        "source_catalog": "NLI",
    }

    def _select_and_confirm(self, client, scan_id=None, index=0):
        import json as _json

        payload = {"candidate_data": _json.dumps(self.CANDIDATE)}
        if scan_id is not None:
            payload["scan_id"] = str(scan_id)
            payload["candidate_index"] = str(index)
        client.post("/ingest/select-candidate/", payload)
        return client.post("/ingest/confirm/")

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_title_page_scan_is_confirmed(
        self, _cover, client_logged_in, user
    ):
        from ingest.models import ScanResult

        scan = ScanResult.objects.create(
            scan_type="ocr",
            status="pending",
            ocr_output={"title": "Mishneh Torah"},
            scanned_by=user,
        )
        self._select_and_confirm(client_logged_in, scan.pk)

        scan.refresh_from_db()
        assert scan.status == "confirmed"
        assert scan.created_record is not None
        assert scan.created_record.title == "Mishneh Torah"

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_confirmed_scan_leaves_the_poll_pane(
        self, _cover, client_logged_in, user
    ):
        """The symptom the user actually sees."""
        from ingest.models import ScanResult

        scan = ScanResult.objects.create(
            scan_type="ocr",
            status="pending",
            ocr_output={"title": "Mishneh Torah"},
            scanned_by=user,
        )
        before = client_logged_in.get("/ingest/scan-title/poll/")
        assert f"title-page-card-{scan.pk}".encode() in before.content

        self._select_and_confirm(client_logged_in, scan.pk)

        after = client_logged_in.get("/ingest/scan-title/poll/")
        assert f"title-page-card-{scan.pk}".encode() not in after.content

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_isbn_lookup_scan_is_confirmed(
        self, _cover, client_logged_in, user
    ):
        """isbn_lookup_view creates a ScanResult too, and it was piling
        up in the review queue the same way."""
        from ingest.models import ScanResult

        scan = ScanResult.objects.create(
            scan_type="isbn",
            status="pending",
            isbn="9780899060269",
            candidate_records=[self.CANDIDATE],
            scanned_by=user,
        )
        self._select_and_confirm(client_logged_in, scan.pk)

        scan.refresh_from_db()
        assert scan.status == "confirmed"
        assert scan.created_record is not None
        assert scan.selected_candidate_index == 0

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_confirm_without_a_scan_still_works(
        self, _cover, client_logged_in
    ):
        """Not every candidate comes from a scan."""
        response = self._select_and_confirm(client_logged_in)
        assert response.status_code == 302
        assert Record.objects.filter(title="Mishneh Torah").exists()

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_a_discarded_scan_is_not_resurrected(
        self, _cover, client_logged_in, user
    ):
        from ingest.models import ScanResult

        scan = ScanResult.objects.create(
            scan_type="ocr", status="discarded", scanned_by=user
        )
        self._select_and_confirm(client_logged_in, scan.pk)

        scan.refresh_from_db()
        assert scan.status == "discarded"

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_another_users_scan_is_not_touched(
        self, _cover, client_logged_in, django_user_model
    ):
        from ingest.models import ScanResult

        other = django_user_model.objects.create_user(
            username="someone-else", password="testpass123"
        )
        scan = ScanResult.objects.create(
            scan_type="ocr",
            status="pending",
            ocr_output={"title": "Mishneh Torah"},
            scanned_by=other,
        )
        self._select_and_confirm(client_logged_in, scan.pk)

        scan.refresh_from_db()
        assert scan.status == "pending"
        assert scan.created_record is None
