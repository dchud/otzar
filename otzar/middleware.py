import os

from django.http import HttpResponse
from django.middleware.csrf import get_token


class SitePasswordMiddleware:
    """Optional site-wide password gate.

    When SITE_PASSWORD is set in the environment, all public pages require
    the password. Authenticated users (catalogers) bypass the gate.
    The admin and login pages are always accessible.
    """

    EXEMPT_PATHS = ("/admin/", "/accounts/", "/health/")

    def __init__(self, get_response):
        self.get_response = get_response
        self.password = os.environ.get("SITE_PASSWORD", "").strip()

    def __call__(self, request):
        if not self.password:
            return self.get_response(request)

        if request.user.is_authenticated:
            return self.get_response(request)

        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return self.get_response(request)

        if request.session.get("site_password_ok"):
            return self.get_response(request)

        if (
            request.method == "POST"
            and request.POST.get("site_password") == self.password
        ):
            request.session["site_password_ok"] = True
            return self.get_response(request)

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
            "required autofocus>\n"
            '<button type="submit">Enter</button>\n'
            "</form>\n</body>\n</html>",
            status=200,
            content_type="text/html",
        )
