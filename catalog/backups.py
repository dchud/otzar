"""Dated database snapshots in the backup bucket, and checks on the replica.

Two mechanisms back up the database. Litestream, started by
``entrypoint.sh``, replicates every change to the bucket within
seconds and keeps seven days of history under
``LITESTREAM_REPLICA_PATH``. This module covers the second: a daily
copy of the whole database, kept longer than Litestream's window, for a
mistake noticed after Litestream's history has moved past it.

It also checks the first: that Litestream uploads a new write and that
the replica restores to the present (``snapshot_db``), and which
replica path is current and whether the database on disk is behind it
(``check_replica``, at every start).

Layout in the backup bucket::

    snapshots/YYYY/MM/DD/db.sqlite3.gz   the copy taken that day
    snapshots/YYYY/MM/DD/manifest.json   what it holds
    snapshots/latest.json                the newest manifest
    monthly/YYYY/MM/db.sqlite3.gz        the copy from the 1st
    monthly/YYYY/MM/manifest.json

Dates in keys are UTC whatever ``TIME_ZONE`` says, so a key names the
same day on every host and in every season. The bucket's lifecycle
rules, not this code, expire ``snapshots/`` and ``monthly/``.
"""

import gzip
import json
import re
import shutil
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.utils import timezone

SNAPSHOT_NAME = "db.sqlite3.gz"
MANIFEST_NAME = "manifest.json"
LATEST_KEY = "snapshots/latest.json"

DAY_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
MONTH_PATTERN = re.compile(r"\d{4}-\d{2}")


class BackupError(Exception):
    """A backup step failed in a way the operator has to hear about."""


def s3_client():
    """Return a boto3 client for the backup bucket.

    Region, endpoint and credentials are the ones the media bucket
    uses, so an S3-compatible stand-in serves both.
    """
    return boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        config=Config(signature_version="s3v4"),
    )


def snapshot_prefix(day: date) -> str:
    return f"snapshots/{day:%Y/%m/%d}/"


def monthly_prefix(day: date) -> str:
    return f"monthly/{day:%Y/%m}/"


def database_path() -> Path:
    return Path(settings.DATABASES["default"]["NAME"])


def copy_database(source: Path, destination: Path) -> int:
    """Copy *source* to *destination* with SQLite's online backup API.

    The backup API copies a consistent state of a WAL database while
    other connections write to it, which a file copy does not. Returns
    the number of catalog records in the copy.
    """
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
            (count,) = dst.execute(
                "SELECT count(*) FROM catalog_record"
            ).fetchone()
        finally:
            dst.close()
    finally:
        src.close()
    return count


def gzip_file(source: Path, destination: Path) -> None:
    with source.open("rb") as raw, gzip.open(destination, "wb") as packed:
        shutil.copyfileobj(raw, packed)


@dataclass(frozen=True)
class Snapshot:
    key: str
    manifest: dict


def take_snapshot(client, bucket: str, now: datetime | None = None):
    """Copy the database, upload it and its manifest, and return both.

    The copy is written beside the database, under ``DATA_DIR``, so it
    lands on the same disk rather than in the container's own
    filesystem, and is removed whether or not the upload succeeds.
    """
    now = (now or timezone.now()).astimezone(UTC)
    database = database_path()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    copy = database.with_name(f"snapshot-{stamp}.sqlite3")
    packed = copy.with_suffix(".sqlite3.gz")

    try:
        record_count = copy_database(database, copy)
        gzip_file(copy, packed)

        prefix = snapshot_prefix(now.date())
        key = prefix + SNAPSHOT_NAME
        build = settings.BUILD_INFO
        manifest = {
            "created_at": now.isoformat(timespec="seconds"),
            "record_count": record_count,
            "commit": build.commit if build else None,
            "key": key,
            "bytes": packed.stat().st_size,
        }
        body = json.dumps(manifest, indent=2).encode()

        client.upload_file(str(packed), bucket, key)
        client.put_object(
            Bucket=bucket,
            Key=prefix + MANIFEST_NAME,
            Body=body,
            ContentType="application/json",
        )
        if now.day == 1:
            monthly = monthly_prefix(now.date())
            for name in (SNAPSHOT_NAME, MANIFEST_NAME):
                client.copy_object(
                    Bucket=bucket,
                    Key=monthly + name,
                    CopySource={"Bucket": bucket, "Key": prefix + name},
                )
        # Written last, so it never names a snapshot that is missing.
        client.put_object(
            Bucket=bucket,
            Key=LATEST_KEY,
            Body=body,
            ContentType="application/json",
        )
    finally:
        copy.unlink(missing_ok=True)
        packed.unlink(missing_ok=True)

    return Snapshot(key=key, manifest=manifest)


