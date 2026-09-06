from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from catalog.models import Author, Record


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


@pytest.mark.django_db
class TestConfirmOffersExistingAuthors:
    """Confirming a candidate must not quietly split one person in two.

    The same person arrives romanized from one catalog and in Hebrew
    from another, so building the author with the incoming heading alone
    puts two rows in the catalog for one person and files their books
    apart in the author browse.
    """

    LC_AUTHOR = "Shneur Zalman, of Lyady"
    NLI_AUTHOR = "שניאור זלמן מלאדי"

    def candidate(self, **overrides):
        candidate = {
            "title": "Likute amarim (Tanya) /",
            "title_alternate": "לקוטי אמרים",
            "author": f"{self.LC_AUTHOR}, 1745-1812.",
            "author_alternate": self.NLI_AUTHOR,
            "date": "1984",
            "language": "heb",
            "source_catalog": "LC",
        }
        candidate.update(overrides)
        return candidate

    def start_confirm(self, client, candidate):
        session = client.session
        session["candidate"] = candidate
        session.save()
        return client.get("/ingest/confirm/")

    def test_no_match_stays_silent(self, client_logged_in):
        Author.objects.create(name="Elliger, Karl")
        response = self.start_confirm(client_logged_in, self.candidate())
        assert response.status_code == 200
        assert response.context["author_matches"] == []
        assert b'name="author_choice"' not in response.content

    def test_a_single_strong_match_is_offered_preselected(
        self, client_logged_in
    ):
        existing = Author.objects.create(name=self.NLI_AUTHOR)
        response = self.start_confirm(client_logged_in, self.candidate())
        assert [a for a, _ in response.context["author_matches"]] == [existing]
        assert response.context["author_match_default"] == existing.pk
        assert b'name="author_choice"' in response.content

    def test_a_romanized_match_is_offered(self, client_logged_in):
        existing = Author.objects.create(
            name="שניאור זלמן, מלאדי", name_romanized=self.LC_AUTHOR
        )
        candidate = self.candidate(
            author=f"{self.NLI_AUTHOR}.", author_alternate=self.LC_AUTHOR
        )
        response = self.start_confirm(client_logged_in, candidate)
        assert response.context["author_matches"] == [(existing, "romanized")]

    def test_a_variant_match_is_offered_but_not_preselected(
        self, client_logged_in
    ):
        """A variant hit is a suggestion, not a decision."""
        existing = Author.objects.create(
            name=self.LC_AUTHOR, variant_names=[self.NLI_AUTHOR]
        )
        candidate = self.candidate(
            author=f"{self.NLI_AUTHOR}.", author_alternate=None
        )
        response = self.start_confirm(client_logged_in, candidate)
        assert response.context["author_matches"] == [(existing, "variant")]
        assert response.context["author_match_default"] is None

    def test_several_matches_are_offered_without_a_default(
        self, client_logged_in
    ):
        Author.objects.create(name=self.NLI_AUTHOR)
        Author.objects.create(
            name="Zalman, Shneur", name_romanized=self.LC_AUTHOR
        )
        candidate = self.candidate(
            author=f"{self.NLI_AUTHOR}.", author_alternate=self.LC_AUTHOR
        )
        response = self.start_confirm(client_logged_in, candidate)
        assert len(response.context["author_matches"]) == 2
        assert response.context["author_match_default"] is None

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_choosing_an_existing_author_attaches_it(
        self, _cover, client_logged_in
    ):
        """The point of the whole exercise: one row, not two."""
        existing = Author.objects.create(
            name=self.LC_AUTHOR, variant_names=[self.NLI_AUTHOR]
        )
        candidate = self.candidate(
            author=f"{self.NLI_AUTHOR}.", author_alternate=None
        )
        self.start_confirm(client_logged_in, candidate)

        response = client_logged_in.post(
            "/ingest/confirm/", {"author_choice": str(existing.pk)}
        )

        assert response.status_code == 302
        record = Record.objects.get(title__startswith="Likute")
        assert list(record.authors.all()) == [existing]
        assert Author.objects.count() == 1

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_asking_for_a_new_author_still_creates_one(
        self, _cover, client_logged_in
    ):
        existing = Author.objects.create(name=self.NLI_AUTHOR)
        self.start_confirm(client_logged_in, self.candidate())

        client_logged_in.post("/ingest/confirm/", {"author_choice": "new"})

        record = Record.objects.get(title__startswith="Likute")
        assert record.authors.first() != existing
        assert Author.objects.count() == 2

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_the_queue_confirm_takes_a_single_strong_match(
        self, _cover, client_logged_in, user
    ):
        """The inline confirm has no page to ask on, so it takes the match."""
        from ingest.models import ScanResult

        existing = Author.objects.create(name=self.NLI_AUTHOR)
        scan = ScanResult.objects.create(
            scan_type="isbn",
            status="pending",
            candidate_records=[self.candidate()],
            scanned_by=user,
        )
        client_logged_in.post(
            f"/ingest/confirm/{scan.pk}/", {"candidate_index": "0"}
        )

        scan.refresh_from_db()
        assert list(scan.created_record.authors.all()) == [existing]
        assert Author.objects.count() == 1


