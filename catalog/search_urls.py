from django.urls import path

from catalog.search_views import catalog_search

urlpatterns = [
    path("search/", catalog_search, name="catalog_search"),
]
