"""The start-up check against the replicas in the backup bucket.

The bucket is moto, in-process. Litestream does not run here: its local
position is LTX file names written beside the database, and the
replica's position comes from a stand-in for ``litestream ltx``.
"""

import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from django.core.management import CommandError, call_command
from moto import mock_aws

from catalog import backups

BUCKET = "otzar-test-backup"
FIRST = "litestream/db"
REBUILT = "litestream/db-20260925T012537Z"
LATER = "litestream/db-20260926T090000Z"
BASE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def database(tmp_path, monkeypatch):
    """Where the database would be. Tests create it or leave it out."""
    path = tmp_path / "data" / "db.sqlite3"
    path.parent.mkdir()
    monkeypatch.setattr(backups, "database_path", lambda: path)
    return path


@pytest.fixture
def s3(monkeypatch, settings):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    settings.AWS_S3_BACKUP_BUCKET = BUCKET
    settings.AWS_S3_REGION = "us-east-1"
    settings.AWS_S3_ENDPOINT_URL = None
    settings.LITESTREAM_REPLICA_PATH = FIRST
    settings.LITESTREAM_MODE = "replicate"
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def replica(client, path, txid=1):
    key = f"{path}/0000/{txid:016x}-{txid:016x}.ltx"
    client.put_object(Bucket=BUCKET, Key=key, Body=b"ltx")


def on_disk(database, txid=None):
    """The database, and Litestream's record of it at *txid*."""
    database.write_bytes(b"")
    if txid is not None:
        state = database.parent / ".db.sqlite3-litestream" / "ltx" / "0"
        state.mkdir(parents=True)
        (state / f"{txid:016x}-{txid:016x}.ltx").write_bytes(b"")


def check(replica_txid=None):
    out, err = StringIO(), StringIO()
    with patch.object(backups, "replica_txid", return_value=replica_txid):
        call_command("check_replica", stdout=out, stderr=err)
    return out.getvalue() + err.getvalue()


def test_litestream_off_checks_nothing(s3, settings):
    settings.LITESTREAM_MODE = "off"
    assert "Litestream is off" in check()


def test_a_path_no_deployment_writes_is_refused(s3, database, settings):
    settings.LITESTREAM_REPLICA_PATH = "backups/elsewhere"
    with pytest.raises(CommandError, match="not a replica path"):
        check()


def test_the_first_start_finds_an_empty_bucket(s3, database):
    assert "starting a new, empty database" in check()


def test_a_fresh_disk_restores_from_the_current_path(s3, database):
    replica(s3, FIRST)
    assert f"restoring the database from {FIRST}" in check()


def test_a_path_a_rebuild_moved_on_from_is_refused(s3, database):
    """A fresh .env after losing the machine names the first path."""
    replica(s3, FIRST)
    replica(s3, REBUILT)
    with pytest.raises(
        CommandError, match=f"Set LITESTREAM_REPLICA_PATH={REBUILT}"
    ):
        check()


def test_an_empty_path_with_no_database_is_refused(s3, database, settings):
    """Nothing to restore, while a replica exists: starting would serve
    an empty catalog."""
    replica(s3, FIRST)
    settings.LITESTREAM_REPLICA_PATH = LATER
    with pytest.raises(CommandError, match="would serve an empty catalog"):
        check()


def test_a_rebuild_replicates_into_its_new_path(s3, database, settings):
    replica(s3, FIRST)
    settings.LITESTREAM_REPLICA_PATH = REBUILT
    on_disk(database)
    assert f"replicating the database on disk into {REBUILT}" in check()


def test_a_database_behind_its_replica_is_refused(s3, database):
    """As after starting from an older copy of the disk."""
    replica(s3, FIRST, txid=0x0D)
    on_disk(database, txid=0x0C)
    with pytest.raises(CommandError, match="behind its replica"):
        check(replica_txid=0x0D)


@pytest.mark.parametrize("local", [0x0D, 0x0E])
def test_a_database_level_with_or_ahead_of_its_replica_starts(
    s3, database, local
):
    replica(s3, FIRST, txid=0x0D)
    on_disk(database, txid=local)
    assert f"replicating into {FIRST}" in check(replica_txid=0x0D)


def test_an_unknown_position_starts_with_a_warning(s3, database):
    replica(s3, FIRST)
    on_disk(database)
    assert "warning: no replication position recorded (on disk)" in check(
        replica_txid=0x0D
    )


def test_litestream_unable_to_list_starts_with_a_warning(s3, database):
    replica(s3, FIRST)
    on_disk(database, txid=0x0C)
    out, err = StringIO(), StringIO()
    with patch.object(
        backups, "replica_txid", side_effect=backups.BackupError("timeout")
    ):
        call_command("check_replica", stdout=out, stderr=err)
    assert "warning: timeout" in err.getvalue()