@pytest.mark.django_db
class TestTitleStatementSurvivesConfirm:
    """The rest of the 245 has to reach the record it describes.

    A candidate card shows the part designation (245 $n), the part title
    (245 $p) and the statement of responsibility (245 $c). Confirming
    the candidate built a Record without them, so what the cataloger
    read on the card was gone from the record a moment later.

    The stored values carry no transcribed punctuation. The record page
    supplies its own ISBD colon between the part number and the part
    title, so a comma or a slash left on the end would print twice over.
    """

    STATEMENT = (
        "translated, annotated, and elucidated by Yisrael Isser Zvi Herczeg."
    )

    CANDIDATE = {
        "title": "Rashi : the Torah, with Rashi's commentary /",
        "volume_part_number": "Volume 2,",
        "volume_part_title": "Sefer Mishpatim /",
        "statement_of_responsibility": STATEMENT,
        "author": "Rashi,",
        "date": "1999",
        "source_catalog": "LC",
    }

    PLAIN_CANDIDATE = {
        "title": "Halakhic man /",
        "author": "Soloveitchik, Joseph Dov,",
        "date": "2007",
        "source_catalog": "NLI",
    }

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_the_review_page_confirm_keeps_all_three(
        self, _cover, client_logged_in
    ):
        session = client_logged_in.session
        session["candidate"] = self.CANDIDATE
        session.save()

        client_logged_in.post("/ingest/confirm/")

        record = Record.objects.get(title__startswith="Rashi")
        assert record.volume_part_number == "Volume 2"
        assert record.volume_part_title == "Sefer Mishpatim"
        assert record.statement_of_responsibility == (
            "translated, annotated, and elucidated by "
            "Yisrael Isser Zvi Herczeg"
        )

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_the_queue_confirm_keeps_all_three(
        self, _cover, client_logged_in, user
    ):
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
        assert record.volume_part_number == "Volume 2"
        assert record.volume_part_title == "Sefer Mishpatim"
        assert record.statement_of_responsibility.endswith("Herczeg")

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_a_candidate_carrying_none_of_them_stores_blanks(
        self, _cover, client_logged_in
    ):
        """The fields are blank-not-null, so absence has to read as ''."""
        session = client_logged_in.session
        session["candidate"] = self.PLAIN_CANDIDATE
        session.save()

        client_logged_in.post("/ingest/confirm/")

        record = Record.objects.get(title__startswith="Halakhic")
        assert record.volume_part_number == ""
        assert record.volume_part_title == ""
        assert record.statement_of_responsibility == ""


@pytest.mark.django_db
class TestSeriesOnConfirm:
    """Confirming a candidate has to place it in its series.

    The parser reads 490/830 into ``series_title`` and ``series_volume``
    and the card shows both, but nothing wrote them, so a set catalogued
    one volume at a time never became a set.

    A series is identified by its normalized title, because that is the
    only thing every volume of a set agrees on. The volume designation
    is normalized to Arabic digits, so "v. 1" and "חלק א" name the same
    position.
    """

    @staticmethod
    def candidate(title, series_title, series_volume):
        return {
            "title": title,
            "author": "Rashi,",
            "date": "1999",
            "source_catalog": "LC",
            "series_title": series_title,
            "series_volume": series_volume,
        }

    @staticmethod
    def confirm(client, candidate):
        session = client.session
        session["candidate"] = candidate
        session.save()
        client.post("/ingest/confirm/")
        return Record.objects.order_by("-id").first()

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_a_first_confirm_creates_the_series_and_the_volume(
        self, _cover, client_logged_in
    ):
        from catalog.models import Series, SeriesVolume

        record = self.confirm(
            client_logged_in,
            self.candidate("Bereshit /", "ArtScroll series ;", "v. 1"),
        )

        series = Series.objects.get()
        assert series.title == "ArtScroll series"

        volume = SeriesVolume.objects.get()
        assert volume.series == series
        assert volume.record == record
        assert volume.volume_number == "1"
        assert volume.held is True

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_a_second_volume_joins_the_series_the_first_made(
        self, _cover, client_logged_in
    ):
        """The same set catalogued twice is one series, not two.

        The two records come from catalogs that punctuate the series
        statement differently and write the volume number differently.
        Neither difference is about the set, so neither may split it.
        """
        from catalog.models import Series, SeriesVolume

        first = self.confirm(
            client_logged_in,
            self.candidate("Bereshit /", "ArtScroll series ;", "v. 1"),
        )
        second = self.confirm(
            client_logged_in,
            self.candidate("Shemot /", "Artscroll Series.", "vol. II"),
        )

        assert Series.objects.count() == 1
        series = Series.objects.get()
        assert SeriesVolume.objects.filter(series=series).count() == 2
        assert sorted(v.volume_number for v in series.volumes.all()) == [
            "1",
            "2",
        ]
        assert series.volumes.get(volume_number="1").record == first
        assert series.volumes.get(volume_number="2").record == second

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_a_confirm_claims_a_gap_left_for_the_volume(
        self, _cover, client_logged_in
    ):
        """A placeholder for a volume not yet held is filled, not doubled."""
        from catalog.models import Series, SeriesVolume
        from ingest.series_workflow import create_series_volumes

        series = Series.objects.create(title="ArtScroll series")
        create_series_volumes(series, "1-3")

        record = self.confirm(
            client_logged_in,
            self.candidate("Vayikra /", "ArtScroll series ;", "v. 3"),
        )

        assert SeriesVolume.objects.count() == 3
        volume = series.volumes.get(volume_number="3")
        assert volume.record == record
        assert volume.held is True

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_a_candidate_with_no_series_confirms_cleanly(
        self, _cover, client_logged_in
    ):
        from catalog.models import Series, SeriesVolume

        record = self.confirm(
            client_logged_in,
            {
                "title": "Halakhic man /",
                "author": "Soloveitchik, Joseph Dov,",
                "date": "2007",
                "source_catalog": "NLI",
                "series_title": None,
                "series_volume": None,
            },
        )

        assert record is not None
        assert Series.objects.count() == 0
        assert SeriesVolume.objects.count() == 0

    @patch("ingest.views.fetch_cover_url", return_value=None)
    def test_the_queue_confirm_places_the_record_too(
        self, _cover, client_logged_in, user
    ):
        from catalog.models import Series, SeriesVolume
        from ingest.models import ScanResult

        scan = ScanResult.objects.create(
            scan_type="isbn",
            status="pending",
            candidate_records=[
                self.candidate("Bamidbar /", "ArtScroll series ;", "v. 4")
            ],
            scanned_by=user,
        )

        client_logged_in.post(
            f"/ingest/confirm/{scan.pk}/", {"candidate_index": "0"}
        )

        scan.refresh_from_db()
        series = Series.objects.get()
        volume = SeriesVolume.objects.get()
        assert volume.series == series
        assert volume.record == scan.created_record
        assert volume.volume_number == "4"


