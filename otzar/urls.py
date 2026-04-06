from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path

from catalog.home_views import home


def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "detail": str(e)}, status=503)


urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("catalog/", include("catalog.urls")),
    path("ingest/", include("ingest.urls")),
    path("", include("catalog.search_urls")),
    path("browse/", include("catalog.browse_urls")),
]
