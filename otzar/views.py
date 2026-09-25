from django.contrib.auth import views as auth_views
from django.http import HttpResponse

from otzar.middleware import SITE_PASSWORD_OK

ROBOTS_TXT = "User-agent: *\nDisallow: /\n"


def robots_txt(request):
    return HttpResponse(ROBOTS_TXT, content_type="text/plain")


class LogoutView(auth_views.LogoutView):
    """Log out without closing the site password gate.

    Logging out flushes the session, and the gate's flag with it. The
    shared password is not what logging out revokes, so a session that
    had passed the gate hands the flag to the session that replaces it.
    """

    def post(self, request, *args, **kwargs):
        passed_gate = request.session.get(SITE_PASSWORD_OK, False)
        response = super().post(request, *args, **kwargs)
        if passed_gate:
            request.session[SITE_PASSWORD_OK] = True
        return response
