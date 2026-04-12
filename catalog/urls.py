from django.urls import path, re_path

from catalog import views

app_name = "catalog"

urlpatterns = [
    path(
        "<str:record_id>/delete/",
        views.delete_record,
        name="delete_record",
    ),
    re_path(
        r"^(?P<record_id>[^/]+)/(?P<slug>[\w-]+)/$",
        views.record_detail,
        name="record_detail",
    ),
    path(
        "<str:record_id>/",
        views.record_detail,
        name="record_detail_no_slug",
    ),
]
