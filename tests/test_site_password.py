"""The site password gate, and the system check that it is on."""

import time
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.checks import Tags, run_checks
from django.core.signing import TimestampSigner, b62_encode
from django.test import Client

from otzar.checks import check_site_password

GATE = "This site requires a password"


@pytest.fixture
def gate(settings):
    settings.SITE_PASSWORD = "open-sesame"


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="alice", password="right-password"
    )


def _is_gate(response):
    return GATE in response.content.decode()


def _pass_gate(client, path="/"):
    return client.post(path, {"site_password": "open-sesame"})


@pytest.mark.django_db
@pytest.mark.usefixtures("gate")
class TestGate:
    def test_right_password_opens_the_gate(self):
        client = Client()
        _pass_gate(client)

        assert client.session["site_password_ok"] is True
        assert not _is_gate(client.get("/"))

    def test_wrong_password_keeps_the_gate_shut(self):
        client = Client()
        response = client.post("/", {"site_password": "open-sesamE"})

        assert _is_gate(response)
        assert "site_password_ok" not in client.session

    def test_missing_field_keeps_the_gate_shut(self):
        response = Client().post("/", {})

        assert _is_gate(response)

    def test_accepted_password_redirects_to_the_same_url(self):
        client = Client()
        response = _pass_gate(client, "/accounts/login/?next=/ingest/")

        assert response.status_code == 303
        assert response["Location"] == "/accounts/login/?next=/ingest/"

    def test_redirect_stays_on_this_host(self):
        response = Client().post(
            "/",
            {"site_password": "open-sesame"},
            PATH_INFO="//evil.example/page",
        )

        assert response.status_code == 303
        assert response["Location"].startswith("/%2F")

    @pytest.mark.parametrize("path", ["/accounts/login/", "/admin/login/"])
    def test_login_pages_are_behind_the_gate(self, path):
        response = Client().get(path)

        assert _is_gate(response)
        assert 'name="username"' not in response.content.decode()

    def test_login_post_without_the_gate_never_authenticates(self, user):
        from axes.models import AccessAttempt

        with patch("django.contrib.auth.forms.authenticate") as authenticate:
            response = Client().post(
                "/accounts/login/",
                {"username": "alice", "password": "wrong"},
                REMOTE_ADDR="198.51.100.7",
            )

        assert _is_gate(response)
        authenticate.assert_not_called()
        assert AccessAttempt.objects.count() == 0

    def test_login_after_the_gate(self, user):
        client = Client()
        _pass_gate(client, "/accounts/login/")

        response = client.post(
            "/accounts/login/",
            {"username": "alice", "password": "right-password"},
        )

        assert response.status_code == 302
        assert client.session["_auth_user_id"]

    def test_logout_keeps_the_gate_open(self, user):
        client = Client()
        _pass_gate(client, "/accounts/login/")
        client.post(
            "/accounts/login/",
            {"username": "alice", "password": "right-password"},
        )

        client.post("/accounts/logout/")

        assert "_auth_user_id" not in client.session
        assert not _is_gate(client.get("/"))

    def test_logout_without_the_gate_flag_leaves_the_gate_shut(self, user):
        # A phone logged in by its QR token never saw the gate, so
        # logging out must not open it.
        client = Client()
        client.force_login(user)

        client.post("/accounts/logout/")

        assert _is_gate(client.get("/"))

    def test_other_ingest_paths_are_behind_the_gate(self):
        assert _is_gate(Client().get("/ingest/"))

    def test_health_check_is_exempt(self):
        response = Client().get("/health/")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.django_db
@pytest.mark.usefixtures("gate")
class TestPhoneHandoffThroughTheGate:
    def test_valid_token_logs_in_and_reaches_the_scan_page(self, user):
        token = TimestampSigner().sign(f"{user.pk}:title")
        client = Client()

        response = client.get(f"/ingest/phone-auth/{token}/")

        assert response.status_code == 302
        assert response.url == "/ingest/scan-title/"
        assert client.session["_auth_user_id"] == str(user.pk)
        page = client.get("/ingest/scan-title/")
        assert page.status_code == 200
        assert not _is_gate(page)

    def test_expired_token_is_refused(self, user):
        two_hours_ago = b62_encode(int(time.time()) - 7200)
        with patch.object(
            TimestampSigner, "timestamp", return_value=two_hours_ago
        ):
            token = TimestampSigner().sign(f"{user.pk}:title")

        response = Client().get(f"/ingest/phone-auth/{token}/")

        assert response.status_code == 403

    def test_tampered_token_is_refused(self, user):
        token = TimestampSigner().sign(f"{user.pk}:title") + "x"

        response = Client().get(f"/ingest/phone-auth/{token}/")

        assert response.status_code == 400


class TestSitePasswordCheck:
    def test_warns_without_debug_and_without_a_password(self, settings):
        settings.DEBUG = False
        settings.SITE_PASSWORD = ""

        warnings = check_site_password(None)

        assert [w.id for w in warnings] == ["otzar.W001"]

    def test_silent_with_a_password(self, settings):
        settings.DEBUG = False
        settings.SITE_PASSWORD = "open-sesame"

        assert check_site_password(None) == []

    def test_silent_with_debug(self, settings):
        settings.DEBUG = True
        settings.SITE_PASSWORD = ""

        assert check_site_password(None) == []

    def test_runs_with_the_registered_checks(self, settings):
        settings.DEBUG = False
        settings.SITE_PASSWORD = ""

        messages = run_checks(
            tags=[Tags.security], include_deployment_checks=True
        )

        assert "otzar.W001" in [m.id for m in messages]
