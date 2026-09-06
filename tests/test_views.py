import gzip
import re
from pathlib import Path

import pytest
from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles import finders
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
        language="heb",
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
        assert "catalog/record_detail.html" in [
            t.name for t in response.templates
        ]

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


@pytest.mark.django_db
class TestResponseCompression:
    """Dynamic responses are gzipped for clients that accept it.

    Cataloguing happens at the shelves on whatever wifi is there, and
    the pages that matter most there are the largest: a candidate list
    carrying twenty MARC records is mostly repeated markup and repeated
    field tags, which is what gzip removes best.
    """

    def _url(self, record):
        return f"/catalog/{record.record_id}/{record.slug}/"

    def test_gzipped_when_the_client_accepts_it(self, client, sample_record):
        response = client.get(
            self._url(sample_record), headers={"accept-encoding": "gzip"}
        )
        assert response.status_code == 200
        assert response.headers["Content-Encoding"] == "gzip"
        body = gzip.decompress(response.content).decode()
        assert "<!DOCTYPE html>" in body
        assert "Mishneh Torah" in body

    def test_not_gzipped_when_the_client_does_not_accept_it(
        self, client, sample_record
    ):
        response = client.get(self._url(sample_record))
        assert "Content-Encoding" not in response.headers
        assert "<!DOCTYPE html>" in response.content.decode()

    def test_compression_is_worth_the_round_trip(self, client, sample_record):
        plain = client.get(self._url(sample_record)).content
        packed = client.get(
            self._url(sample_record), headers={"accept-encoding": "gzip"}
        ).content
        assert len(packed) < len(plain) / 2

    def test_varies_on_accept_encoding(self, client, sample_record):
        response = client.get(
            self._url(sample_record), headers={"accept-encoding": "gzip"}
        )
        assert "Accept-Encoding" in response.headers["Vary"]

    def test_csrf_token_differs_between_renders(self, client):
        """The property that makes compressing these pages safe.

        Compressing a response that carries a secret alongside
        attacker-influenced text can leak the secret through the
        response length, one guessed character at a time -- the BREACH
        attack. Django masks the CSRF token with a fresh random pad on
        every render, so the token bytes in the HTML never repeat and a
        guess cannot compress against them. If two renders produced the
        same token text that defence would be gone, and compression
        would have to go with it.
        """
        first = client.get("/accounts/login/").content.decode()
        second = client.get("/accounts/login/").content.decode()
        pattern = r'name="csrfmiddlewaretoken" value="([^"]+)"'
        first_tokens = re.findall(pattern, first)
        second_tokens = re.findall(pattern, second)
        assert first_tokens, "expected a CSRF token on the page"
        assert first_tokens != second_tokens


class TestMiddlewareOrder:
    GZIP = "django.middleware.gzip.GZipMiddleware"
    WHITENOISE = "whitenoise.middleware.WhiteNoiseMiddleware"

    def test_gzip_is_installed(self):
        assert self.GZIP in settings.MIDDLEWARE

    def test_gzip_sits_below_whitenoise(self):
        """WhiteNoise answers static requests before gzip is reached.

        WhiteNoise compresses static files once, when they are
        collected, and serves the stored ``.gz``/``.br`` sibling. Gzip
        placed above it would redo that work on every request in every
        worker and throw the result away. Below it, WhiteNoise
        short-circuits the static request and gzip never sees it.
        """
        order = settings.MIDDLEWARE
        assert order.index(self.WHITENOISE) < order.index(self.GZIP)

    def test_gzip_wraps_the_middleware_that_writes_bodies(self):
        """Compression happens last on the way out.

        Anything that edits the response body has to see it
        uncompressed, so gzip must wrap those middleware rather than
        run inside them.
        """
        order = settings.MIDDLEWARE
        gzip_at = order.index(self.GZIP)
        assert gzip_at < order.index(
            "django.middleware.common.CommonMiddleware"
        )
        assert gzip_at < order.index(
            "django.middleware.csrf.CsrfViewMiddleware"
        )
        assert gzip_at < order.index("otzar.middleware.SitePasswordMiddleware")

    def test_static_files_are_compressed_at_collect_time(self):
        """Static bytes are shrunk once, not once per request."""
        backend = settings.STORAGES["staticfiles"]["BACKEND"]
        assert backend == "whitenoise.storage.CompressedStaticFilesStorage"


class TestVendoredScripts:
    """Interactivity is served from this application, not a CDN.

    HTMX and Alpine drive the whole ingest workflow -- barcode
    scanning, queue polling, every htmx swap. Loaded from a third-party
    host they fail silently on a bad connection: the page renders and
    nothing responds. Served from here they share the fate of the page
    that needs them.
    """

    HTMX = "vendor/htmx-2.0.4.min.js"
    ALPINE = "vendor/alpine-3.14.8.min.js"

    def template_files(self):
        base = Path(settings.BASE_DIR)
        roots = [base / "templates"]
        for config in apps.get_app_configs():
            path = Path(config.path)
            if base in path.parents:
                roots.append(path / "templates")
        found = []
        for root in roots:
            if root.is_dir():
                found.extend(sorted(root.rglob("*.html")))
        assert found, "no templates found to check"
        return found

    def test_no_template_loads_assets_from_another_host(self):
        tag = re.compile(r"<(?:script|link)\b[^>]*>", re.I | re.S)
        external = re.compile(
            r"""(?:src|href)\s*=\s*["'](?:[a-z]+:)?//""", re.I
        )
        offenders = []
        for path in self.template_files():
            text = path.read_text(encoding="utf-8")
            for match in tag.finditer(text):
                if external.search(match.group(0)):
                    offenders.append(f"{path.name}: {match.group(0)}")
        assert offenders == [], (
            "templates load scripts or stylesheets from another host: "
            + "; ".join(offenders)
        )

    def test_base_template_references_the_pinned_files(self):
        text = (Path(settings.BASE_DIR) / "templates" / "base.html").read_text(
            encoding="utf-8"
        )
        assert self.HTMX in text
        assert self.ALPINE in text

    def test_vendored_files_are_on_the_static_path(self):
        for path in (self.HTMX, self.ALPINE):
            assert finders.find(path), f"{path} is not a findable static file"

    def test_vendored_files_carry_the_versions_they_are_named_for(self):
        htmx = Path(finders.find(self.HTMX)).read_text(encoding="utf-8")
        alpine = Path(finders.find(self.ALPINE)).read_text(encoding="utf-8")
        assert 'version:"2.0.4"' in htmx
        assert '"3.14.8"' in alpine

    def test_provenance_is_recorded_next_to_the_files(self):
        """An upgrade should be a decision, not an excavation."""
        record = (
            Path(settings.BASE_DIR) / "static" / "vendor" / "SOURCES.md"
        ).read_text(encoding="utf-8")
        for needle in (
            "htmx-2.0.4.min.js",
            "alpine-3.14.8.min.js",
            "https://unpkg.com/htmx.org@2.0.4",
            "https://unpkg.com/alpinejs@3.14.8/dist/cdn.min.js",
        ):
            assert needle in record
