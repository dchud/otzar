import re

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from catalog.models import Author, Location, Publisher, Record, Series, Subject

ITEMS_PER_PAGE = 25

HEBREW_RE = re.compile(r"[\u0590-\u05FF]")


def _paginate(request, queryset, per_page=ITEMS_PER_PAGE):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page")
    return paginator.get_page(page_number)


def browse_index(request):
    return render(request, "catalog/browse/index.html")


def author_browse(request):
    authors = (
        Author.objects.annotate(record_count=Count("records"))
        .filter(record_count__gt=0)
        .order_by("name")
    )
    page_obj = _paginate(request, authors)
    return render(request, "catalog/browse/authors.html", {"page_obj": page_obj})


def title_browse(request):
    """List records by title, Hebrew-script titles first, then Latin."""
    hebrew_records = (
        Record.objects.filter(title__regex=r"[\u0590-\u05FF]")
        .order_by("title")
        .values_list("pk", flat=True)
    )
    latin_records = (
        Record.objects.exclude(title__regex=r"[\u0590-\u05FF]")
        .order_by("title")
        .values_list("pk", flat=True)
    )
    # Combine the two ordered querysets by pk ordering
    ordered_pks = list(hebrew_records) + list(latin_records)

    # Use a single queryset preserving the ordering
    if ordered_pks:
        from django.db.models import Case, Value, When

        ordering = Case(
            *[When(pk=pk, then=Value(i)) for i, pk in enumerate(ordered_pks)]
        )
        records = Record.objects.filter(pk__in=ordered_pks).order_by(ordering)
    else:
        records = Record.objects.none()

    page_obj = _paginate(request, records)
    return render(request, "catalog/browse/titles.html", {"page_obj": page_obj})


def subject_browse(request):
    subjects = (
        Subject.objects.annotate(record_count=Count("records"))
        .filter(record_count__gt=0)
        .order_by("heading")
    )
    page_obj = _paginate(request, subjects)
    return render(request, "catalog/browse/subjects.html", {"page_obj": page_obj})


def publisher_browse(request):
    publishers = (
        Publisher.objects.annotate(record_count=Count("records"))
        .filter(record_count__gt=0)
        .order_by("name")
    )
    page_obj = _paginate(request, publishers)
    return render(request, "catalog/browse/publishers.html", {"page_obj": page_obj})


def date_browse(request):
    """Group records by decade, showing counts."""
    records_with_dates = Record.objects.filter(
        date_of_publication__isnull=False
    ).values_list("date_of_publication", flat=True)

    decade_counts = {}
    for year in records_with_dates:
        decade = (year // 10) * 10
        label = f"{decade}s"
        decade_counts[label] = decade_counts.get(label, 0) + 1

    decades = sorted(decade_counts.items(), key=lambda x: x[0])
    page_obj = _paginate(request, decades)
    return render(request, "catalog/browse/dates.html", {"page_obj": page_obj})


def location_browse(request):
    locations = (
        Location.objects.annotate(record_count=Count("records"))
        .filter(record_count__gt=0)
        .order_by("label")
    )
    page_obj = _paginate(request, locations)
    return render(request, "catalog/browse/locations.html", {"page_obj": page_obj})


def author_detail(request, pk, slug=None):
    author = Author.objects.get(pk=pk)
    records = Record.objects.filter(authors=author).order_by("-created_at")
    page_obj = _paginate(request, records)
    return render(
        request,
        "catalog/browse/author_detail.html",
        {"author": author, "page_obj": page_obj},
    )


def subject_detail(request, pk, slug=None):
    subject = Subject.objects.get(pk=pk)
    records = Record.objects.filter(subjects=subject).order_by("-created_at")
    page_obj = _paginate(request, records)
    return render(
        request,
        "catalog/browse/subject_detail.html",
        {"subject": subject, "page_obj": page_obj},
    )


def series_browse(request):
    series_qs = Series.objects.annotate(
        volume_count=Count("volumes"),
        held_count=Count("volumes", filter=Q(volumes__held=True)),
        gap_count=Count("volumes", filter=Q(volumes__held=False)),
    ).order_by("title")
    page_obj = _paginate(request, series_qs)
    return render(request, "catalog/browse/series.html", {"page_obj": page_obj})
