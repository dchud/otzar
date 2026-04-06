from django.contrib import admin
from django.db.models import Count

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


def delete_orphans(modeladmin, request, queryset):
    """Delete selected items that have no linked records."""
    deleted = 0
    for obj in queryset:
        if obj.records.count() == 0:
            obj.delete()
            deleted += 1
    modeladmin.message_user(request, f"Deleted {deleted} orphaned item(s).")


delete_orphans.short_description = "Delete selected items with no linked records"


class OrphanFilter(admin.SimpleListFilter):
    title = "record links"
    parameter_name = "orphan"

    def lookups(self, request, model_admin):
        return [("orphan", "No linked records"), ("linked", "Has linked records")]

    def queryset(self, request, queryset):
        qs = queryset.annotate(_record_count=Count("records"))
        if self.value() == "orphan":
            return qs.filter(_record_count=0)
        if self.value() == "linked":
            return qs.filter(_record_count__gt=0)
        return queryset


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
    list_display = ["name", "name_romanized", "viaf_id", "record_count"]
    search_fields = ["name", "name_romanized", "viaf_id"]
    list_filter = [OrphanFilter]
    actions = [delete_orphans]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_record_count=Count("records"))

    @admin.display(ordering="_record_count", description="Records")
    def record_count(self, obj):
        return obj._record_count


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["heading", "heading_romanized", "source", "record_count"]
    list_filter = ["source", OrphanFilter]
    search_fields = ["heading", "heading_romanized"]
    actions = [delete_orphans]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_record_count=Count("records"))

    @admin.display(ordering="_record_count", description="Records")
    def record_count(self, obj):
        return obj._record_count


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ["name", "name_romanized", "place", "record_count"]
    search_fields = ["name", "name_romanized", "place"]
    list_filter = [OrphanFilter]
    actions = [delete_orphans]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_record_count=Count("records"))

    @admin.display(ordering="_record_count", description="Records")
    def record_count(self, obj):
        return obj._record_count


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ["title", "title_romanized", "total_volumes", "publisher"]
    search_fields = ["title", "title_romanized"]
    inlines = [SeriesVolumeInline]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["label", "record_count"]
    search_fields = ["label"]
    list_filter = [OrphanFilter]
    actions = [delete_orphans]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_record_count=Count("records"))

    @admin.display(ordering="_record_count", description="Records")
    def record_count(self, obj):
        return obj._record_count
