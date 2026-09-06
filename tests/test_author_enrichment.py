"""Tests for enriching Author rows from VIAF.

Every test serves VIAF's answers through ``FakeVIAF`` in place of the
HTTP call, so the client, the cache and the throttle all run for real
and nothing reaches the network.
"""

from io import StringIO

import httpx
import pytest
from django.core.management import CommandError, call_command

from catalog.models import Author
from ingest.authority import (
    CONFLICT,
    LINKED,
    UNAVAILABLE,
    VIAF_FORM_LIMIT,
    apply_author_enrichment,
    enrich_author_from_viaf,
)
from sources.viaf import (
    AMBIGUOUS,
    HEADING,
    INCOMPLETE,
    NO_MATCH,
    UNSUPPORTED,
    VARIANT_ONLY,
    VIAFClient,
)
from tests.viaf_fixtures import (
    COHEN_1949,
    COHEN_1955,
    COHEN_PLAIN,
    DOV_BER,
    DOV_BER_ID,
    EMPTY,
    FRADKIN,
    FRADKIN_ID,
    FREIDA,
    FREIDA_ID,
    HESCHEL_DNB,
    PTBNP_SPLIT,
    PTBNP_SPLIT_ID,
    SHNEUR_ZALMAN,
    SHNEUR_ZALMAN_ID,
    FakeVIAF,
    cluster,
    response,
    x400,
)

LC_HEADING = "Shneur Zalman, of Lyady, 1745-1812"
NLI_HEADING = "שניאור זלמן בן ברוך, 1745-1812"
SHORT_HEBREW = "שניאור זלמן מלאדי"

