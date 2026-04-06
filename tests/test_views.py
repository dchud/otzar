import pytest
from django.test import Client

from catalog.models import Author, Record


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def sample_record(db):
    record = Record.objects.create(
        title="משנה תורה",
        title_romanized="Mishneh Torah",
        subtitle="ספר המדע",
        language="Hebrew",
        date_of_publication=1480,
        notes="First printed edition.",
        source_marc={
            "leader": "00000nam a2200000 a 4500",
            "fields": [
                {"001": "990001"},
                {
                    "245": {
                        "ind1": "1",
                        "ind2": "0",
                        "subfields": [
                            {"a": "משנה תורה /"},
                            {"c": "רמבם."},
                        ],
                    }
                },
            ],
        },
    )
    author = Author.objects.create(name="רמבם", name_romanized="Maimonides")
    record.authors.add(author)
    return record


@pytest.mark.django_db
class TestRecordDetailView:
    def test_record_detail_loads(self, client, sample_record):
        url = f"/catalog/{sample_record.record_id}/{sample_record.slug}/"
        response = client.get(url)
        assert response.status_code == 200

    def test_correct_template_used(self, client, sample_record):
        url = f"/catalog/{sample_record.record_id}/{sample_record.slug}/"
        response = client.get(url)
        assert "catalog/record_detail.html" in [t.name for t in response.templates]

    def test_record_data_displayed(self, client, sample_record):
        url = f"/catalog/{sample_record.record_id}/{sample_record.slug}/"
        response = client.get(url)
        content = response.content.decode()
        assert "משנה תורה" in content
        assert "Mishneh Torah" in content
        assert "Maimonides" in content
        assert "Hebrew" in content
        assert "1480" in content
        assert "First printed edition." in content

    def test_redirect_from_no_slug_url(self, client, sample_record):
        url = f"/catalog/{sample_record.record_id}/"
        response = client.get(url)
        assert response.status_code == 302
        assert sample_record.slug in response["Location"]

    def test_404_for_nonexistent_record(self, client, db):
        response = client.get("/catalog/otzar-ZZZZZZ/some-slug/")
        assert response.status_code == 404

    def test_marc_section_rendered(self, client, sample_record):
        url = f"/catalog/{sample_record.record_id}/{sample_record.slug}/"
        response = client.get(url)
        content = response.content.decode()
        assert "245" in content
        assert "View source MARC" in content
