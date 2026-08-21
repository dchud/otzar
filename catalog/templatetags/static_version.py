"""Static file URLs that change when the file changes."""

import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def versioned_static(path):
    """Return the static URL for *path* with its mtime attached.

    The compiled stylesheet keeps one filename across rebuilds, so a
    browser holding the old bytes goes on using them until someone
    forces a reload -- awkward on a laptop, worse on the phone that is
    half of the scanning workflow. The query string changes whenever the
    file does, which is enough for the browser to fetch it again.

    Falls back to the plain URL when the file cannot be located, which
    covers hashed storage backends that already solve this.
    """
    url = static(path)
    absolute = finders.find(path)
    if not absolute:
        return url
    try:
        stamp = int(os.path.getmtime(absolute))
    except OSError:
        return url
    return f"{url}?v={stamp}"
