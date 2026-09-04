"""Render stored language codes as language names.

Two display sites hold candidate metadata as plain dicts from session
data rather than as Record instances, so the lookup is a filter rather
than a model property.
"""

from django import template

from catalog import language_codes

register = template.Library()


@register.filter
def language_name(value):
    """Render an ISO 639 code as its English language name."""
    return language_codes.language_name(value)
