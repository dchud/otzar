from django.contrib import admin

from catalog.models import (
    Author,
    ExternalIdentifier,
    Location,
    Publisher,
    Record,
    Series,
    SeriesVolume,
    Subject,
    TitlePageImage,
)


class ExternalIdentifierInline(admin.TabularInline):
    model = ExternalIdentifier
    extra = 1


class SeriesVolumeInline(admin.TabularInline):
    model = SeriesVolume
    extra = 1


class TitlePageImageInline(admin.TabularInline):
    model = TitlePageImage
    extra = 0


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = [
        "record_id",
        "title",
        "date_of_publication",
        "source_catalog",
        "created_at",
    ]
    list_filter = ["source_catalog", "language"]
    search_fields = ["title", "title_romanized", "record_id"]
    readonly_fields = ["record_id", "created_at", "updated_at"]
    filter_horizontal = ["authors", "subjects", "publishers", "locations"]
    inlines = [ExternalIdentifierInline, TitlePageImageInline]


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["name", "name_romanized", "viaf_id"]
    search_fields = ["name", "name_romanized", "viaf_id"]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["heading", "heading_romanized", "source"]
    list_filter = ["source"]
    search_fields = ["heading", "heading_romanized"]


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ["name", "name_romanized", "place"]
    search_fields = ["name", "name_romanized", "place"]


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ["title", "title_romanized", "total_volumes", "publisher"]
    search_fields = ["title", "title_romanized"]
    inlines = [SeriesVolumeInline]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["label"]
    search_fields = ["label"]
