from django.urls import path

from ingest import views

urlpatterns = [
    path("", views.ingest_index, name="ingest"),
    path("new/", views.manual_entry, name="manual_entry"),
    path("select-candidate/", views.select_candidate, name="select_candidate"),
    path("confirm/", views.confirm_candidate, name="confirm_candidate"),
    path("edit/<str:record_id>/", views.edit_record, name="edit_record"),
    path("scan/", views.isbn_scan, name="isbn_scan"),
    path("scan/poll/", views.scan_poll, name="scan_poll"),
    path("isbn-lookup/", views.isbn_lookup_view, name="isbn_lookup"),
    path("authority-check/", views.authority_check, name="authority_check"),
    path("series/<int:series_id>/", views.series_manage, name="series_manage"),
    path("scan-title/", views.title_page_scan, name="title_page_scan"),
    path("upload-title/", views.title_page_upload, name="title_page_upload"),
    path("queue/", views.review_queue, name="review_queue"),
    path("confirm/<int:scan_id>/", views.confirm_scan, name="confirm_scan"),
    path("discard/<int:scan_id>/", views.discard_scan, name="discard_scan"),
    path("qr/", views.qr_code_view, name="qr_code"),
    path("phone-auth/<str:token>/", views.phone_scan_auth, name="phone_scan_auth"),
]
