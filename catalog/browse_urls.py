from django.urls import path

from catalog.browse_views import (
    author_browse,
    browse_index,
    date_browse,
    location_browse,
    publisher_browse,
    series_browse,
    subject_browse,
    title_browse,
)

urlpatterns = [
    path("", browse_index, name="browse-index"),
    path("authors/", author_browse, name="browse-authors"),
    path("titles/", title_browse, name="browse-titles"),
    path("subjects/", subject_browse, name="browse-subjects"),
    path("publishers/", publisher_browse, name="browse-publishers"),
    path("dates/", date_browse, name="browse-dates"),
    path("locations/", location_browse, name="browse-locations"),
    path("series/", series_browse, name="browse-series"),
]
