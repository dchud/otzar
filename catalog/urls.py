from django.urls import path

from catalog import views

app_name = "catalog"

urlpatterns = [
    path(
        "<str:record_id>/<slug:slug>/",
        views.record_detail,
        name="record_detail",
    ),
    path(
        "<str:record_id>/",
        views.record_detail,
        name="record_detail_no_slug",
    ),
]