def test_restore_only_never_compares_positions(s3, database, settings):
    settings.LITESTREAM_MODE = "restore-only"
    replica(s3, FIRST, txid=0x0D)
    on_disk(database, txid=0x0C)
    assert "restore-only" in check(replica_txid=0x0D)


def test_an_unreadable_bucket_with_no_database_is_refused(
    s3, database, settings
):
    settings.AWS_S3_BACKUP_BUCKET = "no-such-bucket"
    with pytest.raises(CommandError, match="cannot be listed"):
        check()


def test_an_unreadable_bucket_with_a_database_starts_with_a_warning(
    s3, database, settings
):
    settings.AWS_S3_BACKUP_BUCKET = "no-such-bucket"
    on_disk(database, txid=1)
    assert "starting on the database on disk unchecked" in check()


def test_a_path_holding_only_delete_markers_is_not_a_replica(s3):
    s3.put_bucket_versioning(
        Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"}
    )
    replica(s3, FIRST)
    replica(s3, LATER)
    for item in s3.list_objects_v2(Bucket=BUCKET, Prefix=LATER)["Contents"]:
        s3.delete_object(Bucket=BUCKET, Key=item["Key"])

    assert backups.replica_paths(s3, BUCKET) == {FIRST}


@pytest.mark.parametrize(
    ("paths", "newest"),
    [
        (set(), None),
        ({FIRST}, FIRST),
        ({FIRST, REBUILT, LATER}, LATER),
        ({FIRST, "litestream/other"}, FIRST),
    ],
)
def test_newest_replica_path(paths, newest):
    assert backups.newest_replica_path(paths) == newest


def test_local_txid_reads_the_newest_ltx_name(database):
    state = database.parent / ".db.sqlite3-litestream" / "ltx"
    for level, name in [
        ("0", "0000000000000011-0000000000000013.ltx"),
        ("1", "0000000000000001-0000000000000010.ltx"),
        ("0", "notes.txt"),
    ]:
        (state / level).mkdir(parents=True, exist_ok=True)
        (state / level / name).write_bytes(b"")
    assert backups.local_txid(database) == 0x13


def test_replica_txid_reads_litestream_ltx(database, tmp_path):
    listing = (
        "level  min_txid          max_txid          size  created\n"
        "0      0000000000000013  0000000000000013  208   2026-09-25T03:00Z\n"
        "9      0000000000000001  0000000000000012  24271 2026-09-25T01:00Z\n"
    )
    done = subprocess.CompletedProcess([], 0, listing, "")
    with patch("catalog.backups.subprocess.run", return_value=done) as run:
        assert backups.replica_txid(database, tmp_path / "l.yml") == 0x13
    assert run.call_args.args[0][:4] == [
        "litestream",
        "ltx",
        "-config",
        str(tmp_path / "l.yml"),
    ]


def test_replica_txid_of_an_empty_replica_is_none(database, tmp_path):
    done = subprocess.CompletedProcess([], 0, "level  min_txid\n", "")
    with patch("catalog.backups.subprocess.run", return_value=done):
        assert backups.replica_txid(database, tmp_path / "l.yml") is None


def test_the_check_leaves_a_missing_database_missing(tmp_path):
    """It runs before the restore, which skips when a file exists."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "otzar.settings",
        "DATA_DIR": str(tmp_path),
        "LITESTREAM_MODE": "off",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check_replica"],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "db.sqlite3").exists()


# load_dotenv is replaced before settings.py imports it, so a line in a
# developer's .env cannot stand in for the variable under test.
_READ_MODE = """
import json
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False
import django
from django.conf import settings
django.setup()
print(json.dumps(settings.LITESTREAM_MODE))
"""


def _read_mode(mode):
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "otzar.settings"}
    env.pop("LITESTREAM_MODE", None)
    if mode is not None:
        env["LITESTREAM_MODE"] = mode
    return subprocess.run(
        [sys.executable, "-c", _READ_MODE],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.parametrize(
    ("value", "mode"),
    [
        (None, "replicate"),
        ("", "replicate"),
        (" Restore-Only ", "restore-only"),
    ],
)
def test_litestream_mode_is_read_from_the_environment(value, mode):
    result = _read_mode(value)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == mode


def test_an_unknown_litestream_mode_refuses_to_start():
    result = _read_mode("disabled")
    assert result.returncode != 0
    assert "LITESTREAM_MODE is 'disabled'" in result.stderr
