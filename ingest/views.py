import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import Author, Location, Publisher, Record
from catalog.search import ensure_fts_table, index_record
from ingest.forms import RecordForm
from sources.cascade import isbn_lookup

logger = logging.getLogger(__name__)

# Fields that can be pre-filled from ISBN lookup query params.
_PREFILL_FIELDS = [
    "title",
    "title_romanized",
    "author_name",
    "date_of_publication",
    "place_of_publication",
    "publisher_name",
    "language",
]


@login_required
def manual_entry(request):
    """Create a new record via manual entry form."""
    if request.method == "POST":
        form = RecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.created_by = request.user

            # Attach source MARC/catalog from session if available.
            source_marc = request.session.pop("source_marc", None)
            source_catalog = request.session.pop("source_catalog", None)
            if source_marc:
                record.source_marc = source_marc
            if source_catalog:
                record.source_catalog = source_catalog

            record.save()

            _attach_related(record, form.cleaned_data)
            ensure_fts_table()
            index_record(record)

            return redirect(
                "catalog:record_detail", record_id=record.record_id, slug=record.slug
            )
    else:
        # Pre-fill from GET parameters (ISBN lookup flow).
        initial = {}
        for field_name in _PREFILL_FIELDS:
            value = request.GET.get(field_name, "").strip()
            if value:
                initial[field_name] = value

        # Store source MARC/catalog in session if provided.
        source_marc_json = request.GET.get("source_marc", "")
        source_catalog = request.GET.get("source_catalog", "")
        if source_marc_json:
            try:
                request.session["source_marc"] = json.loads(source_marc_json)
            except (json.JSONDecodeError, TypeError):
                pass
        if source_catalog:
            request.session["source_catalog"] = source_catalog

        form = RecordForm(initial=initial) if initial else RecordForm()

    return render(request, "ingest/manual_entry.html", {"form": form})


@login_required
def isbn_scan(request):
    """Render the ISBN/barcode scanning page."""
    return render(request, "ingest/isbn_scan.html")


@login_required
def isbn_lookup_view(request):
    """Look up an ISBN and return candidate records as an HTMX partial."""
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    isbn = request.POST.get("isbn", "").strip()
    if not isbn:
        return HttpResponse('<p class="text-red-600 text-sm">Please enter an ISBN.</p>')

    try:
        results = isbn_lookup(isbn)
    except Exception:
        logger.exception("ISBN lookup error for isbn=%s", isbn)
        return HttpResponse(
            '<p class="text-red-600 text-sm">'
            "An error occurred while looking up this ISBN. Please try again."
            "</p>"
        )

    candidates = []
    for rec in results.get("nli_records", []):
        rec["source_catalog"] = "NLI"
        candidates.append(rec)
    for rec in results.get("lc_records", []):
        rec["source_catalog"] = "LC"
        candidates.append(rec)

    return render(
        request,
        "ingest/_candidates.html",
        {"candidates": candidates, "isbn": isbn},
    )


@login_required
def edit_record(request, record_id):
    """Edit an existing record."""
    record = get_object_or_404(Record, record_id=record_id)

    if request.method == "POST":
        form = RecordForm(request.POST, instance=record)
        if form.is_valid():
            record = form.save()
            _attach_related(record, form.cleaned_data)
            ensure_fts_table()
            index_record(record)

            return redirect(
                "catalog:record_detail", record_id=record.record_id, slug=record.slug
            )
    else:
        initial = {}
        first_author = record.authors.first()
        if first_author:
            initial["author_name"] = first_author.name
            initial["author_name_romanized"] = first_author.name_romanized

        first_publisher = record.publishers.first()
        if first_publisher:
            initial["publisher_name"] = first_publisher.name
            initial["publisher_place"] = first_publisher.place

        first_location = record.locations.first()
        if first_location:
            initial["location_label"] = first_location.label

        form = RecordForm(instance=record, initial=initial)

    return render(request, "ingest/manual_entry.html", {"form": form, "record": record})


def _attach_related(record, cleaned_data):
    """Create or link Author, Publisher, and Location from form data."""
    author_name = cleaned_data.get("author_name", "").strip()
    if author_name:
        author, _ = Author.objects.get_or_create(
            name=author_name,
            defaults={
                "name_romanized": cleaned_data.get("author_name_romanized", "").strip()
            },
        )
        record.authors.add(author)

    publisher_name = cleaned_data.get("publisher_name", "").strip()
    if publisher_name:
        publisher, _ = Publisher.objects.get_or_create(
            name=publisher_name,
            defaults={"place": cleaned_data.get("publisher_place", "").strip()},
        )
        record.publishers.add(publisher)

    location_label = cleaned_data.get("location_label", "").strip()
    if location_label:
        location, _ = Location.objects.get_or_create(label=location_label)
        record.locations.add(location)