@pytest.mark.django_db
class TestLinkRecordToSeries:
    """The helper both confirm paths run through."""

    @pytest.fixture
    def record(self, user):
        return Record.objects.create(title="Bereshit", created_by=user)

    def test_linking_twice_leaves_one_volume(self, record):
        from catalog.models import SeriesVolume
        from ingest.series_workflow import link_record_to_series

        first = link_record_to_series(record, "ArtScroll series ;", "v. 1")
        second = link_record_to_series(record, "ArtScroll series ;", "v. 1")

        assert first == second
        assert SeriesVolume.objects.count() == 1

    def test_a_record_offered_a_second_number_keeps_its_place(self, record):
        """One record holds one position in a series, not two."""
        from catalog.models import SeriesVolume
        from ingest.series_workflow import link_record_to_series

        link_record_to_series(record, "ArtScroll series", "v. 1")
        link_record_to_series(record, "ArtScroll series", "v. 2")

        assert SeriesVolume.objects.filter(record=record).count() == 1

    def test_no_title_links_nothing(self, record):
        from catalog.models import Series, SeriesVolume
        from ingest.series_workflow import link_record_to_series

        assert link_record_to_series(record, "", "v. 1") is None
        assert link_record_to_series(record, None, "") is None
        assert Series.objects.count() == 0
        assert SeriesVolume.objects.count() == 0

    def test_an_unnumbered_volume_still_joins_the_series(self, record):
        """A 490 with no $v is common; the link is still worth having."""
        from catalog.models import SeriesVolume
        from ingest.series_workflow import link_record_to_series

        volume = link_record_to_series(record, "Sifriyat Dorot", "")

        assert volume is not None
        assert volume.volume_number == ""
        assert SeriesVolume.objects.get().record == record

    def test_a_second_unnumbered_volume_does_not_displace_the_first(
        self, record, user
    ):
        """(series, volume_number) is unique, so the empty slot holds one.

        The second record keeps its own row in the catalog; it simply
        gets no series position, which is the honest answer when the
        source gave no number to tell the two apart by.
        """
        from catalog.models import SeriesVolume
        from ingest.series_workflow import link_record_to_series

        other = Record.objects.create(title="Shemot", created_by=user)
        link_record_to_series(record, "Sifriyat Dorot", "")

        assert link_record_to_series(other, "Sifriyat Dorot", "") is None
        assert SeriesVolume.objects.count() == 1
        assert SeriesVolume.objects.get().record == record

    def test_two_spellings_of_one_number_are_one_position(self, record, user):
        """Gematria and a Roman numeral for three are the same volume."""
        from catalog.models import SeriesVolume
        from ingest.series_workflow import link_record_to_series

        other = Record.objects.create(title="Shemot", created_by=user)
        link_record_to_series(record, "Mishneh Torah", "vol. III")

        assert link_record_to_series(other, "Mishneh Torah", "חלק ג") is None
        assert SeriesVolume.objects.count() == 1
        assert SeriesVolume.objects.get().volume_number == "3"
