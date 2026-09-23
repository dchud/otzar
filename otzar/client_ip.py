"""The address a request came from, as the login throttle sees it.

Behind the reverse proxy every request arrives from the proxy's
address, so ``REMOTE_ADDR`` names the proxy and a lockout keyed on it
would lock out every user at once. The proxy (Caddy) records the
address it received the connection from as the last entry of
``X-Forwarded-For``. Entries before it were supplied by the client and
can say anything, so only the last one is trusted.

The header is read only when ``SECURE_PROXY_SSL_HEADER`` is set, which
is the setting that already declares the site sits behind a proxy.
Without a proxy the header is entirely client-supplied, and
``REMOTE_ADDR`` is the real peer.
"""

from django.conf import settings


def client_ip(request):
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        last = forwarded.rsplit(",", 1)[-1].strip()
        if last:
            return last
    return request.META.get("REMOTE_ADDR")
