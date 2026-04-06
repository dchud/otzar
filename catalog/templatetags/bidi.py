import re

from django import template
from django.utils.html import format_html

register = template.Library()

HEBREW_RE = re.compile(r"[\u0590-\u05FF]")


def has_hebrew(text):
    """Check if text contains Hebrew characters."""
    return bool(HEBREW_RE.search(text)) if text else False


@register.filter
def bidi_text(value):
    """Wrap text in a span with appropriate dir attribute.

    Hebrew/Aramaic text gets dir="rtl", other text gets dir="ltr".
    """
    if not value:
        return value
    direction = "rtl" if has_hebrew(str(value)) else "ltr"
    css_class = "text-rtl" if direction == "rtl" else ""
    return format_html(
        '<span dir="{}" class="{}">{}</span>', direction, css_class, value
    )


@register.filter
def bidi_auto(value):
    """Wrap text in a span with dir="auto" for mixed content."""
    if not value:
        return value
    return format_html('<span dir="auto">{}</span>', value)
