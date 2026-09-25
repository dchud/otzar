from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path

from catalog.home_views import home
from catalog.language_views import language_search
from otzar.views import LogoutView, robots_txt


def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception as e:  # noqa: BLE001 - any failure means unhealthy
        return JsonResponse({"status": "error", "detail": str(e)}, status=503)


urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    # Login, logout and password change. django.contrib.auth.urls also
    # mounts the password reset views, and password reset sends email,
    # which is not configured: the form would accept an address and then
    # fail. An administrator resets a forgotten password through the
    # admin. Password change stays because the admin's own change page
    # requires staff status, which cataloging does not.
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(),
        name="login",
    ),
    path(
        "accounts/logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path(
        "accounts/password_change/",
        auth_views.PasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "accounts/password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path("catalog/", include("catalog.urls")),
    path("ingest/", include("ingest.urls")),
    path("", include("catalog.search_urls")),
    path("browse/", include("catalog.browse_urls")),
    path("api/languages/", language_search, name="language_search"),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
