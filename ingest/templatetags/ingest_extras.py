"""Tag support for the ingest mode bar.

The bar (``_ingest_nav.html``) reads its current route from the
resolver rather than from view context, so no view needs to know it
exists. The pending count follows the same rule: a tag the bar calls
itself, rather than a key every view that includes the bar would have
to remember to pass in.
"""

from django import template

from ingest.models import ScanResult

register = template.Library()


@register.simple_tag
def pending_scan_count():
    """Count of ScanResults awaiting review.

    Every logged-in cataloger sees the same review queue, so the count
    is not scoped to the current user.
    """
    return ScanResult.objects.filter(status="pending").count()
