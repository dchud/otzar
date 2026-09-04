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
