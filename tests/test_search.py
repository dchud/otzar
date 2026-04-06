import pytest

from catalog.models import Author, Record, Subject
from catalog.search import ensure_fts_table, index_record, search, search_records


@pytest.mark.django_db
class TestFTS5Search:
    @pytest.fixture(autouse=True)
    def setup_fts(self):
        ensure_fts_table()

    def test_search_by_title(self):
        record = Record.objects.create(title="Mishneh Torah")
        index_record(record)
        results = search("Mishneh")
        assert len(results) == 1
        assert results[0][0] == record.record_id

    def test_search_hebrew_title(self):
        record = Record.objects.create(title="משנה תורה")
        index_record(record)
        results = search("משנה")
        assert len(results) == 1

    def test_search_by_romanized_title(self):
        record = Record.objects.create(
            title="משנה תורה", title_romanized="Mishneh Torah"
        )
        index_record(record)
        results = search("Mishneh")
        assert len(results) == 1

    def test_search_by_author(self):
        record = Record.objects.create(title="Guide for the Perplexed")
        author = Author.objects.create(name="רמבם", name_romanized="Maimonides")
        record.authors.add(author)
        index_record(record)
        results = search("Maimonides")
        assert len(results) == 1

    def test_search_by_subject(self):
        record = Record.objects.create(title="Some Book")
        subject = Subject.objects.create(heading="Jewish law")
        record.subjects.add(subject)
        index_record(record)
        results = search("Jewish law")
        assert len(results) == 1

    def test_search_no_results(self):
        results = search("nonexistent")
        assert len(results) == 0

    def test_search_empty_query(self):
        results = search("")
        assert len(results) == 0

    def test_search_records_returns_objects(self):
        record = Record.objects.create(title="Test Book")
        index_record(record)
        records = search_records("Test")
        assert len(records) == 1
        assert records[0].pk == record.pk

    def test_multiple_results_ranked(self):
        r1 = Record.objects.create(title="Torah commentary")
        r2 = Record.objects.create(title="Torah study guide")
        index_record(r1)
        index_record(r2)
        results = search("Torah")
        assert len(results) == 2
