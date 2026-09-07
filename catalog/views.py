from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import Record, Series, SeriesVolume
from catalog.search import remove_from_index


def record_detail(request, record_id, slug=None):
    """Display a single bibliographic record."""
    try:
        record = Record.objects.prefetch_related(
            "authors",
            "subjects",
            "publishers",
            "locations",
            "external_identifiers",
            "title_page_images",
            Prefetch(
                "series_volumes",
                queryset=SeriesVolume.objects.select_related("series"),
            ),
        ).get(record_id=record_id)
    except Record.DoesNotExist:
        raise Http404("Record not found")

    if slug is None:
        return redirect(
            "catalog:record_detail",
            record_id=record.record_id,
            slug=record.slug or "-",
        )

    # Related: other works by the same author(s)
    author_ids = list(record.authors.values_list("pk", flat=True))
    other_by_author = (
        Record.objects.filter(authors__pk__in=author_ids)
        .exclude(pk=record.pk)
        .distinct()[:10]
        if author_ids
        else Record.objects.none()
    )

    # Related: other records sharing a subject heading, most-shared
    # first. A collection catalogued by subject makes this the more
    # useful list to browse once the series has been exhausted.
    subject_ids = list(record.subjects.values_list("pk", flat=True))
    same_subject = (
        Record.objects.filter(subjects__pk__in=subject_ids)
        .exclude(pk=record.pk)
        .annotate(shared_subjects=Count("subjects", distinct=True))
        .order_by("-shared_subjects")[:10]
        if subject_ids
        else Record.objects.none()
    )

    # The publisher's series this record was issued in. It is a fact
    # about how the book was published rather than membership in a set,
    # so it names the series and stops there: no position, no siblings
    # laid out in order, and no gaps.
    publisher_series = record.series.filter(kind=Series.KIND_IMPRINT)

    # Related: other volumes in the same set. A position under a series
    # since refiled as a publisher's line is skipped rather than shown:
    # the row survives so the correction can be undone, but a sequence
    # nobody completes has no siblings worth laying out.
    series_volumes = record.series_volumes.all()
    sibling_volumes = []
    for sv in series_volumes:
        if not sv.series.is_work_set:
            continue
        siblings = (
            SeriesVolume.objects.filter(series=sv.series)
            .select_related("record")
            .order_by("volume_number")
        )
        sibling_volumes.append(
            {
                "series": sv.series,
                "current_volume": sv.volume_number,
                "volumes": siblings,
            }
        )

    # Parse MARC for tagged display
    marc_fields = []
    if record.source_marc and "fields" in record.source_marc:
        for field in record.source_marc["fields"]:
            if isinstance(field, dict):
                for tag, content in field.items():
                    if isinstance(content, dict):
                        ind1 = content.get("ind1", " ")
                        ind2 = content.get("ind2", " ")
                        subfields = content.get("subfields", [])
                        subfield_parts = []
                        for sf in subfields:
                            if isinstance(sf, dict):
                                for code, val in sf.items():
                                    subfield_parts.append(
                                        {"code": code, "value": val}
                                    )
                        marc_fields.append(
                            {
                                "tag": tag,
                                "ind1": ind1,
                                "ind2": ind2,
                                "subfields": subfield_parts,
                            }
                        )
                    else:
                        marc_fields.append(
                            {
                                "tag": tag,
                                "ind1": " ",
                                "ind2": " ",
                                "subfields": [
                                    {"code": "", "value": str(content)}
                                ],
                            }
                        )

    context = {
        "record": record,
        "other_by_author": other_by_author,
        "same_subject": same_subject,
        "publisher_series": publisher_series,
        "sibling_volumes": sibling_volumes,
        "marc_fields": marc_fields,
    }
    return render(request, "catalog/record_detail.html", context)


@staff_member_required
def delete_record(request, record_id):
    """Delete a record (staff only, POST required)."""
    record = get_object_or_404(Record, record_id=record_id)
    if request.method == "POST":
        remove_from_index(record_id)
        record.delete()
        return redirect("home")
    return redirect(
        "catalog:record_detail", record_id=record_id, slug=record.slug
    )
