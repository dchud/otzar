"""OCR module: extract bibliographic metadata from title page images via Claude Vision."""

import base64
import json
import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)

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
    "read them carefully even if stylized.\n\n"
    "Return ONLY a JSON object with these 8 keys: "
    "title, subtitle, publisher, place, date, title_romanized, "
    "author, author_romanized. "
    "Use the original Hebrew script (without nikkud) for all values "
    "except date (use Gregorian digits), title_romanized, and "
    "author_romanized (Latin script). "
    "Use null for any field you cannot determine."
)


def _parse_vision_json(text):
    """Parse JSON from vision model response, handling markdown fences and gershayim."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Repair Hebrew gershayim (double quote between Hebrew chars)
        repaired = re.sub(
            r'(?<=[\u0590-\u05FF])"(?=[\u0590-\u05FF])',
            "\u05f4",
            text,
        )
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None


def extract_metadata_from_image(image_bytes):
    """Send a title page image to Claude Vision and extract bibliographic metadata.

    Args:
        image_bytes: Raw image bytes (JPEG or PNG).

    Returns:
        A dict with keys: title, subtitle, publisher, place, date,
        title_romanized, author, author_romanized. Returns None on error.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set")
        return None

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=1024,
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

    text = message.content[0].text.strip()
    result = _parse_vision_json(text)
    if result is None:
        logger.warning("Could not parse Claude Vision response: %.200s", text)
        return None

    return result
