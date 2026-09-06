"""Tests for authority matching and series workflow modules."""

import pytest

from catalog.models import Author, Record, Series, SeriesVolume
from ingest.authority import (
    candidate_author_forms,
    find_author_matches,
    find_candidate_author_matches,
    normalize_for_comparison,
    resolve_candidate_author,
    single_strong_match,
)
from ingest.series_workflow import (
    create_series_volumes,
    detect_series_from_marc,
    find_matching_series,
)


class TestNormalizeForComparison:
    def test_strips_punctuation(self):
        assert normalize_for_comparison('Hello, "World"!') == "hello world!"

    def test_lowercases(self):
        assert normalize_for_comparison("FOO BAR") == "foo bar"

    def test_strips_hebrew_punctuation(self):
        assert normalize_for_comparison("שם׳ הכהן") == "שם הכהן"

    def test_collapses_whitespace(self):
        assert normalize_for_comparison("  foo   bar  ") == "foo bar"

    def test_empty_string(self):
        assert normalize_for_comparison("") == ""

    def test_none_returns_empty(self):
        assert normalize_for_comparison(None) == ""


@pytest.mark.django_db
class TestFindAuthorMatchesExact:
    def test_exact_name_match(self):
        author = Author.objects.create(name="Rashi")
        matches = find_author_matches("Rashi")
        assert len(matches) == 1
        assert matches[0] == (author, "exact")

    def test_no_match(self):
        Author.objects.create(name="Rashi")
        matches = find_author_matches("Rambam")
        assert len(matches) == 0


@pytest.mark.django_db
class TestFindAuthorMatchesRomanized:
    def test_romanized_name_match(self):
        author = Author.objects.create(
            name="ר׳ שלמה יצחקי",
            name_romanized="Rashi",
        )
        matches = find_author_matches("other name", name_romanized="Rashi")
        assert len(matches) == 1
        assert matches[0] == (author, "romanized")


@pytest.mark.django_db
class TestFindAuthorMatchesVariant:
    def test_variant_name_match(self):
        author = Author.objects.create(
            name="Rashi",
            variant_names=["R. Shlomo Yitzhaki", "Shelomo Yishaki"],
        )
        matches = find_author_matches("R. Shlomo Yitzhaki")
        assert len(matches) == 1
        assert matches[0] == (author, "variant")

    def test_variant_match_normalized(self):
        """Variant matching ignores punctuation differences."""
        author = Author.objects.create(
            name="Some Author",
            variant_names=["Shlomo, Yitzhaki"],
        )
        matches = find_author_matches("Shlomo Yitzhaki")
        assert len(matches) == 1
        assert matches[0] == (author, "variant")


@pytest.mark.django_db
class TestFindAuthorNoMatches:
    def test_empty_input(self):
        assert find_author_matches("") == []

    def test_no_authors_in_db(self):
        assert find_author_matches("Rashi") == []


class TestDetectSeriesFromMarc:
    def test_with_series_info(self):
        parsed = {
            "title": "Book Title",
            "series_title": "Library of Jewish thought",
            "series_volume": "vol. 3",
        }
        result = detect_series_from_marc(parsed)
        assert result is not None
        assert result["series_title"] == "Library of Jewish thought"
        assert result["series_volume"] == "vol. 3"

    def test_without_series_info(self):
        parsed = {
            "title": "Book Title",
            "series_title": None,
            "series_volume": None,
        }
        result = detect_series_from_marc(parsed)
        assert result is None

    def test_empty_series_title(self):
        parsed = {
            "title": "Book",
            "series_title": "",
            "series_volume": "vol. 1",
        }
        assert detect_series_from_marc(parsed) is None

    def test_missing_keys(self):
        parsed = {"title": "Book"}
        assert detect_series_from_marc(parsed) is None


