from django.urls import path

from ingest import views

urlpatterns = [
    path("", views.manual_entry, name="ingest"),
    path("new/", views.manual_entry, name="manual_entry"),
    path("edit/<str:record_id>/", views.edit_record, name="edit_record"),
    path("scan/", views.isbn_scan, name="isbn_scan"),
    path("isbn-lookup/", views.isbn_lookup_view, name="isbn_lookup"),
]
