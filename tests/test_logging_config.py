"""Tests for the application logging configuration in otzar.settings.

Django merges its own default LOGGING into ``settings.LOGGING`` at
startup rather than replacing it, so the behavior that matters is what
a real log call produces once that merge has happened -- not what the
LOGGING dict says on its own. These exercise real loggers, real
handlers and real calls.
"""

import io
import logging
import os
import re

import httpx

from sources.marc import extract_marc_records

# A minimal SRU envelope carrying one recordData whose leader mrrc
# cannot parse -- the same failure extract_marc_records catches and
# logs rather than letting propagate, so one malformed record does not
# lose the rest of an SRU response page.
UNPARSEABLE_SRU_XML = """<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>1</numberOfRecords>
  <records>
    <record>
      <recordData>
        <record xmlns="http://www.loc.gov/MARC21/slim">
          <leader>not a valid leader</leader>
        </record>
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>"""


def test_app_logger_levels_follow_debug_setting():
    """catalog/ingest/sources sit at DEBUG under DEBUG=true, INFO otherwise.

    Checks the effective level that resulted from applying
    settings.LOGGING at process startup, not the dict itself -- Django
    merges its own default LOGGING in ahead of it.

    Compares against the DEBUG value read from the environment the
    same way settings.py reads it, not against ``settings.DEBUG``
    directly: pytest-django's test environment forces
    ``settings.DEBUG`` to False for the session (its
    ``--django-debug-mode`` default) after logging has already been
    configured from the real startup value, and that override does
    not reconfigure logging.
    """
    debug_at_startup = os.environ.get("DEBUG", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    expected = logging.DEBUG if debug_at_startup else logging.INFO
    for name in ("catalog", "ingest", "sources"):
        assert logging.getLogger(name).getEffectiveLevel() == expected


def test_httpx_held_at_warning_regardless_of_debug():
    for name in ("httpx", "httpcore"):
        assert logging.getLogger(name).getEffectiveLevel() == logging.WARNING


def test_unparseable_marc_record_logs_a_debug_line(caplog):
    """The record mrrc can't parse is skipped, not silently dropped."""
    with caplog.at_level(logging.DEBUG, logger="sources.marc"):
        count, records = extract_marc_records(UNPARSEABLE_SRU_XML)

    assert count == 1
    assert records == []
    assert any(
        record.name == "sources.marc"
        and record.levelno == logging.DEBUG
        and "could not parse" in record.getMessage()
        for record in caplog.records
    )


def test_httpx_per_request_line_does_not_reach_a_handler():
    """httpx logs one INFO line per request; it must not surface here.

    A handler is attached directly to the httpx logger for this test
    so the assertion is about the level gate suppressing the record,
    not about whether a handler happens to exist downstream.
    """
    stream = io.StringIO()
    probe = logging.StreamHandler(stream)
    logger = logging.getLogger("httpx")
    logger.addHandler(probe)

    def handler(request):
        return httpx.Response(200, json={"ok": True})

    try:
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            client.get("https://example.invalid/probe")
    finally:
        logger.removeHandler(probe)

    assert stream.getvalue() == ""


def test_warning_carries_timestamp_level_and_logger_name():
    """A warning/error must say which module, which level, and when.

    Exercises the real handler and formatter already attached to an
    application logger by swapping its stream for the call, rather
    than building a Formatter in isolation and reading its output.
    """
    handlers = [
        h
        for h in logging.getLogger("ingest").handlers
        if isinstance(h, logging.StreamHandler)
    ]
    assert handlers, "expected a console handler on the ingest logger"
    handler = handlers[0]

    original_stream = handler.stream
    handler.stream = io.StringIO()
    try:
        logging.getLogger("ingest.ocr").warning(
            "test warning for format verification"
        )
        output = handler.stream.getvalue()
    finally:
        handler.stream = original_stream

    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", output)
    assert "WARNING" in output
    assert "ingest.ocr" in output
    assert "test warning for format verification" in output
