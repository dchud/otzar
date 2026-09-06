from django.contrib import admin
from django.db.models import Count

from catalog.language_codes import language_name
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
from catalog.search import reindex_records


def delete_orphans(modeladmin, request, queryset):
    """Delete selected items that have no linked records.

    Nothing here touches the search index: an orphan is an object no
    record links to, so no record's indexed text changes.
    """
    deleted = 0
    for obj in queryset:
        if obj.records.count() == 0:
            obj.delete()
            deleted += 1
    modeladmin.message_user(request, f"Deleted {deleted} orphaned item(s).")


delete_orphans.short_description = (
    "Delete selected items with no linked records"
)


class OrphanFilter(admin.SimpleListFilter):
    title = "record links"
    parameter_name = "orphan"

    def lookups(self, request, model_admin):
        return [
            ("orphan", "No linked records"),
            ("linked", "Has linked records"),
        ]

    def queryset(self, request, queryset):
        qs = queryset.annotate(_record_count=Count("records"))
        if self.value() == "orphan":
            return qs.filter(_record_count=0)
        if self.value() == "linked":
            return qs.filter(_record_count__gt=0)
        return queryset


class LanguageFilter(admin.SimpleListFilter):
    """Filter records by language, listing names rather than codes."""

    title = "language"
    parameter_name = "language"

    def lookups(self, request, model_admin):
        codes = (
            model_admin.get_queryset(request)
            .exclude(language="")
            .values_list("language", flat=True)
            .distinct()
        )
        return sorted(
            ((code, language_name(code)) for code in codes),
            key=lambda pair: pair[1].lower(),
        )

    def queryset(self, request, queryset):
        value = self.value()
        return queryset.filter(language=value) if value else queryset


class IndexedAdmin(admin.ModelAdmin):
    """Admin for a model the search index reads text from.

    The index denormalizes a record's own text together with the names
    of the authors, subjects and publishers it links to, so a write
    through the admin has to reindex every record that draws on the
    object saved or deleted -- otherwise a record edited here keeps its
    old text in search, a deleted one keeps an orphaned entry, and a
    renamed author leaves every one of their records stale.

    The default covers the models a record links to. `Record` itself
    overrides it. Models the index holds no text from, such as
    `Location` and `Series`, do not need this at all.
    """

    def indexed_record_ids(self, obj):
        """Return the ids of records whose indexed text draws on `obj`."""
        return list(obj.records.values_list("record_id", flat=True))

    def save_related(self, request, form, formsets, change):
        # Runs after the many-to-many fields and inlines are saved, so
        # the record is whole by the time it is indexed.
        super().save_related(request, form, formsets, change)
        reindex_records(self.indexed_record_ids(form.instance))

    def delete_model(self, request, obj):
        record_ids = self.indexed_record_ids(obj)
        super().delete_model(request, obj)
        reindex_records(record_ids)

    def delete_queryset(self, request, queryset):
        record_ids = [
            record_id
            for obj in queryset
            for record_id in self.indexed_record_ids(obj)
        ]
        super().delete_queryset(request, queryset)
        reindex_records(record_ids)


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
class RecordAdmin(IndexedAdmin):
    list_display = [
        "record_id",
        "title",
        "date_of_publication",
        "source_catalog",
        "created_at",
    ]
    list_filter = ["source_catalog", LanguageFilter]
    search_fields = [
        "title",
        "title_romanized",
        "record_id",
        "provenance",
        "bookplate_text",
        "dedication_text",
        "stamp_text",
    ]
    readonly_fields = ["record_id", "created_at", "updated_at"]
    filter_horizontal = ["authors", "subjects", "publishers", "locations"]
    inlines = [ExternalIdentifierInline, TitlePageImageInline]

    def indexed_record_ids(self, obj):
        return [obj.record_id]


@admin.register(Author)
class AuthorAdmin(IndexedAdmin):
    list_display = ["name", "name_romanized", "viaf_id", "record_count"]
    search_fields = ["name", "name_romanized", "viaf_id"]
    list_filter = [OrphanFilter]
    actions = [delete_orphans]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_record_count=Count("records"))
        )

    @admin.display(ordering="_record_count", description="Records")
    def record_count(self, obj):
        return obj._record_count


@admin.register(Subject)
class SubjectAdmin(IndexedAdmin):
    list_display = ["heading", "heading_romanized", "source", "record_count"]
    list_filter = ["source", OrphanFilter]
    search_fields = ["heading", "heading_romanized"]
    actions = [delete_orphans]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_record_count=Count("records"))
        )

    @admin.display(ordering="_record_count", description="Records")
    def record_count(self, obj):
        return obj._record_count


@admin.register(Publisher)
class PublisherAdmin(IndexedAdmin):
    list_display = ["name", "name_romanized", "place", "record_count"]
    search_fields = ["name", "name_romanized", "place"]
    list_filter = [OrphanFilter]
    actions = [delete_orphans]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_record_count=Count("records"))
        )

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
        return (
            super()
            .get_queryset(request)
            .annotate(_record_count=Count("records"))
        )

    @admin.display(ordering="_record_count", description="Records")
    def record_count(self, obj):
        return obj._record_count
