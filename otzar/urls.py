from django.contrib import admin
from django.urls import include, path
from catalog.home_views import home

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("catalog/", include("catalog.urls")),
    path("ingest/", include("ingest.urls")),
    path("", include("catalog.search_urls")),
    path("browse/", include("catalog.browse_urls")),
]