@pytest.mark.django_db
class TestFindMatchingSeries:
    def test_exact_match(self):
        series = Series.objects.create(title="Library of Jewish thought")
        result = find_matching_series("Library of Jewish thought")
        assert result == series

    def test_normalized_match(self):
        series = Series.objects.create(title="Library of Jewish thought")
        result = find_matching_series("Library of Jewish Thought")
        assert result == series

    def test_no_match(self):
        Series.objects.create(title="Library of Jewish thought")
        assert find_matching_series("Unrelated Series") is None

    def test_empty_title(self):
        assert find_matching_series("") is None


@pytest.mark.django_db
class TestCreateSeriesVolumes:
    def test_range_spec(self):
        series = Series.objects.create(title="Test Series")
        created = create_series_volumes(series, "1-5")
        assert len(created) == 5
        assert SeriesVolume.objects.filter(series=series).count() == 5
        vol_nums = sorted(sv.volume_number for sv in created)
        assert vol_nums == ["1", "2", "3", "4", "5"]

    def test_all_n_spec(self):
        series = Series.objects.create(title="Test Series")
        created = create_series_volumes(series, "all 3")
        assert len(created) == 3

    def test_list_spec(self):
        series = Series.objects.create(title="Test Series")
        created = create_series_volumes(series, [1, 3, 7])
        assert len(created) == 3
        vol_nums = {sv.volume_number for sv in created}
        assert vol_nums == {"1", "3", "7"}

    def test_with_records_marks_held(self):
        series = Series.objects.create(title="Test Series")
        record = Record.objects.create(title="Vol 2 Book")
        created = create_series_volumes(series, "1-3", records={"2": record})
        assert len(created) == 3
        vol2 = SeriesVolume.objects.get(series=series, volume_number="2")
        vol1 = SeriesVolume.objects.get(series=series, volume_number="1")
        assert vol2.held is True
        assert vol2.record == record
        assert vol1.held is False
        assert vol1.record is None

    def test_no_duplicate_volumes(self):
        series = Series.objects.create(title="Test Series")
        create_series_volumes(series, "1-3")
        created2 = create_series_volumes(series, "1-5")
        # Only 4 and 5 should be new
        assert len(created2) == 2
        assert SeriesVolume.objects.filter(series=series).count() == 5


# The two headings the catalogs send for one person: the Library of
# Congress puts the romanized form in 100$a and the Hebrew in a linked
# 880, the National Library of Israel does the reverse.
LC_AUTHOR = "Shneur Zalman, of Lyady"
NLI_AUTHOR = "שניאור זלמן מלאדי"


def lc_candidate(**overrides):
    """A candidate as the LC path builds it: romanized 100, Hebrew 880."""
    candidate = {
        "title": "Likute amarim (Tanya) /",
        "title_alternate": "לקוטי אמרים",
        "author": f"{LC_AUTHOR}, 1745-1812.",
        "author_alternate": NLI_AUTHOR,
        "source_catalog": "LC",
    }
    candidate.update(overrides)
    return candidate


def nli_candidate(**overrides):
    """A candidate as the NLI path builds it: Hebrew 100, romanized 880."""
    candidate = {
        "title": "לקוטי אמרים",
        "title_alternate": "לקוטי אמרים",
        "author": f"{NLI_AUTHOR}.",
        "author_alternate": LC_AUTHOR,
        "source_catalog": "NLI",
    }
    candidate.update(overrides)
    return candidate


