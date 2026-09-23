"""The daily snapshot, the replication check and the backup pings.

The bucket is moto, which intercepts boto3 in-process, so no socket is
opened. Litestream does not run here: a test stands in for it by
putting an object under the replica path, or by not doing so.
"""

import gzip
import json
import sqlite3
from datetime import UTC, datetime
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

import boto3
import httpx
import pytest
from django.core.management import CommandError, call_command
from moto import mock_aws

from catalog import backups
from catalog.models import ReplicationProbe
from otzar.build_info import BuildInfo

BUCKET = "otzar-test-backup"
REPLICA = "litestream/db"
PING = "https://hc-ping.example/uuid"
COMMAND = "catalog.management.commands.snapshot_db"


@pytest.fixture
def database(tmp_path, monkeypatch):
    """A database file with three catalog records, in place of the live
    one. The test database is in memory, and the backup API needs a
    file."""
    path = tmp_path / "data" / "db.sqlite3"
    path.parent.mkdir()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE catalog_record (id INTEGER PRIMARY KEY)")
    conn.executemany("INSERT INTO catalog_record VALUES (?)", [(1,), (2,)])
    conn.commit()
    # Left open with an uncheckpointed write in the WAL, as the running
    # application leaves it; the copy has to include this row.
    conn.execute("INSERT INTO catalog_record VALUES (3)")
    conn.commit()
    monkeypatch.setattr(backups, "database_path", lambda: path)
    yield path
    conn.close()


@pytest.fixture
def s3(monkeypatch, settings):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    settings.AWS_S3_BACKUP_BUCKET = BUCKET
    settings.AWS_S3_REGION = "us-east-1"
    settings.AWS_S3_ENDPOINT_URL = None
    settings.LITESTREAM_REPLICA_PATH = REPLICA
    settings.LITESTREAM_DISABLED = False
    settings.BACKUP_PING_URL = ""
    settings.BUILD_INFO = BuildInfo(commit="abc1234")
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def read(client, key):
    return client.get_object(Bucket=BUCKET, Key=key)["Body"].read()


def keys(client):
    listing = client.list_objects_v2(Bucket=BUCKET)
    return {item["Key"] for item in listing.get("Contents", ())}


def test_snapshot_uploads_database_manifest_and_latest(s3, database):
    now = datetime(2026, 9, 22, 7, 30, tzinfo=UTC)

    snapshot = backups.take_snapshot(s3, BUCKET, now=now)

    prefix = "snapshots/2026/09/22/"
    assert snapshot.key == prefix + "db.sqlite3.gz"
    manifest = json.loads(read(s3, prefix + "manifest.json"))
    assert manifest == {
        "created_at": "2026-09-22T07:30:00+00:00",
        "record_count": 3,
        "commit": "abc1234",
        "key": prefix + "db.sqlite3.gz",
        "bytes": manifest["bytes"],
    }
    assert json.loads(read(s3, "snapshots/latest.json")) == manifest

    restored = database.parent / "restored.sqlite3"
    restored.write_bytes(gzip.decompress(read(s3, snapshot.key)))
    conn = sqlite3.connect(restored)
    assert conn.execute("SELECT count(*) FROM catalog_record").fetchone() == (
        3,
    )
    conn.close()


def test_snapshot_leaves_no_copy_behind(s3, database):
    backups.take_snapshot(s3, BUCKET)

    assert sorted(p.name for p in database.parent.iterdir()) == [
        "db.sqlite3",
        "db.sqlite3-shm",
        "db.sqlite3-wal",
    ]


def test_no_monthly_copy_after_the_first(s3, database):
    backups.take_snapshot(s3, BUCKET, now=datetime(2026, 9, 2, tzinfo=UTC))

    assert not any(key.startswith("monthly/") for key in keys(s3))


def test_dated_keys_are_utc_whatever_the_local_zone(s3, database):
    """10 pm on 28 February in New York is 1 March in UTC, so the copy
    is filed under 1 March and is also the monthly copy for March."""
    evening = datetime(2026, 2, 28, 22, 0, tzinfo=ZoneInfo("America/New_York"))

    backups.take_snapshot(s3, BUCKET, now=evening)

    assert keys(s3) == {
        "snapshots/2026/03/01/db.sqlite3.gz",
        "snapshots/2026/03/01/manifest.json",
        "snapshots/latest.json",
        "monthly/2026/03/db.sqlite3.gz",
        "monthly/2026/03/manifest.json",
    }
    manifest = json.loads(read(s3, "monthly/2026/03/manifest.json"))
    assert manifest["created_at"] == "2026-03-01T03:00:00+00:00"


def litestream_uploads(client):
    """Stand in for a running Litestream: the first wait after the
    probe write finds a new object under the replica path."""

    def sleep(seconds):
        client.put_object(
            Bucket=BUCKET, Key=f"{REPLICA}/ltx/0/0000000000000002.ltx"
        )

    return patch("catalog.backups.time.sleep", side_effect=sleep)


def run(*args):
    out, err = StringIO(), StringIO()
    call_command("snapshot_db", *args, stdout=out, stderr=err)
    return out.getvalue()


@pytest.mark.django_db
def test_command_pings_success_when_both_checks_pass(s3, database, settings):
    settings.BACKUP_PING_URL = PING
    s3.put_object(Bucket=BUCKET, Key=f"{REPLICA}/ltx/0/0000000000000001.ltx")

    with (
        litestream_uploads(s3),
        patch(f"{COMMAND}.httpx.get") as get,
        patch(f"{COMMAND}.httpx.post") as post,
    ):
        out = run()

    get.assert_called_once_with(PING, timeout=10)
    post.assert_not_called()
    assert "3 records" in out
    assert f"s3://{BUCKET}/{REPLICA}/ received a new write" in out
    assert ReplicationProbe.objects.count() == 1


