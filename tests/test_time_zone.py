"""The site time zone: where a day begins and ends, and what it does
not change.

TIME_ZONE is read from the environment when settings.py is imported,
and the test process has already imported it, so the setting itself is
read in a fresh interpreter. Day boundaries are checked in-process
with override_settings, which resets Django's current time zone.
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test import override_settings

from ingest.models import APIUsageLog

BASE_DIR = Path(__file__).resolve().parent.parent

NEW_YORK = ZoneInfo("America/New_York")

# load_dotenv is replaced before settings.py imports it, so a TIME_ZONE
# line in a developer's .env cannot stand in for the variable the test
# means to leave unset.
_READ_TIME_ZONE = """
import json
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False
import django
from django.conf import settings
django.setup()
print(json.dumps({"time_zone": settings.TIME_ZONE, "use_tz": settings.USE_TZ}))
"""


def _read_time_zone(time_zone=None):
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "otzar.settings"}
    env.pop("TIME_ZONE", None)
    if time_zone is not None:
        env["TIME_ZONE"] = time_zone
    return subprocess.run(
        [sys.executable, "-c", _READ_TIME_ZONE],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.parametrize("time_zone", [None, ""])
def test_unset_or_empty_time_zone_is_utc(time_zone):
    result = _read_time_zone(time_zone)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"time_zone": "UTC", "use_tz": True}


def test_time_zone_is_read_from_the_environment():
    result = _read_time_zone("America/New_York")
    assert result.returncode == 0, result.stderr
    values = json.loads(result.stdout)
    assert values["time_zone"] == "America/New_York"
    assert values["use_tz"] is True


@pytest.mark.parametrize(
    "time_zone", ["America/New_Yrok", "America/../etc/passwd", "/etc/passwd"]
)
def test_unknown_time_zone_refuses_to_start(time_zone):
    result = _read_time_zone(time_zone)
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert f"TIME_ZONE {time_zone!r} is not a known" in result.stderr


def _log_call_at(user, when):
    row = APIUsageLog.objects.create(
        api="ocr", user=user, input_tokens=1, output_tokens=1
    )
    APIUsageLog.objects.filter(pk=row.pk).update(created_at=when)
    return row


@pytest.fixture
def user(db):
    return User.objects.create_user(username="cataloger", password="pw")


@override_settings(TIME_ZONE="America/New_York")
@pytest.mark.django_db
def test_stored_timestamps_are_utc_whatever_the_site_zone(user):
    # 20:30 in New York on 14 January is 01:30 UTC on the 15th: the
    # stored value carries the UTC date and hour, not the local ones.
    moment = datetime(2026, 1, 14, 20, 30, tzinfo=NEW_YORK)
    row = _log_call_at(user, moment)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT created_at FROM ingest_apiusagelog WHERE id = %s",
            [row.pk],
        )
        (raw,) = cursor.fetchone()

    assert str(raw).startswith("2026-01-15 01:30:00")


class TestDayBoundary:
    """calls_today counts from midnight in the site zone."""

    # 23:59 and 00:01 either side of midnight, New York time, which is
    # 04:59 and 05:01 UTC on the same UTC day.
    BEFORE_MIDNIGHT = datetime(2026, 1, 14, 23, 59, tzinfo=NEW_YORK)
    AFTER_MIDNIGHT = datetime(2026, 1, 15, 0, 1, tzinfo=NEW_YORK)

    def _count_at(self, now):
        with patch("django.utils.timezone.now", return_value=now):
            return APIUsageLog.calls_today()

    @override_settings(TIME_ZONE="America/New_York")
    @pytest.mark.django_db
    def test_a_call_just_before_local_midnight_counts_toward_that_day(
        self, user
    ):
        _log_call_at(user, self.BEFORE_MIDNIGHT)
        still_the_14th = datetime(2026, 1, 14, 23, 59, 30, tzinfo=NEW_YORK)
        assert self._count_at(still_the_14th) == 1

    @override_settings(TIME_ZONE="America/New_York")
    @pytest.mark.django_db
    def test_after_local_midnight_only_the_new_days_calls_count(self, user):
        _log_call_at(user, self.BEFORE_MIDNIGHT)
        _log_call_at(user, self.AFTER_MIDNIGHT)
        now = datetime(2026, 1, 15, 0, 2, tzinfo=NEW_YORK)
        assert self._count_at(now) == 1

    @override_settings(TIME_ZONE="UTC")
    @pytest.mark.django_db
    def test_in_utc_the_same_two_calls_fall_on_one_day(self, user):
        # Both are 15 January in UTC, so neither is cut off by the
        # New York midnight between them.
        _log_call_at(user, self.BEFORE_MIDNIGHT)
        _log_call_at(user, self.AFTER_MIDNIGHT)
        now = datetime(2026, 1, 15, 5, 2, tzinfo=UTC)
        assert self._count_at(now) == 2
