"""Settings that apply when DEBUG is false, behind the TLS proxy.

settings.py branches on DEBUG at import time, and the test process has
already imported it with the development environment. The settings
themselves are therefore read in a fresh interpreter with the
production environment; the request-level behavior they produce is
checked in-process with override_settings.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import qrcode
from django.contrib.auth.models import User
from django.test import Client, RequestFactory, override_settings

from otzar.client_ip import client_ip

BASE_DIR = Path(__file__).resolve().parent.parent

PROXY_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

_READ_SETTINGS = """
import json
import django
from django.conf import settings
django.setup()
print(json.dumps({
    "proxy_header": settings.SECURE_PROXY_SSL_HEADER,
    "session_secure": settings.SESSION_COOKIE_SECURE,
    "csrf_secure": settings.CSRF_COOKIE_SECURE,
    "hsts": settings.SECURE_HSTS_SECONDS,
    "ssl_redirect": settings.SECURE_SSL_REDIRECT,
}))
"""

_LOG_REQUEST_ERROR = """
import logging
import django
django.setup()
logging.getLogger("django.request").error("request failed: marker-7f3a")
"""


def _run(code, **env):
    """Run *code* in a fresh interpreter with the given environment.

    python-dotenv does not override variables already set, so values
    passed here win over the developer's .env.
    """
    full_env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "otzar.settings",
        **env,
    }
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=BASE_DIR,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _production(**extra):
    return {
        "DEBUG": "false",
        "SECRET_KEY": "test-production-key-" + "x" * 40,
        **extra,
    }


def test_production_settings_trust_the_proxy_and_secure_cookies():
    result = _run(_READ_SETTINGS, **_production())
    assert result.returncode == 0, result.stderr
    values = json.loads(result.stdout)
    assert values["proxy_header"] == list(PROXY_HEADER)
    assert values["session_secure"] is True
    assert values["csrf_secure"] is True
    assert values["hsts"] == 3600
    assert values["ssl_redirect"] is False


def test_development_settings_leave_cookies_plain():
    result = _run(_READ_SETTINGS, DEBUG="true")
    assert result.returncode == 0, result.stderr
    values = json.loads(result.stdout)
    assert values["proxy_header"] is None
    assert values["session_secure"] is False
    assert values["hsts"] == 0


@pytest.mark.parametrize(
    "secret_key", ["", "django-insecure-dev-only-change-me"]
)
def test_production_refuses_the_fallback_secret_key(secret_key):
    result = _run(_READ_SETTINGS, DEBUG="false", SECRET_KEY=secret_key)
    assert result.returncode != 0
    assert "SECRET_KEY must be set when DEBUG is false" in result.stderr


def test_request_errors_reach_the_console_in_production():
    """With DEBUG false, a django.request error is printed, once."""
    result = _run(_LOG_REQUEST_ERROR, **_production())
    assert result.returncode == 0, result.stderr
    lines = [ln for ln in result.stderr.splitlines() if "marker-7f3a" in ln]
    assert len(lines) == 1
    assert "ERROR django.request" in lines[0]


@override_settings(SECURE_PROXY_SSL_HEADER=PROXY_HEADER)
def test_forwarded_proto_makes_the_request_secure():
    request = RequestFactory().get("/", HTTP_X_FORWARDED_PROTO="https")
    assert request.is_secure()


@override_settings(
    SECURE_PROXY_SSL_HEADER=PROXY_HEADER,
    CSRF_TRUSTED_ORIGINS=[],
    ALLOWED_HOSTS=["otzar.example"],
)
@pytest.mark.django_db
def test_qr_handoff_url_is_https_behind_the_proxy():
    user = User.objects.create_user(username="cataloger", password="pw")
    client = Client()
    client.force_login(user)

    with patch("ingest.views.qrcode.make", wraps=qrcode.make) as make:
        response = client.get(
            "/ingest/qr/",
            HTTP_HOST="otzar.example",
            HTTP_X_FORWARDED_PROTO="https",
        )

    assert response.status_code == 200
    assert make.call_args.args[0].startswith("https://otzar.example/")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    ["/accounts/password_reset/", "/accounts/reset/done/"],
)
def test_password_reset_views_are_not_mounted(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.django_db
def test_password_change_is_open_to_a_non_staff_user(client):
    user = User.objects.create_user(username="cataloger", password="pw")
    client.force_login(user)
    assert client.get("/accounts/password_change/").status_code == 200


class TestClientIp:
    def test_without_a_proxy_the_peer_address_is_used(self):
        request = RequestFactory().get(
            "/", REMOTE_ADDR="198.51.100.7", HTTP_X_FORWARDED_FOR="1.2.3.4"
        )
        assert client_ip(request) == "198.51.100.7"

    @override_settings(SECURE_PROXY_SSL_HEADER=PROXY_HEADER)
    def test_behind_the_proxy_the_last_forwarded_entry_is_used(self):
        # The first entry is whatever the client sent; the last is the
        # address the proxy saw.
        request = RequestFactory().get(
            "/",
            REMOTE_ADDR="172.17.0.1",
            HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.7",
        )
        assert client_ip(request) == "198.51.100.7"

    @override_settings(SECURE_PROXY_SSL_HEADER=PROXY_HEADER)
    def test_behind_the_proxy_without_the_header_the_peer_is_used(self):
        request = RequestFactory().get("/", REMOTE_ADDR="172.17.0.1")
        assert client_ip(request) == "172.17.0.1"