@pytest.mark.django_db
def test_a_replica_that_receives_nothing_is_a_failure(s3, database, settings):
    """Old objects under the replica path do not count: only one that
    appears after the probe write shows Litestream is running."""
    settings.BACKUP_PING_URL = PING
    s3.put_object(Bucket=BUCKET, Key=f"{REPLICA}/ltx/0/0000000000000001.ltx")

    with (
        patch(f"{COMMAND}.httpx.get") as get,
        patch(f"{COMMAND}.httpx.post") as post,
        pytest.raises(CommandError, match="replication has stopped"),
    ):
        run("--replica-timeout", "0")

    get.assert_not_called()
    post.assert_called_once()
    assert post.call_args.args == (PING + "/fail",)
    assert b"replication check failed" in post.call_args.kwargs["content"]
    # The snapshot still went up: one failure does not stop the other.
    assert "snapshots/latest.json" in keys(s3)


@pytest.mark.django_db
def test_a_failed_snapshot_pings_failure(s3, database, settings):
    settings.BACKUP_PING_URL = PING

    with (
        litestream_uploads(s3),
        patch.object(backups, "copy_database", side_effect=OSError("disk")),
        patch(f"{COMMAND}.httpx.get") as get,
        patch(f"{COMMAND}.httpx.post") as post,
        pytest.raises(CommandError, match="snapshot failed: disk"),
    ):
        run()

    get.assert_not_called()
    assert post.call_args.args == (PING + "/fail",)


@pytest.mark.django_db
def test_without_a_ping_url_nothing_is_requested(s3, database):
    with (
        litestream_uploads(s3),
        patch(f"{COMMAND}.httpx.get") as get,
        patch(f"{COMMAND}.httpx.post") as post,
    ):
        run()

    get.assert_not_called()
    post.assert_not_called()


@pytest.mark.django_db
def test_disabled_litestream_skips_the_replication_check(
    s3, database, settings
):
    settings.LITESTREAM_DISABLED = True
    settings.BACKUP_PING_URL = PING

    with patch(f"{COMMAND}.httpx.get") as get:
        out = run("--replica-timeout", "0")

    assert "replication check skipped" in out
    get.assert_called_once_with(PING, timeout=10)
    assert not ReplicationProbe.objects.exists()


def test_no_bucket_is_a_failure(settings):
    settings.AWS_S3_BACKUP_BUCKET = ""
    settings.BACKUP_PING_URL = PING

    with (
        patch(f"{COMMAND}.httpx.post") as post,
        pytest.raises(CommandError, match="AWS_S3_BACKUP_BUCKET"),
    ):
        run()

    assert post.call_args.args == (PING + "/fail",)


@pytest.mark.django_db
def test_an_unreachable_ping_url_is_a_failure(s3, database, settings):
    settings.BACKUP_PING_URL = PING

    with (
        litestream_uploads(s3),
        patch(
            f"{COMMAND}.httpx.get", side_effect=httpx.ConnectError("refused")
        ),
        pytest.raises(CommandError, match="backup ping failed"),
    ):
        run()


@pytest.mark.django_db
def test_a_ping_the_service_rejects_is_a_failure(s3, database, settings):
    """A mistyped check URL answers 404, and that ping counts for
    nothing."""
    settings.BACKUP_PING_URL = PING
    not_found = httpx.Response(404, request=httpx.Request("GET", PING))

    with (
        litestream_uploads(s3),
        patch(f"{COMMAND}.httpx.get", return_value=not_found),
        pytest.raises(CommandError, match="backup ping failed"),
    ):
        run()


@pytest.mark.parametrize(
    ("value", "key"),
    [
        ("2026-09-22", "snapshots/2026/09/22/db.sqlite3.gz"),
        ("2026-03", "monthly/2026/03/db.sqlite3.gz"),
    ],
)
def test_snapshot_dates_name_daily_and_monthly_copies(value, key):
    assert backups.parse_snapshot_date(value) == key


@pytest.mark.parametrize("value", ["2026-9-22x", "yesterday", "2026"])
def test_other_dates_are_refused(value):
    with pytest.raises(ValueError):
        backups.parse_snapshot_date(value)


def test_fetch_snapshot_restores_the_database(s3, database, tmp_path):
    backups.take_snapshot(s3, BUCKET, now=datetime(2026, 9, 1, tzinfo=UTC))
    output = tmp_path / "restore" / "db.sqlite3"
    output.parent.mkdir()

    call_command("fetch_snapshot", "2026-09", "--output", str(output))

    conn = sqlite3.connect(output)
    assert conn.execute("SELECT count(*) FROM catalog_record").fetchone() == (
        3,
    )
    conn.close()
    assert [p.name for p in output.parent.iterdir()] == ["db.sqlite3"]


def test_fetch_snapshot_never_overwrites(s3, database):
    backups.take_snapshot(s3, BUCKET, now=datetime(2026, 9, 2, tzinfo=UTC))

    with pytest.raises(CommandError, match="move it aside"):
        call_command("fetch_snapshot", "2026-09-02")


def test_fetch_snapshot_reports_a_missing_snapshot(s3, tmp_path):
    with pytest.raises(CommandError, match="cannot download"):
        call_command(
            "fetch_snapshot", "2020-01-01", "--output", str(tmp_path / "db")
        )
    assert list(tmp_path.iterdir()) == []
