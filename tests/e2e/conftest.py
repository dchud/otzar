"""Shared fixtures for end-to-end Playwright tests."""

import os
from unittest.mock import patch

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import pytest
from django.contrib.auth.models import User
from playwright.sync_api import Page

from catalog.models import (
    Author,
    ExternalIdentifier,
    Location,
    Publisher,
    Record,
    Subject,
)
from catalog.search import ensure_fts_table, index_record

# The suite blocks sockets, and the live-server fixture these tests run
# against needs a real one on the loopback interface. Allowing the two
# loopback addresses keeps that working while an outbound call from the
# Python side still fails, which is the reason the block exists.
#
# It does not constrain the browser. Playwright drives it in a separate
# process, so a page that fetches an off-origin asset is invisible here;
# test_asset_delivery.py covers that by aborting off-origin requests
# through the browser context and asserting none were attempted.
_LOOPBACK = ["127.0.0.1", "::1"]


def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.allow_hosts(_LOOPBACK))


@pytest.fixture(autouse=True)
def no_cover_lookup():
    """Keep the confirm path from reaching Open Library.

    ``confirm_scan`` calls ``fetch_cover``, which issues a live GET to
    covers.openlibrary.org. No end-to-end test exercises a live cover
    fetch, so every one of them was paying for a request to a third
    party -- and the ones that remembered to patch it were the only
    thing keeping the rest of the suite polite.

    Patching here rather than per test makes the rule uniform: an
    end-to-end test does not fetch covers over the network. A test that
    needs a stored cover creates a ``RecordCover`` directly instead of
    overriding this fixture.
    """
    with patch("ingest.views.fetch_cover", return_value=None):
        yield


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="testadmin", password="testpass123", is_staff=True
    )


@pytest.fixture
def sample_record(db, staff_user):
    """Create a sample record with related data for browsing/viewing tests."""
    ensure_fts_table()

    author = Author.objects.create(
        name="Brown, John Seely", name_romanized="Brown, John Seely"
    )
    author2 = Author.objects.create(name="Duguid, Paul")
    publisher = Publisher.objects.create(
        name="Harvard Business School Press", place="Boston"
    )
    subject = Subject.objects.create(
        heading="Information society", source="LC"
    )
    subject2 = Subject.objects.create(
        heading="Information technology", source="LC"
    )
    location = Location.objects.create(label="Floor 1, Shelf A")

    record = Record.objects.create(
        title="The social life of information",
        date_of_publication=2000,
        place_of_publication="Boston",
        language="eng",
        source_catalog="LC",
        created_by=staff_user,
    )
    record.authors.add(author, author2)
    record.publishers.add(publisher)
    record.subjects.add(subject, subject2)
    record.locations.add(location)
    ExternalIdentifier.objects.create(
        record=record, identifier_type="ISBN", value="0875847625"
    )
    ExternalIdentifier.objects.create(
        record=record, identifier_type="LCCN", value="99049068"
    )

    index_record(record)
    return record


@pytest.fixture
def german_record(db, staff_user):
    """A record whose language code diverges between ISO 639-2/B and 639-3.

    MARC 008/35-37 says ``ger`` for German, and pycountry finds that only
    under ``bibliographic``, so a lookup that reaches for ``alpha_3``
    alone renders the field blank.
    """
    ensure_fts_table()

    record = Record.objects.create(
        title="Der Zauberberg",
        date_of_publication=1924,
        place_of_publication="Berlin",
        language="ger",
        created_by=staff_user,
    )
    index_record(record)
    return record


def login(
    page: Page, live_server, username="testadmin", password="testpass123"
):
    """Log in via the login page."""
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/")