# What VIAF returns for the LC heading, and for the Hebrew one.
LYADY_RESPONSE = response([PTBNP_SPLIT, SHNEUR_ZALMAN, DOV_BER])
HEBREW_RESPONSE = response([FREIDA, FRADKIN, SHNEUR_ZALMAN, DOV_BER])


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any test that lets the client reach for the network."""

    def refuse(url, **kwargs):
        raise AssertionError(f"test reached for the network: {url}")

    monkeypatch.setattr("sources.viaf.httpx.get", refuse)


@pytest.fixture
def viaf(monkeypatch):
    return FakeVIAF().install(monkeypatch)


@pytest.fixture
def client():
    return VIAFClient(delay=0)


@pytest.mark.django_db
class TestEnrichAuthorFromViaf:
    def test_an_lc_heading_links_the_cluster_lc_put_it_in(self, viaf, client):
        author = Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.outcome == LINKED
        assert enrichment.viaf_id == SHNEUR_ZALMAN_ID
        assert enrichment.source_ids == {
            "LC": "n  81144085",
            "J9U": "987007268012305171",
        }
        assert enrichment.detail == f'by heading "{LC_HEADING}" (J9U, LC)'

    def test_a_split_cluster_elsewhere_is_reported_not_taken(
        self, viaf, client
    ):
        author = Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.outcome == LINKED
        assert {c.viaf_id for c, _ in enrichment.matches} == {
            SHNEUR_ZALMAN_ID,
            PTBNP_SPLIT_ID,
        }

    def test_an_nli_heading_links_the_same_cluster(self, viaf, client):
        author = Author.objects.create(name=NLI_HEADING)
        viaf.answer(HEBREW_RESPONSE)

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.outcome == LINKED
        assert enrichment.viaf_id == SHNEUR_ZALMAN_ID
        # The daughter's heading holds every word of his and did not match.
        assert all(c.viaf_id != FREIDA_ID for c, _ in enrichment.matches)

    def test_a_short_hebrew_form_alone_is_only_a_tracing(self, viaf, client):
        author = Author.objects.create(name=SHORT_HEBREW)
        viaf.answer(HEBREW_RESPONSE)

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.outcome == VARIANT_ONLY
        assert enrichment.viaf_id == ""
        assert enrichment.forms == []
        assert [c.viaf_id for c, _ in enrichment.matches] == [SHNEUR_ZALMAN_ID]

    def test_a_romanization_on_the_row_carries_the_match(self, viaf, client):
        """Each form is judged against the heading in its own script."""
        author = Author.objects.create(
            name=SHORT_HEBREW, name_romanized="Shneur Zalman, of Lyady"
        )
        viaf.answer(HEBREW_RESPONSE)

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.outcome == LINKED
        matched = dict((c.viaf_id, m) for c, m in enrichment.matches)[
            SHNEUR_ZALMAN_ID
        ]
        assert matched.tier == HEADING
        assert matched.form == "Shneur Zalman, of Lyady"

    def test_a_recorded_variant_carries_the_match(self, viaf, client):
        """A heading a confirm filed on the row counts as the row's."""
        author = Author.objects.create(
            name=SHORT_HEBREW, variant_names=[LC_HEADING]
        )
        viaf.answer(HEBREW_RESPONSE)

        assert enrich_author_from_viaf(author, client=client).outcome == (
            LINKED
        )

    def test_forms_are_the_catalog_files_headings_first(self, viaf, client):
        author = Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)

        forms = enrich_author_from_viaf(author, client=client).forms

        assert forms[:2] == [NLI_HEADING, SHORT_HEBREW]
        assert "Baʻal ha-Tanya, 1745-1812" in forms
        assert LC_HEADING not in forms
        assert not any("Шнеур" in form for form in forms)
        assert not any(form.startswith("אדמוה״ז") for form in forms)
        assert len(forms) <= VIAF_FORM_LIMIT

    def test_forms_the_row_holds_are_left_out(self, viaf, client):
        author = Author.objects.create(
            name=LC_HEADING, variant_names=[SHORT_HEBREW + "."]
        )
        viaf.answer(LYADY_RESPONSE)

        forms = enrich_author_from_viaf(author, client=client).forms

        assert SHORT_HEBREW not in forms
        assert forms[0] == NLI_HEADING

    def test_forms_are_capped(self, viaf, client, monkeypatch):
        monkeypatch.setattr("ingest.authority.VIAF_FORM_LIMIT", 2)
        author = Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)

        forms = enrich_author_from_viaf(author, client=client).forms

        assert forms == [NLI_HEADING, SHORT_HEBREW]

    def test_a_catalog_file_tracing_elsewhere_is_ambiguous(self, viaf, client):
        rival = cluster(
            FRADKIN_ID,
            headings=[("Shneʾur Zalman ben Shelomoh, mi-Ladi", ["LC"])],
            source_ids={"LC": "n  85158455"},
            x400s=[x400([("a", "Shneur Zalman, of Lyady")], ["LC"])],
        )
        author = Author.objects.create(name=LC_HEADING)
        viaf.answer(response([SHNEUR_ZALMAN, rival]))

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.outcome == AMBIGUOUS
        assert enrichment.viaf_id == ""
        assert FRADKIN_ID in enrichment.detail

    def test_more_clusters_than_seen_is_incomplete(self, viaf, client):
        author = Author.objects.create(name="Cohen, David")
        viaf.answer(response([COHEN_1949, COHEN_PLAIN, COHEN_1955], total=390))

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.outcome == INCOMPLETE
        assert "390" in enrichment.detail

    def test_two_clusters_with_the_heading_are_ambiguous(self, viaf, client):
        author = Author.objects.create(name="Cohen, David")
        viaf.answer(response([COHEN_1949, COHEN_PLAIN, COHEN_1955]))

        assert enrich_author_from_viaf(author, client=client).outcome == (
            AMBIGUOUS
        )

    def test_a_heading_only_another_file_holds_is_unsupported(
        self, viaf, client
    ):
        author = Author.objects.create(
            name="Heschel, Abraham Joshua, 1907-1972"
        )
        viaf.answer(response([HESCHEL_DNB]))

        assert enrich_author_from_viaf(author, client=client).outcome == (
            UNSUPPORTED
        )

    def test_nothing_found_is_no_match(self, viaf, client):
        author = Author.objects.create(name="Nobody, Real")
        viaf.answer(EMPTY, EMPTY)

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.outcome == NO_MATCH
        assert len(viaf.urls) == 2

    def test_viaf_not_answering_is_unavailable_and_retried(self, viaf, client):
        author = Author.objects.create(name="Nobody, Real")
        viaf.answer(httpx.ConnectError("down"), httpx.ConnectError("down"))

        assert enrich_author_from_viaf(author, client=client).outcome == (
            UNAVAILABLE
        )

        viaf.answer(EMPTY, EMPTY)
        assert enrich_author_from_viaf(author, client=client).outcome == (
            NO_MATCH
        )
        assert len(viaf.urls) == 4

    def test_a_different_id_on_the_row_is_a_conflict(self, viaf, client):
        author = Author.objects.create(name=LC_HEADING, viaf_id=DOV_BER_ID)
        viaf.answer(LYADY_RESPONSE)

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.outcome == CONFLICT
        assert DOV_BER_ID in enrichment.detail
        assert SHNEUR_ZALMAN_ID in enrichment.detail
        assert enrichment.forms == []

    def test_the_same_id_on_the_row_is_linked(self, viaf, client):
        author = Author.objects.create(
            name=LC_HEADING, viaf_id=SHNEUR_ZALMAN_ID
        )
        viaf.answer(LYADY_RESPONSE)

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.outcome == LINKED
        assert enrichment.forms[0] == NLI_HEADING

    def test_other_rows_with_the_id_are_reported(self, viaf, client):
        twin = Author.objects.create(
            name=NLI_HEADING, viaf_id=SHNEUR_ZALMAN_ID
        )
        author = Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)

        enrichment = enrich_author_from_viaf(author, client=client)

        assert enrichment.also_linked == [twin]

    def test_a_repeat_lookup_is_answered_from_the_cache(self, viaf, client):
        author = Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)
        enrich_author_from_viaf(author, client=client)
        requests = len(viaf.urls)

        again = enrich_author_from_viaf(author, client=client)

        assert again.outcome == LINKED
        assert len(viaf.urls) == requests