class TestCandidateAuthorForms:
    """What is handed to the matcher decides whether it can hit.

    ``find_author_matches`` compares ``Author.name`` and
    ``Author.name_romanized`` as exact strings, and every Author built
    from a candidate is built from a name that has been through
    ``strip_marc_punctuation``. Handing the matcher the raw MARC heading
    therefore misses the author a previous confirm of the very same
    catalog record created.
    """

    def test_strips_the_marc_punctuation_the_creator_strips(self):
        primary, alternate = candidate_author_forms(
            {"author": "Brown, John Seely.", "author_alternate": None}
        )
        assert primary == "Brown, John Seely"
        assert alternate == ""

    def test_keeps_a_distinct_alternate_script_form(self):
        primary, alternate = candidate_author_forms(lc_candidate())
        assert primary == f"{LC_AUTHOR}, 1745-1812"
        assert alternate == NLI_AUTHOR

    def test_drops_an_alternate_that_repeats_the_primary(self):
        """A Hebrew 100 with no 880 copies itself into the alternate."""
        primary, alternate = candidate_author_forms(
            {"author": NLI_AUTHOR, "author_alternate": NLI_AUTHOR}
        )
        assert primary == NLI_AUTHOR
        assert alternate == ""

    def test_no_author_at_all(self):
        assert candidate_author_forms({}) == ("", "")


@pytest.mark.django_db
class TestFindCandidateAuthorMatches:
    def test_exact_match_is_offered(self):
        author = Author.objects.create(name="Brown, John Seely")
        matches = find_candidate_author_matches(
            {"author": "Brown, John Seely.", "author_alternate": None}
        )
        assert matches == [(author, "exact")]

    def test_romanized_match_is_offered(self):
        """Two Hebrew headings, one romanization, one person.

        The catalogs punctuate the Hebrew differently, so the names are
        not equal as strings; the 880 romanization is what they share.
        """
        author = Author.objects.create(
            name="שניאור זלמן, מלאדי",
            name_romanized=LC_AUTHOR,
        )
        matches = find_candidate_author_matches(nli_candidate())
        assert matches == [(author, "romanized")]

    def test_variant_match_is_offered(self):
        """The Hebrew 880 an earlier LC confirm filed as a variant."""
        author = Author.objects.create(
            name=LC_AUTHOR, variant_names=[NLI_AUTHOR]
        )
        matches = find_candidate_author_matches(
            {"author": f"{NLI_AUTHOR}.", "author_alternate": None}
        )
        assert matches == [(author, "variant")]

    def test_alternate_form_matches_an_existing_name(self):
        """The candidate's 880 is the whole name of an existing author."""
        author = Author.objects.create(name=NLI_AUTHOR)
        matches = find_candidate_author_matches(lc_candidate())
        assert matches == [(author, "exact")]

    def test_no_match_returns_nothing(self):
        Author.objects.create(name="Elliger, Karl")
        assert find_candidate_author_matches(lc_candidate()) == []

    def test_an_author_is_offered_once(self):
        """One author reachable by both forms is still one offer."""
        author = Author.objects.create(
            name=NLI_AUTHOR, name_romanized=LC_AUTHOR
        )
        matches = find_candidate_author_matches(lc_candidate())
        assert [a for a, _ in matches] == [author]

    def test_the_strongest_match_sorts_first(self):
        variant_only = Author.objects.create(
            name="Zalman, Shneur", variant_names=[NLI_AUTHOR]
        )
        exact = Author.objects.create(name=NLI_AUTHOR)
        matches = find_candidate_author_matches(lc_candidate())
        assert [a for a, _ in matches] == [exact, variant_only]


@pytest.mark.django_db
class TestSingleStrongMatch:
    def test_one_exact_match_is_strong(self):
        author = Author.objects.create(name=NLI_AUTHOR)
        matches = find_candidate_author_matches(lc_candidate())
        assert single_strong_match(matches) == author

    def test_one_variant_match_is_not_strong(self):
        Author.objects.create(name=LC_AUTHOR, variant_names=[NLI_AUTHOR])
        matches = find_candidate_author_matches(
            {"author": NLI_AUTHOR, "author_alternate": None}
        )
        assert single_strong_match(matches) is None

    def test_several_matches_are_not_strong(self):
        Author.objects.create(name=NLI_AUTHOR)
        Author.objects.create(name="Zalman, Shneur", name_romanized=LC_AUTHOR)
        matches = find_candidate_author_matches(nli_candidate())
        assert len(matches) == 2
        assert single_strong_match(matches) is None

    def test_no_matches(self):
        assert single_strong_match([]) is None


