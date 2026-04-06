import pytest
from django.test import Client

from catalog.models import (
    Author,
    Location,
    Publisher,
    Record,
    Series,
    SeriesVolume,
    Subject,
)


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def sample_data(db):
    """Create enough data to test pagination and counts."""
    author = Author.objects.create(name="Test Author", variant_names=["Alt Name"])
    subject = Subject.objects.create(heading="Test Subject")
    publisher = Publisher.objects.create(name="Test Publisher", place="New York")
    location = Location.objects.create(label="Shelf A")

    series = Series.objects.create(title="Test Series", total_volumes=5)

    records = []
    for i in range(30):
        r = Record.objects.create(
            title=f"Title {i:03d}",
            date_of_publication=1950 + i,
        )
        records.append(r)

    # Link first few records to the author, subject, publisher, location
    for r in records[:10]:
        r.authors.add(author)
        r.subjects.add(subject)
        r.publishers.add(publisher)
        r.locations.add(location)

    # Create series volumes with held/gap indicators
    for i in range(1, 6):
        SeriesVolume.objects.create(
            series=series,
            record=records[i - 1] if i <= 3 else None,
            volume_number=str(i),
            held=i <= 3,  # volumes 1-3 held, 4-5 gaps
        )

    return {
        "author": author,
        "subject": subject,
        "publisher": publisher,
        "location": location,
        "series": series,
        "records": records,
    }


# --- Each browse view returns 200 ---


@pytest.mark.django_db
def test_browse_index(client):
    response = client.get("/browse/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_author_browse_200(client, sample_data):
    response = client.get("/browse/authors/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_title_browse_200(client, sample_data):
    response = client.get("/browse/titles/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_subject_browse_200(client, sample_data):
    response = client.get("/browse/subjects/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_publisher_browse_200(client, sample_data):
    response = client.get("/browse/publishers/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_date_browse_200(client, sample_data):
    response = client.get("/browse/dates/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_location_browse_200(client, sample_data):
    response = client.get("/browse/locations/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_series_browse_200(client, sample_data):
    response = client.get("/browse/series/")
    assert response.status_code == 200


# --- Pagination ---


@pytest.mark.django_db
def test_title_browse_pagination(client, sample_data):
    """30 records with 25 per page means 2 pages."""
    response = client.get("/browse/titles/")
    assert response.status_code == 200
    page_obj = response.context["page_obj"]
    assert page_obj.paginator.num_pages == 2
    assert len(page_obj) == 25

    response2 = client.get("/browse/titles/?page=2")
    assert response2.status_code == 200
    page_obj2 = response2.context["page_obj"]
    assert len(page_obj2) == 5


@pytest.mark.django_db
def test_date_browse_pagination(client, db):
    """Create records across many decades to trigger pagination."""
    for i in range(30):
        Record.objects.create(
            title=f"Date test {i}",
            date_of_publication=1800 + i * 10,
        )
    response = client.get("/browse/dates/")
    assert response.status_code == 200
    page_obj = response.context["page_obj"]
    assert page_obj.paginator.num_pages >= 2


# --- Author browse shows record counts ---


@pytest.mark.django_db
def test_author_browse_shows_record_count(client, sample_data):
    response = client.get("/browse/authors/")
    content = response.content.decode()
    assert "10 records" in content


# --- Series browse shows held/gap counts ---


@pytest.mark.django_db
def test_series_browse_shows_held_gap(client, sample_data):
    response = client.get("/browse/series/")
    content = response.content.decode()
    assert "3 held" in content
    assert "2 gaps" in content
