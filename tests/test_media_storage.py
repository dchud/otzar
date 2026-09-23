"""Media storage: the S3 switch, and the S3 path the rest of CI skips.

Everything else in the suite runs on FileSystemStorage (see
``filesystem_media_storage`` in conftest.py). These tests run the S3
backend against moto, which intercepts boto3 in-process, so no socket
is opened.
"""

import json
import os
import subprocess
import sys
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import boto3
import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from moto import mock_aws

from ingest.models import ScanResult

BASE_DIR = Path(__file__).resolve().parent.parent
BUCKET = "otzar-test-media"

_READ_STORAGE = """
import json
import django
from django.conf import settings
django.setup()
print(json.dumps(settings.STORAGES["default"]))
"""


def _storage_settings(**env):
    result = subprocess.run(
        [sys.executable, "-c", _READ_STORAGE],
        cwd=BASE_DIR,
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "otzar.settings",
            **env,
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_without_a_bucket_media_stays_on_the_filesystem():
    storage = _storage_settings(AWS_S3_MEDIA_BUCKET="")
    assert storage["BACKEND"] == (
        "django.core.files.storage.FileSystemStorage"
    )


def test_a_bucket_switches_media_to_private_s3():
    storage = _storage_settings(
        AWS_S3_MEDIA_BUCKET="some-bucket",
        AWS_S3_REGION="us-east-1",
        AWS_S3_ENDPOINT_URL="",
    )
    options = storage["OPTIONS"]
    assert storage["BACKEND"] == "storages.backends.s3.S3Storage"
    assert options["bucket_name"] == "some-bucket"
    assert options["region_name"] == "us-east-1"
    assert options["endpoint_url"] is None
    assert options["file_overwrite"] is False
    assert options["default_acl"] is None
    assert options["querystring_auth"] is True
    assert options["querystring_expire"] == 6 * 60 * 60


def test_an_endpoint_url_reaches_the_backend():
    storage = _storage_settings(
        AWS_S3_MEDIA_BUCKET="some-bucket",
        AWS_S3_ENDPOINT_URL="http://localhost:9000",
    )
    assert storage["OPTIONS"]["endpoint_url"] == "http://localhost:9000"


@pytest.fixture
def s3_media(monkeypatch):
    """The default storage on a moto S3 bucket, configured as settings.py
    configures it."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(
            Bucket=BUCKET
        )
        with override_settings(
            STORAGES={
                "default": {
                    "BACKEND": "storages.backends.s3.S3Storage",
                    "OPTIONS": {
                        "bucket_name": BUCKET,
                        "region_name": "us-east-1",
                        "signature_version": "s3v4",
                        "file_overwrite": False,
                        "default_acl": None,
                        "querystring_auth": True,
                        "querystring_expire": 6 * 60 * 60,
                    },
                },
                "staticfiles": {
                    "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
                },
            }
        ):
            yield default_storage


def test_save_open_delete_round_trip(s3_media):
    name = s3_media.save("staging/2026/01/02/a.jpg", ContentFile(b"jpeg"))
    assert name == "staging/2026/01/02/a.jpg"

    with s3_media.open(name, "rb") as f:
        assert f.read() == b"jpeg"

    s3_media.delete(name)
    assert not s3_media.exists(name)


def test_a_name_clash_gets_a_new_name_rather_than_overwriting(s3_media):
    first = s3_media.save("staging/x.jpg", ContentFile(b"one"))
    second = s3_media.save("staging/x.jpg", ContentFile(b"two"))

    assert second != first
    with s3_media.open(first, "rb") as f:
        assert f.read() == b"one"


def test_url_is_presigned_for_six_hours(s3_media):
    name = s3_media.save("title-pages/2026/01/02/b.jpg", ContentFile(b"x"))

    url = urlparse(s3_media.url(name))
    query = parse_qs(url.query)

    assert url.scheme == "https"
    assert BUCKET in url.netloc or url.path.startswith(f"/{BUCKET}/")
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert query["X-Amz-Expires"] == ["21600"]


@pytest.mark.django_db
def test_staging_sweep_removes_orphans_from_s3(s3_media):
    """The orphan half of the sweep finds and deletes S3 objects.

    A sweep that walked MEDIA_ROOT would find no staging directory and
    report nothing, so this is the test that the sweep goes through the
    storage API.
    """
    orphan = s3_media.save("staging/2026/01/02/orphan.jpg", ContentFile(b"o"))
    held = s3_media.save("staging/2026/01/02/held.jpg", ContentFile(b"h"))
    confirmed = s3_media.save(
        "title-pages/2026/01/02/kept.jpg", ContentFile(b"k")
    )
    ScanResult.objects.create(scan_type="ocr", status="pending", image=held)

    # Objects cannot be backdated in S3, so the sweep runs later instead.
    later = timezone.now() + timedelta(days=31)
    with patch(
        "ingest.management.commands.cleanup_staging.timezone.now",
        return_value=later,
    ):
        out = StringIO()
        call_command(
            "cleanup_staging", "--apply", stdout=out, stderr=StringIO()
        )

    assert f"orphan {orphan}" in out.getvalue()
    assert not s3_media.exists(orphan)
    assert s3_media.exists(held)
    assert s3_media.exists(confirmed)


@pytest.mark.django_db
def test_staging_sweep_leaves_recent_orphans_on_s3(s3_media):
    orphan = s3_media.save("staging/2026/01/02/new.jpg", ContentFile(b"n"))

    call_command(
        "cleanup_staging", "--apply", stdout=StringIO(), stderr=StringIO()
    )

    assert s3_media.exists(orphan)