@pytest.mark.django_db
class TestApplyAuthorEnrichment:
    def test_links_the_row_and_records_the_forms(self, viaf, client):
        author = Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)
        enrichment = enrich_author_from_viaf(author, client=client)

        changed = apply_author_enrichment(enrichment)

        author.refresh_from_db()
        assert changed == ["viaf_id", "variant_names"]
        assert author.viaf_id == SHNEUR_ZALMAN_ID
        assert author.variant_names[:2] == [NLI_HEADING, SHORT_HEBREW]
        assert author.name_romanized == ""

    def test_a_hebrew_row_gains_the_lc_heading_as_its_romanization(
        self, viaf, client
    ):
        author = Author.objects.create(name=NLI_HEADING)
        viaf.answer(HEBREW_RESPONSE)
        enrichment = enrich_author_from_viaf(author, client=client)

        changed = apply_author_enrichment(enrichment)

        author.refresh_from_db()
        assert "name_romanized" in changed
        assert author.name_romanized == LC_HEADING
        assert LC_HEADING not in author.variant_names
        assert SHORT_HEBREW in author.variant_names

    def test_an_id_already_on_the_row_is_not_rewritten(self, viaf, client):
        author = Author.objects.create(
            name=LC_HEADING, viaf_id=SHNEUR_ZALMAN_ID
        )
        viaf.answer(LYADY_RESPONSE)

        changed = apply_author_enrichment(
            enrich_author_from_viaf(author, client=client)
        )

        assert changed == ["variant_names"]

    def test_other_outcomes_write_nothing(self, viaf, client):
        author = Author.objects.create(name=SHORT_HEBREW)
        viaf.answer(HEBREW_RESPONSE)

        changed = apply_author_enrichment(
            enrich_author_from_viaf(author, client=client)
        )

        author.refresh_from_db()
        assert changed == []
        assert author.viaf_id == ""
        assert author.variant_names == []

    def test_applying_twice_changes_nothing_the_second_time(
        self, viaf, client
    ):
        author = Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)
        apply_author_enrichment(enrich_author_from_viaf(author, client=client))
        author.refresh_from_db()
        held = list(author.variant_names)

        changed = apply_author_enrichment(
            enrich_author_from_viaf(author, client=client)
        )

        author.refresh_from_db()
        assert changed == []
        assert author.variant_names == held


