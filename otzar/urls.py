from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path

from catalog.home_views import home
from catalog.language_views import language_search


def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception as e:  # noqa: BLE001 - any failure means unhealthy
        return JsonResponse({"status": "error", "detail": str(e)}, status=503)


urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    # Login and logout only. django.contrib.auth.urls also mounts the
    # password reset and change views, and password reset sends email,
    # which is not configured: the form would accept an address and then
    # fail. An administrator resets a password through the admin.
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
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
