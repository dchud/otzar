"""Shared fixtures for end-to-end Playwright tests."""

import os

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
    subject = Subject.objects.create(heading="Information society", source="LC")
    subject2 = Subject.objects.create(heading="Information technology", source="LC")
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


def login(page: Page, live_server, username="testadmin", password="testpass123"):
    """Log in via the login page."""
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/")
