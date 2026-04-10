from django.urls import path

from catalog.browse_views import (
    author_browse,
    author_detail,
    browse_index,
    date_browse,
    location_browse,
    place_browse,
    place_detail,
    publisher_browse,
    series_browse,
    subject_browse,
    subject_detail,
    title_browse,
)

urlpatterns = [
    path("", browse_index, name="browse-index"),
    path("authors/", author_browse, name="browse-authors"),
    path("authors/<int:pk>/<slug:slug>/", author_detail, name="author-detail"),
    path("authors/<int:pk>/", author_detail, name="author-detail-no-slug"),
    path("titles/", title_browse, name="browse-titles"),
    path("subjects/", subject_browse, name="browse-subjects"),
    path("subjects/<int:pk>/<slug:slug>/", subject_detail, name="subject-detail"),
    path("subjects/<int:pk>/", subject_detail, name="subject-detail-no-slug"),
    path("publishers/", publisher_browse, name="browse-publishers"),
    path("dates/", date_browse, name="browse-dates"),
    path("locations/", location_browse, name="browse-locations"),
    path("series/", series_browse, name="browse-series"),
    path("places/", place_browse, name="browse-places"),
    path("places/<path:place_name>/", place_detail, name="place-detail"),
]
