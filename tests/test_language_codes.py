import pycountry
import pytest
from django.template import Context, Template

from catalog.language_codes import language_name
from catalog.models import Record
from catalog.templatetags.language_names import (
    language_name as language_name_filter,
)


class TestBibliographicCodes:
    """MARC 008/35-37 carries ISO 639-2/B codes.

    pycountry indexes ISO 639-3, where these twenty exist only as a
    ``bibliographic`` alias, so an alpha_3 lookup on its own misses every
    one of them.
    """

    @pytest.mark.parametrize(
        "code,expected",
        [
            ("ger", "German"),
            ("fre", "French"),
            ("dut", "Dutch"),
            ("cze", "Czech"),
            ("per", "Persian"),
            ("chi", "Chinese"),
            ("rum", "Romanian"),
            ("wel", "Welsh"),
            ("baq", "Basque"),
            ("arm", "Armenian"),
            ("ice", "Icelandic"),
            ("geo", "Georgian"),
            ("mac", "Macedonian"),
            ("mao", "Maori"),
            ("bur", "Burmese"),
            ("slo", "Slovak"),
            ("alb", "Albanian"),
            ("tib", "Tibetan"),
        ],
    )
    def test_bibliographic_code(self, code, expected):
        assert language_name(code) == expected

    @pytest.mark.parametrize(
        "bibliographic,terminology",
        [
            ("ger", "deu"),
            ("fre", "fra"),
            ("dut", "nld"),
            ("gre", "ell"),
            ("cze", "ces"),
            ("per", "fas"),
        ],
    )
    def test_both_forms_agree(self, bibliographic, terminology):
        assert language_name(bibliographic) == language_name(terminology)


class TestCatalogCodes:
    @pytest.mark.parametrize(
        "code,expected",
        [
            ("heb", "Hebrew"),
            ("yid", "Yiddish"),
            ("lad", "Ladino"),
            ("jrb", "Judeo-Arabic"),
            ("jpr", "Judeo-Persian"),
            ("sam", "Samaritan Aramaic"),
            ("eng", "English"),
            ("ara", "Arabic"),
            ("rus", "Russian"),
        ],
    )
    def test_catalog_code(self, code, expected):
        assert language_name(code) == expected


class TestObsoleteCodes:
    """Codes withdrawn from MARC, some reassigned by ISO 639-3."""

    @pytest.mark.parametrize(
        "code,expected",
        [
            ("gae", "Scottish Gaelic"),
            ("cam", "Khmer"),
            ("far", "Faroese"),
            ("gag", "Galician"),
            ("gal", "Oromo"),
            ("gua", "Guarani"),
            ("iri", "Irish"),
            ("lan", "Occitan (post 1500)"),
            ("max", "Manx"),
            ("mla", "Malagasy"),
            ("sao", "Samoan"),
            ("sho", "Shona"),
            ("sso", "Southern Sotho"),
            ("tag", "Tagalog"),
            ("taj", "Tajik"),
            ("tar", "Tatar"),
            ("tsw", "Tswana"),
            ("kus", "Kosraean"),
            ("eth", "Geez"),
            ("esp", "Esperanto"),
            ("fri", "Western Frisian"),
            ("mol", "Romanian"),
            ("scc", "Serbian"),
            ("scr", "Croatian"),
            ("snh", "Sinhala"),
            ("swz", "Swati"),
            ("lap", "Sami languages"),
        ],
    )
    def test_obsolete_code(self, code, expected):
        assert language_name(code) == expected

    @pytest.mark.parametrize(
        "code",
        ["gae", "cam", "far", "gag", "gua", "iri", "lan", "tag", "tar"],
    )
    def test_obsolete_code_beats_reassignment(self, code):
        """ISO 639-3 gave these codes to unrelated languages."""
        reassigned = pycountry.languages.get(alpha_3=code)
        assert reassigned is not None
        assert language_name(code) != reassigned.name


class TestNameOverrides:
    @pytest.mark.parametrize(
        "code,expected",
        [
            ("arc", "Aramaic"),
            ("gre", "Greek"),
            ("ell", "Greek"),
        ],
    )
    def test_override(self, code, expected):
        assert language_name(code) == expected


