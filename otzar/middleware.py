import hmac

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.http import escape_leading_slashes

# The session key that records a passed gate. The logout view carries
# it over to the session that replaces the one it ends.
SITE_PASSWORD_OK = "site_password_ok"


class RobotsTagMiddleware:
    """Ask search engines not to index or follow any response.

    The catalog has no public audience. The header goes on every
    response, the site password gate page and the health check
    included, so a crawler that reaches any URL is told the same thing.
    It binds only crawlers that honour it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response


class SitePasswordMiddleware:
    """Optional site-wide password gate.

    When settings.SITE_PASSWORD is set, every page requires it,
    including the login pages: the gate's check is a constant-time
    comparison with no database write, so it stands in front of the
    password hash and the lockout bookkeeping that a login attempt
    costs. Authenticated users pass without it.

    Exempt paths are the health check, robots.txt, and the phone
    handoff URL, whose signed token authenticates the phone itself.
    """

    EXEMPT_PATHS = ("/health/", "/robots.txt", "/ingest/phone-auth/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        password = settings.SITE_PASSWORD
        if not password:
            return self.get_response(request)

        if request.user.is_authenticated:
            return self.get_response(request)

        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return self.get_response(request)

        if request.session.get(SITE_PASSWORD_OK):
            return self.get_response(request)

        if request.method == "POST" and hmac.compare_digest(
            request.POST.get("site_password", "").encode(),
            password.encode(),
        ):
            request.session[SITE_PASSWORD_OK] = True
            # The POST was meant for the gate, not for the view
            # underneath, so load that view afresh with a GET. A path
            # starting "//" would read as another host in Location.
            response = HttpResponseRedirect(
                escape_leading_slashes(request.get_full_path())
            )
            response.status_code = 303
            return response

        csrf_token = get_token(request)
        return HttpResponse(
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            '<head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width, initial-scale=1">\n'
            "<title>otzar</title>\n"
            "<style>body{font-family:system-ui;display:flex;justify-content:center;"
            "align-items:center;min-height:100vh;margin:0;background:#f9fafb;"
            "color:#111827}"
            "form{text-align:center}"
            "input{padding:0.5rem;font-size:1rem;margin:0.5rem;"
            "background:#fff;color:#111827;border:1px solid #d1d5db;"
            "border-radius:0.25rem}"
            "button{padding:0.5rem 1rem;font-size:1rem;cursor:pointer;"
            "background:#2563eb;color:#fff;border:none;border-radius:0.25rem}"
            "@media(prefers-color-scheme:dark){"
            "body{background:#111827;color:#f9fafb}"
            "input{background:#1f2937;color:#f9fafb;border-color:#6b7280}"
            "button{background:#3b82f6;color:#fff}"
            "}</style>\n"
            "</head>\n<body>\n"
            '<form method="post">\n'
            "<p>This site requires a password.</p>\n"
            f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">\n'
            '<input type="password" name="site_password" placeholder="Password" '
            'aria-label="Site password" required autofocus>\n'
            '<button type="submit">Enter</button>\n'
            "</form>\n</body>\n</html>",
            status=200,
            content_type="text/html",
        )
