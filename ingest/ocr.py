"""OCR module: extract bibliographic metadata from title page images via Claude Vision."""

import base64
import json
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

# The eight keys a title-page reading produces. The schema below turns
# them into the response format the model is constrained to, so the
# reply arrives as valid JSON with every key present and no repair
# step between the model and the caller. Hebrew title pages are full of
# gershayim (רש״י, תשע״ד), and a quotation mark in a value is only a
# problem when the model has to serialize the reply unaided.
OCR_FIELDS = (
    "title",
    "subtitle",
    "publisher",
    "place",
    "date",
    "title_romanized",
    "author",
    "author_romanized",
)

OCR_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        field: {"anyOf": [{"type": "string"}, {"type": "null"}]}
        for field in OCR_FIELDS
    },
    "required": list(OCR_FIELDS),
    "additionalProperties": False,
}

OCR_PROMPT = (
    "This is a photograph of a Hebrew book title page. "
    "Read ALL the Hebrew text on the page and extract:\n"
    "1. title - the main title (largest text)\n"
    "2. subtitle - secondary title text, if any\n"
    "3. publisher - publisher/printer name\n"
    "4. place - city of publication\n"
    "5. date - year of publication "
    "(convert Hebrew gematria dates to Gregorian)\n"
    "6. title_romanized - the main title transliterated to Latin script "
    "using ALA-LC Hebrew romanization rules:\n"
    '   - \u05e9\u05c1 = "sh", \u05e9\u05c2 = "s"\n'
    '   - \u05d7 = "\u1e25", \u05db (spirant) = "kh", \u05e2 = "\u02bb"\n'
    "   - No distinction for dagesh except \u05e4/\u05e4\u05bc \u2192 f/p\n"
    '   - Article \u05d4 prefix \u2192 "ha-" (hyphenated)\n'
    '   - Vowels per standard: \u05e7\u05de\u05e5 = "a", \u05e6\u05d9\u05e8\u05d4 = "e", \u05d7\u05d5\u05dc\u05dd = "o"\n'
    "7. author - the author's name as printed on the title page "
    "(often introduced by words like \u05de\u05d0\u05ea, \u05de\u05d4\u05e8\u05d1, \u05d7\u05d9\u05d1\u05e8\u05d5, etc.)\n"
    "8. author_romanized - the author's name transliterated to Latin script "
    "using ALA-LC Hebrew romanization rules\n\n"
    "IMPORTANT RULES:\n"
    "- Do NOT add nikkud (vowel points) to Hebrew text. "
    "Write Hebrew words without any diacritical marks.\n"
    "- Preserve the natural RIGHT-TO-LEFT word order of Hebrew text. "
    "The first word in the title should be the rightmost word as printed.\n"
    "- Use null for any field you truly cannot read. "
    "Do NOT guess or hallucinate \u2014 if the text is unclear, return null.\n"
    "- Decorative or ornamental letters are still Hebrew letters \u2014 "
    "read them carefully even if stylized.\n"
    "- Give every value in the original Hebrew script (without nikkud), "
    "except date, which uses Gregorian digits, and title_romanized and "
    "author_romanized, which use Latin script."
)


def extract_metadata_from_image(image_bytes):
    """Read a title page image and return its bibliographic metadata.

    Args:
        image_bytes: Raw image bytes (JPEG or PNG).

    Returns:
        A dict holding every key in ``OCR_FIELDS``, each value a string
        or None. A page the model could read nothing from comes back
        with every value None: that is a reading, and what to do with an
        empty one is the caller's decision. None is returned only when
        the call produced no reading at all \u2014 an API failure, a refusal,
        a reply cut short, or a reply with no text in it \u2014 and the log
        names which.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set")
        return None

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=8192,
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": OCR_RESPONSE_SCHEMA,
                }
            },
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": OCR_PROMPT,
                        },
                    ],
                }
            ],
        )
    except anthropic.APIError as exc:
        logger.exception("Claude Vision API error: %s", exc)
        return None
    except Exception:
        logger.exception("Unexpected error calling Claude Vision API")
        return None

    # The schema binds the answer, not the turn: a reply the model never
    # finished, or declined to give, is outside it.
    if message.stop_reason == "max_tokens":
        logger.error("Claude Vision reply was truncated at the token limit")
        return None
    if message.stop_reason == "refusal":
        logger.error(
            "Claude Vision refused the image: %s", message.stop_details
        )
        return None

    text = next(
        (block.text for block in message.content if block.type == "text"),
        "",
    ).strip()
    if not text:
        logger.error(
            "No text block in Claude Vision response (stop_reason=%s)",
            message.stop_reason,
        )
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.exception(
            "Claude Vision reply is not schema-constrained JSON: %.200s",
            text,
        )
        return None