class TestMacrolanguageSuffix:
    """ISO 639-3 tags macrolanguages; ISO 639-2 and MARC do not."""

    @pytest.mark.parametrize(
        "code,expected",
        [
            ("may", "Malay"),
            ("msa", "Malay"),
            ("swa", "Swahili"),
            ("nep", "Nepali"),
            ("ori", "Oriya"),
        ],
    )
    def test_suffix_dropped(self, code, expected):
        assert language_name(code) == expected


class TestCollectiveCodes:
    """ISO 639-5 collective codes are valid in MARC 008/35-37."""

    @pytest.mark.parametrize(
        "code,expected",
        [
            ("sem", "Semitic languages"),
            ("sla", "Slavic languages"),
            ("gem", "Germanic languages"),
            ("ber", "Berber languages"),
        ],
    )
    def test_collective_code(self, code, expected):
        assert language_name(code) == expected


class TestSpecialCodes:
    @pytest.mark.parametrize(
        "code,expected",
        [
            ("mul", "Multiple languages"),
            ("und", "Undetermined"),
            ("zxx", "No linguistic content"),
        ],
    )
    def test_special_code(self, code, expected):
        assert language_name(code) == expected


class TestNormalization:
    @pytest.mark.parametrize("code", ["HEB", "Heb", " heb ", "\theb\n"])
    def test_case_and_whitespace(self, code):
        assert language_name(code) == "Hebrew"

    @pytest.mark.parametrize("code", ["GER", " ger "])
    def test_normalizes_bibliographic_codes_too(self, code):
        assert language_name(code) == "German"


class TestPassthrough:
    def test_unknown_code_kept(self):
        assert language_name("qqq") == "qqq"

    def test_unknown_code_keeps_original_case(self):
        assert language_name("Klingon") == "Klingon"

    def test_unknown_code_trimmed(self):
        assert language_name("  qqq  ") == "qqq"

    def test_empty_string(self):
        assert language_name("") == ""

    def test_whitespace_only(self):
        assert language_name("   ") == ""

    def test_none(self):
        assert language_name(None) == ""


class TestTemplateFilter:
    def test_filter_renders_name(self):
        assert language_name_filter("ger") == "German"

    def test_filter_handles_missing_value(self):
        assert language_name_filter(None) == ""

    def test_filter_in_template(self):
        template = Template(
            "{% load language_names %}{{ code|language_name }}"
        )
        assert template.render(Context({"code": "ger"})) == "German"

    def test_filter_escapes_unknown_value(self):
        template = Template(
            "{% load language_names %}{{ code|language_name }}"
        )
        rendered = template.render(Context({"code": "<b>x</b>"}))
        assert "<b>" not in rendered


@pytest.mark.django_db
class TestLanguageAutosuggest:
    def test_returns_code_and_name(self, client):
        response = client.get("/api/languages/", {"q": "hebrew"})
        assert {"code": "heb", "name": "Hebrew"} in response.json()

    def test_offers_bibliographic_form_of_divergent_codes(self, client):
        response = client.get("/api/languages/", {"q": "greek"})
        results = response.json()
        assert {"code": "gre", "name": "Greek"} in results
        assert not any(result["code"] == "ell" for result in results)

    def test_offers_overridden_name(self, client):
        response = client.get("/api/languages/", {"q": "aramaic"})
        assert {"code": "arc", "name": "Aramaic"} in response.json()


@pytest.mark.django_db
class TestAdminLanguageFilter:
    @pytest.fixture
    def superuser_client(self, client, django_user_model):
        django_user_model.objects.create_superuser(
            username="root", password="rootpass123", email="root@example.com"
        )
        client.login(username="root", password="rootpass123")
        return client

    @pytest.fixture
    def records(self, db):
        return [
            Record.objects.create(title="Ein Buch", language="ger"),
            Record.objects.create(title="A book", language="eng"),
            Record.objects.create(title="Uncoded", language=""),
        ]

    def test_sidebar_lists_names_not_codes(self, superuser_client, records):
        response = superuser_client.get("/admin/catalog/record/")
        body = response.content.decode()
        assert "?language=ger" in body
        assert ">German<" in body
        assert ">English<" in body

    def test_filtering_by_code_narrows_the_list(
        self, superuser_client, records
    ):
        response = superuser_client.get("/admin/catalog/record/?language=ger")
        body = response.content.decode()
        assert "Ein Buch" in body
        assert "A book" not in body