@pytest.mark.django_db
class TestResolveCandidateAuthor:
    def test_no_author_resolves_to_nothing(self):
        assert resolve_candidate_author({"title": "Untitled"}) is None

    def test_creates_an_author_when_nothing_matches(self):
        author = resolve_candidate_author(lc_candidate())
        assert author.name == f"{LC_AUTHOR}, 1745-1812"
        assert Author.objects.count() == 1

    def test_a_new_author_keeps_the_hebrew_880_as_a_variant(self):
        """A romanized heading with a Hebrew 880 files the Hebrew away.

        Nothing else on the row can hold it, and it is what a confirm
        from the other catalog arrives carrying.
        """
        author = resolve_candidate_author(lc_candidate())
        assert author.variant_names == [NLI_AUTHOR]
        assert author.name_romanized == ""

    def test_a_new_author_keeps_the_880_romanization(self):
        author = resolve_candidate_author(nli_candidate())
        assert author.name == NLI_AUTHOR
        assert author.name_romanized == LC_AUTHOR

    def test_a_single_strong_match_is_reused(self):
        existing = Author.objects.create(name=NLI_AUTHOR)
        assert resolve_candidate_author(lc_candidate()) == existing
        assert Author.objects.count() == 1

    def test_an_ambiguous_match_is_not_taken_silently(self):
        Author.objects.create(name=LC_AUTHOR, variant_names=[NLI_AUTHOR])
        author = resolve_candidate_author(
            {"author": f"{NLI_AUTHOR}.", "author_alternate": None}
        )
        assert author.name == NLI_AUTHOR
        assert Author.objects.count() == 2

    def test_an_explicit_choice_is_used(self):
        chosen = Author.objects.create(name="Zalman, Shneur")
        assert resolve_candidate_author(lc_candidate(), chosen.pk) == chosen
        assert Author.objects.count() == 1

    def test_choosing_an_author_teaches_it_the_candidate_forms(self):
        """The choice states that these headings are one person."""
        chosen = Author.objects.create(name="Zalman, Shneur")
        resolve_candidate_author(lc_candidate(), chosen.pk)
        chosen.refresh_from_db()
        assert f"{LC_AUTHOR}, 1745-1812" in chosen.variant_names
        assert NLI_AUTHOR in chosen.variant_names

    def test_teaching_an_author_is_idempotent(self):
        chosen = Author.objects.create(name="Zalman, Shneur")
        resolve_candidate_author(lc_candidate(), chosen.pk)
        resolve_candidate_author(lc_candidate(), chosen.pk)
        chosen.refresh_from_db()
        assert len(chosen.variant_names) == len(set(chosen.variant_names))

    def test_asking_for_a_new_author_overrides_a_strong_match(self):
        existing = Author.objects.create(name=NLI_AUTHOR)
        author = resolve_candidate_author(lc_candidate(), "new")
        assert author != existing
        assert Author.objects.count() == 2

    def test_a_choice_that_no_longer_exists_falls_back_to_matching(self):
        existing = Author.objects.create(name=NLI_AUTHOR)
        stale = existing.pk + 1000
        assert resolve_candidate_author(lc_candidate(), stale) == existing


@pytest.mark.django_db
class TestCrossCatalogMatching:
    """One person catalogued twice, once from each source.

    Confirming both editions has to leave one Author row, not two.
    """

    def test_lc_then_nli_offers_the_first_row(self):
        first = resolve_candidate_author(lc_candidate())
        matches = find_candidate_author_matches(nli_candidate())
        assert [a for a, _ in matches] == [first]

    def test_nli_then_lc_offers_the_first_row(self):
        first = resolve_candidate_author(nli_candidate())
        matches = find_candidate_author_matches(lc_candidate())
        assert [a for a, _ in matches] == [first]
