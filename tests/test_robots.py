"""robots.txt and the X-Robots-Tag header."""

import pytest
from django.contrib.auth.models import User
from django.test import Client

NOINDEX = "noindex, nofollow"


@pytest.fixture
def gate(settings):
    settings.SITE_PASSWORD = "open-sesame"


@pytest.mark.django_db
@pytest.mark.usefixtures("gate")
class TestRobots:
    def test_robots_txt_disallows_everything_past_the_gate(self):
        response = Client().get("/robots.txt")

        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/plain")
        assert response.content.decode() == "User-agent: *\nDisallow: /\n"

    def test_gate_page_carries_the_header(self):
        response = Client().get("/")

        assert "This site requires a password" in response.content.decode()
        assert response["X-Robots-Tag"] == NOINDEX

    def test_gated_page_carries_the_header(self):
        client = Client()
        client.force_login(User.objects.create_user(username="alice"))

        response = client.get("/ingest/")

        assert response.status_code == 200
        assert response["X-Robots-Tag"] == NOINDEX

    def test_health_check_carries_the_header(self):
        response = Client().get("/health/")

        assert response.status_code == 200
        assert response["X-Robots-Tag"] == NOINDEX