@pytest.mark.django_db
class TestEnrichAuthorsCommand:
    def run(self, *args):
        out = StringIO()
        call_command("enrich_authors", *args, stdout=out)
        return out.getvalue()

    @pytest.fixture(autouse=True)
    def no_delay(self, monkeypatch):
        monkeypatch.setenv("SRU_REQUEST_DELAY", "0")

    def test_links_unlinked_rows_and_skips_linked_ones(self, viaf):
        Author.objects.create(name="Karo, Joseph", viaf_id="97224401")
        founder = Author.objects.create(name=LC_HEADING)
        nobody = Author.objects.create(name="Nobody, Real")
        # Newest row first: two empty answers for the Latin cascade, then
        # the founder's.
        viaf.answer(EMPTY, EMPTY, LYADY_RESPONSE)

        out = self.run()

        founder.refresh_from_db()
        nobody.refresh_from_db()
        assert founder.viaf_id == SHNEUR_ZALMAN_ID
        assert NLI_HEADING in founder.variant_names
        assert nobody.viaf_id == ""
        assert "Karo" not in out
        assert f"linked to VIAF {SHNEUR_ZALMAN_ID}" in out
        assert "no_match --" in out
        assert "Done: 1 linked, 1 no_match." in out

    def test_dry_run_saves_nothing(self, viaf):
        founder = Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)

        out = self.run("--dry-run")

        founder.refresh_from_db()
        assert founder.viaf_id == ""
        assert founder.variant_names == []
        assert f"would link to VIAF {SHNEUR_ZALMAN_ID}" in out
        assert "would record" in out

    def test_named_rows_are_looked_up_linked_or_not(self, viaf):
        held = Author.objects.create(name=LC_HEADING, viaf_id=DOV_BER_ID)
        Author.objects.create(name="Nobody, Real")
        viaf.answer(LYADY_RESPONSE)

        out = self.run("--author", str(held.pk))

        assert "conflict --" in out
        assert "Nobody" not in out
        held.refresh_from_db()
        assert held.viaf_id == DOV_BER_ID

    def test_an_unknown_id_is_an_error(self, viaf):
        with pytest.raises(CommandError, match="no author with id 12345"):
            self.run("--author", "12345")

    def test_limit_takes_the_newest_rows(self, viaf):
        Author.objects.create(name="Nobody, Real")
        founder = Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)

        out = self.run("--limit", "1")

        founder.refresh_from_db()
        assert founder.viaf_id == SHNEUR_ZALMAN_ID
        assert "Nobody" not in out

    def test_one_client_spaces_every_request(self, viaf, monkeypatch):
        monkeypatch.setenv("SRU_REQUEST_DELAY", "3")
        Author.objects.create(name=LC_HEADING)
        Author.objects.create(name=NLI_HEADING)
        viaf.answer(HEBREW_RESPONSE, LYADY_RESPONSE)

        out = self.run()

        assert len(viaf.urls) == 2
        assert len(viaf.sleeps) == 1
        assert 0 < viaf.sleeps[0] <= 3
        assert "3s between VIAF requests" in out
        assert "6s to 24s of waiting" in out

    def test_rows_sharing_an_id_are_reported(self, viaf):
        twin = Author.objects.create(
            name=NLI_HEADING, viaf_id=SHNEUR_ZALMAN_ID
        )
        Author.objects.create(name=LC_HEADING)
        viaf.answer(LYADY_RESPONSE)

        out = self.run()

        assert f"VIAF {SHNEUR_ZALMAN_ID} is also on #{twin.pk}" in out

    def test_nothing_to_do(self, viaf):
        Author.objects.create(name="Karo, Joseph", viaf_id="97224401")

        out = self.run()

        assert "0 authors to look up" in out
        assert "Done: nothing to look up." in out
