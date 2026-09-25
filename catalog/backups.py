"""Dated database snapshots in the backup bucket, and the replica check.

Two mechanisms back up the database. Litestream, started by
``entrypoint.sh``, replicates every change to the bucket within
seconds and keeps seven days of history under
``LITESTREAM_REPLICA_PATH``. This module covers the second: a daily
copy of the whole database, kept longer than Litestream's window, for a
mistake noticed after Litestream's history has moved past it.

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

    Returns the number of new keys seen. Raises BackupError when none
    appears in time.
    """
    from catalog.models import ReplicationProbe

    before = replica_keys(client, bucket, replica_path)
    ReplicationProbe.objects.update_or_create(
        pk=1, defaults={"written_at": timezone.now()}
    )
    deadline = time.monotonic() + timeout
    while True:
        new = replica_keys(client, bucket, replica_path) - before
        if new:
            return len(new)
        if time.monotonic() >= deadline:
            raise BackupError(
                f"no new object under s3://{bucket}/{replica_path}/ within "
                f"{timeout:g}s of a database write; replication has stopped"
            )
        time.sleep(interval)


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