def replica_keys(client, bucket: str, replica_path: str) -> set[str]:
    """Return every object key under the replica path."""
    keys = set()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=replica_path + "/"):
        keys.update(item["Key"] for item in page.get("Contents", ()))
    return keys


def newest_object(client, bucket: str, prefix: str):
    """Return the listing entry of the newest object under *prefix*.

    Returns None when there is none. Objects written in the same second
    are ordered by key, which for Litestream's files is the order they
    were written in.
    """
    newest = None
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", ()):
            if newest is None or (item["LastModified"], item["Key"]) > (
                newest["LastModified"],
                newest["Key"],
            ):
                newest = item
    return newest


def latest_manifest(client, bucket: str) -> dict | None:
    """Return the manifest of the newest snapshot, or None if none."""
    try:
        body = client.get_object(Bucket=bucket, Key=LATEST_KEY)["Body"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise
    return json.loads(body.read())


def check_replication(
    client,
    bucket: str,
    replica_path: str,
    *,
    timeout: float,
    interval: float = 2.0,
) -> int:
    """Confirm that Litestream uploads a change made now.

    Writes the ``ReplicationProbe`` row and waits up to *timeout*
    seconds for a key that was not under the replica path before the
    write. Litestream syncs every second, so a running process uploads
    one within a few seconds. Comparing key sets rather than object
    ages makes the result independent of how long the catalog has sat
    unchanged and of any difference between this host's clock and the
    bucket's.

    Returns the moment written into the probe row, which a restored
    copy has to hold. Raises BackupError when no new key appears in
    time.
    """
    from catalog.models import ReplicationProbe

    before = replica_keys(client, bucket, replica_path)
    written_at = timezone.now()
    ReplicationProbe.objects.update_or_create(
        pk=1, defaults={"written_at": written_at}
    )
    deadline = time.monotonic() + timeout
    while True:
        new = replica_keys(client, bucket, replica_path) - before
        if new:
            return written_at
        if time.monotonic() >= deadline:
            raise BackupError(
                f"no new object under s3://{bucket}/{replica_path}/ within "
                f"{timeout:g}s of a database write; replication has stopped"
            )
        time.sleep(interval)


def verify_restore(
    replica_path: str, probe_written_at: datetime, *, timeout: float
) -> int:
    """Restore the replica to a scratch file and check the copy.

    Uses the Litestream binary and ``litestream-config`` from the
    image. The copy has to pass ``PRAGMA integrity_check`` and hold the
    probe write that ``check_replication`` saw uploaded, which shows
    that the whole chain of files in the bucket restores to the present.
    The scratch files sit beside the database, on the same disk, and
    are removed whatever happens. Returns the copy's record count.
    Raises BackupError on any failure.
    """
    database = database_path()
    target = database.with_name("restore-test.sqlite3")
    config = database.with_name("restore-test.yml")
    scratch = [config, target] + [
        target.with_name(target.name + suffix) for suffix in ("-wal", "-shm")
    ]
    for path in scratch:
        path.unlink(missing_ok=True)
    try:
        try:
            with config.open("w") as out:
                subprocess.run(
                    ["litestream-config", replica_path],
                    stdout=out,
                    check=True,
                    timeout=30,
                )
            subprocess.run(
                [
                    "litestream",
                    "restore",
                    "-config",
                    str(config),
                    "-o",
                    str(target),
                    str(database),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "").strip() or f"exit {exc.returncode}"
            raise BackupError(f"litestream restore failed: {detail}") from exc
        except subprocess.TimeoutExpired as exc:
            raise BackupError(
                f"litestream restore took longer than {exc.timeout:g}s"
            ) from exc

        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        try:
            (integrity,) = conn.execute("PRAGMA integrity_check").fetchone()
            probe = conn.execute(
                "SELECT written_at FROM catalog_replicationprobe WHERE id = 1"
            ).fetchone()
            (count,) = conn.execute(
                "SELECT count(*) FROM catalog_record"
            ).fetchone()
        except sqlite3.Error as exc:
            raise BackupError(
                f"the restored copy cannot be read: {exc}"
            ) from exc
        finally:
            conn.close()
    finally:
        for path in scratch:
            path.unlink(missing_ok=True)

    if integrity != "ok":
        raise BackupError(
            f"the restored copy fails integrity_check: {integrity}"
        )
    # Django keeps datetimes in SQLite as UTC text without an offset.
    restored = (
        datetime.fromisoformat(probe[0]).replace(tzinfo=UTC) if probe else None
    )
    if restored != probe_written_at:
        raise BackupError(
            "the restored copy lacks the write the replica received; "
            "the files in the bucket do not restore to the present"
        )
    return count


# The replica paths a deployment writes: litestream/db, and the path
# each rebuild moves replication to. The stamp orders them.
REPLICA_ROOT = "litestream/"
FIRST_REPLICA_PATH = "litestream/db"
REBUILT_REPLICA_PATH = re.compile(r"litestream/db-(\d{8}T\d{6}Z)")
LTX_NAME = re.compile(r"([0-9a-f]{16})-([0-9a-f]{16})\.ltx")


def replica_path_age(path: str) -> str | None:
    """A key that sorts replica paths oldest first, or None for a path
    no deployment writes."""
    if path == FIRST_REPLICA_PATH:
        return ""
    match = REBUILT_REPLICA_PATH.fullmatch(path)
    return match.group(1) if match else None


def replica_paths(client, bucket: str) -> set[str]:
    """Return the paths under ``litestream/`` that hold a current object.

    Read from the keys themselves rather than from grouped prefixes, so
    a path whose objects have all been deleted, leaving only delete
    markers in the versioned bucket, is not counted.
    """
    paths = set()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=REPLICA_ROOT):
        for item in page.get("Contents", ()):
            name = item["Key"][len(REPLICA_ROOT) :].split("/", 1)[0]
            if name:
                paths.add(REPLICA_ROOT + name)
    return paths


def newest_replica_path(paths) -> str | None:
    """The newest of *paths* that a deployment writes, or None."""
    known = [p for p in paths if replica_path_age(p) is not None]
    return max(known, key=replica_path_age, default=None)


def local_txid(database: Path) -> int | None:
    """The newest transaction Litestream recorded for *database* here.

    Read from the names of the LTX files in Litestream's directory
    beside the database, ``<min txid>-<max txid>.ltx``. None when there
    are none.
    """
    state = database.with_name(f".{database.name}-litestream") / "ltx"
    txids = [
        int(match.group(2), 16)
        for path in state.glob("*/*.ltx")
        if (match := LTX_NAME.fullmatch(path.name))
    ]
    return max(txids, default=None)


def replica_txid(database: Path, config: Path) -> int | None:
    """The newest transaction in the replica *config* names for
    *database*, from ``litestream ltx``. None when it holds no files.
    Raises BackupError when Litestream cannot list them."""
    try:
        result = subprocess.run(
            [
                "litestream",
                "ltx",
                "-config",
                str(config),
                "-level",
                "all",
                str(database),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = (getattr(exc, "stderr", "") or "").strip() or str(exc)
        raise BackupError(f"litestream ltx failed: {detail}") from exc
    # A header line, then: level, min_txid, max_txid, size, created.
    txids = []
    for line in result.stdout.splitlines()[1:]:
        columns = line.split()
        if len(columns) >= 3:
            txids.append(int(columns[2], 16))
    return max(txids, default=None)


def parse_snapshot_date(value: str) -> str:
    """Map ``YYYY-MM-DD`` or ``YYYY-MM`` to the snapshot key it names.

    A day names the daily copy under ``snapshots/``; a month names the
    copy under ``monthly/``, taken on the 1st. Returns the database
    key. A date that fits neither form is a ValueError.
    """
    if DAY_PATTERN.fullmatch(value):
        return snapshot_prefix(date.fromisoformat(value)) + SNAPSHOT_NAME
    if MONTH_PATTERN.fullmatch(value):
        month = date.fromisoformat(value + "-01")
        return monthly_prefix(month) + SNAPSHOT_NAME
    raise ValueError(f"{value!r} is neither YYYY-MM-DD nor YYYY-MM")


def fetch_snapshot(client, bucket: str, key: str, destination: Path):
    """Download the snapshot at *key* and unpack it to *destination*.

    Refuses to write over an existing file: the caller moves the
    database it is replacing out of the way first.
    """
    if destination.exists():
        raise BackupError(f"{destination} exists; move it aside first")
    packed = destination.with_name(destination.name + ".download.gz")
    partial = destination.with_name(destination.name + ".partial")
    try:
        try:
            client.download_file(bucket, key, str(packed))
        except ClientError as exc:
            raise BackupError(
                f"cannot download s3://{bucket}/{key}: {exc}"
            ) from exc
        with gzip.open(packed, "rb") as src, partial.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        partial.rename(destination)
    finally:
        packed.unlink(missing_ok=True)
        partial.unlink(missing_ok=True)
