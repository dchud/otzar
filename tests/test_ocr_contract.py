"""Contract tests for the Claude SDK surface the OCR path depends on.

Every other test of ``extract_metadata_from_image`` replaces the
Anthropic client with a ``MagicMock``, which accepts any argument and
returns whatever it is told to. That is the right shape for testing this
project's own logic, and it is blind by construction to the thing most
likely to break it: the SDK changing under us. A renamed parameter or a
moved response attribute passes every one of those tests and fails only
against the real API, in the hands of someone photographing a book.

These tests run the real function against a mocked HTTP transport, so
genuine SDK code builds the request and parses the response. No network
call is made. What they verify is the SDK's contract, not the server's --
a change on Anthropic's side that the SDK still accepts would not be
caught here, and nothing short of a live call would catch it.
"""

import json

import anthropic
import httpx2
import pytest

from ingest.ocr import (
    OCR_FIELDS,
    OCR_RESPONSE_SCHEMA,
    extract_metadata_from_image,
)

SAMPLE = {field: None for field in OCR_FIELDS} | {
    "title": "משנה תורה",
    "title_romanized": "Mishneh Torah",
}


def _reply(body, status=200):
    """Build a transport returning one canned Messages API response."""
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx2.Response(status, json=body)

    return httpx2.MockTransport(handler), seen


def _message(content, stop_reason="end_turn", **extra):
    return {
        "id": "msg_contract",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
        **extra,
    }


@pytest.fixture
def vision(monkeypatch):
    """Patch Anthropic construction to use a caller-supplied transport."""

    def build(transport):
        real = anthropic.Anthropic

        def factory(*args, **kwargs):
            kwargs["http_client"] = httpx2.Client(transport=transport)
            return real(*args, **kwargs)

        monkeypatch.setattr(anthropic, "Anthropic", factory)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return build


def test_schema_reaches_the_wire_under_output_config(vision):
    """The parameter name and nesting the SDK accepts, not a mock's."""
    transport, seen = _reply(
        _message([{"type": "text", "text": json.dumps(SAMPLE)}])
    )
    vision(transport)

    result = extract_metadata_from_image(b"jpeg bytes")

    assert result == SAMPLE
    body = seen["body"]
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["format"]["schema"] == OCR_RESPONSE_SCHEMA
    # The deprecated spelling must not reappear alongside it.
    assert "output_format" not in body


def test_reads_past_a_thinking_block(vision):
    """Thinking models put a reasoning block ahead of the answer."""
    transport, _ = _reply(
        _message(
            [
                {"type": "thinking", "thinking": "reading", "signature": "s"},
                {"type": "text", "text": json.dumps(SAMPLE)},
            ]
        )
    )
    vision(transport)

    assert extract_metadata_from_image(b"jpeg bytes") == SAMPLE


def test_truncated_reply_is_not_treated_as_a_reading(vision):
    transport, _ = _reply(
        _message(
            [{"type": "text", "text": '{"title": "trunc'}],
            stop_reason="max_tokens",
        )
    )
    vision(transport)

    assert extract_metadata_from_image(b"jpeg bytes") is None


def test_refusal_is_not_treated_as_a_reading(vision):
    transport, _ = _reply(
        _message(
            [],
            stop_reason="refusal",
            stop_details={"type": "refusal", "reason": "declined"},
        )
    )
    vision(transport)

    assert extract_metadata_from_image(b"jpeg bytes") is None


def test_api_error_is_caught_by_the_declared_exception(vision):
    """anthropic.APIError must still parent the concrete error types."""
    transport, _ = _reply(
        {
            "type": "error",
            "error": {"type": "rate_limit_error", "message": "slow down"},
        },
        status=429,
    )
    vision(transport)

    assert extract_metadata_from_image(b"jpeg bytes") is None
