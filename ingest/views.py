import json
import logging
import os
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import Author, Location, Publisher, Record, Series
from catalog.search import ensure_fts_table, index_record
from ingest.authority import find_author_matches
from ingest.forms import RecordForm
from ingest.ocr import extract_metadata_from_image
from ingest.series_workflow import create_series_volumes
from sources.cascade import isbn_lookup, search_lc, search_nli

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


@login_required
def title_page_scan(request):
    """Render the title page camera/upload page."""
    return render(request, "ingest/title_page_scan.html")


@login_required
def title_page_upload(request):
    """Receive a title page image, run OCR, return metadata for review.

    HTMX POST endpoint. On initial upload, runs Claude Vision OCR and
    returns editable metadata fields. When the user clicks 'Search catalogs',
    runs the search cascade and returns candidates.
    """
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    # --- Cascade search phase (user confirmed/edited metadata) ---
    if request.POST.get("action") == "search":
        metadata = {
            "title": request.POST.get("title", "").strip(),
            "subtitle": request.POST.get("subtitle", "").strip(),
            "author": request.POST.get("author", "").strip(),
            "publisher": request.POST.get("publisher", "").strip(),
            "place": request.POST.get("place", "").strip(),
            "date": request.POST.get("date", "").strip(),
            "title_romanized": request.POST.get("title_romanized", "").strip(),
            "author_romanized": request.POST.get("author_romanized", "").strip(),
        }
        candidates = []
        try:
            nli_result = search_nli(metadata)
            for rec in nli_result.records:
                rec["source_catalog"] = "NLI"
                candidates.append(rec)
        except Exception:
            logger.exception("NLI cascade search failed")
        try:
            lc_result = search_lc(metadata)
            for rec in lc_result.records:
                rec["source_catalog"] = "LC"
                candidates.append(rec)
        except Exception:
            logger.exception("LC cascade search failed")

        return render(
            request,
            "ingest/_candidates.html",
            {"candidates": candidates, "metadata": metadata},
        )

    # --- OCR phase (image upload) ---
    image_file = request.FILES.get("image")
    if not image_file:
        return HttpResponse('<p class="text-red-600 text-sm">No image uploaded.</p>')

    image_bytes = image_file.read()

    # Save to staging directory for debugging / reprocessing.
    staging_dir = os.path.join(settings.BASE_DIR, "tmp", "title_pages")
    os.makedirs(staging_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    staging_path = os.path.join(staging_dir, filename)
    with open(staging_path, "wb") as f:
        f.write(image_bytes)

    metadata = extract_metadata_from_image(image_bytes)
    if metadata is None:
        return HttpResponse(
            '<p class="text-red-600 text-sm">'
            "OCR could not extract metadata from this image. "
            "Please try again with a clearer photo."
            "</p>"
        )

    return render(
        request,
        "ingest/_ocr_results.html",
        {"metadata": metadata, "staging_file": filename},
    )


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


@login_required
def authority_check(request):
    """HTMX endpoint: check for matching authors during ingest.

    POST with ``author_name`` (and optionally ``author_name_romanized``).
    Returns an HTML partial listing any existing Author matches so the
    user can choose to reuse one rather than creating a duplicate.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    author_name = request.POST.get("author_name", "").strip()
    author_name_romanized = request.POST.get("author_name_romanized", "").strip()

    if not author_name and not author_name_romanized:
        return HttpResponse("")

    matches = find_author_matches(author_name, author_name_romanized)

    return render(
        request,
        "ingest/_authority_matches.html",
        {"matches": matches, "query_name": author_name},
    )


@login_required
def series_manage(request, series_id):
    """Manage volumes for an existing Series.

    GET: display existing volumes with gap indicators and an add-volumes form.
    POST: create new SeriesVolume entries from the submitted volume spec.
    """
    series = get_object_or_404(Series, pk=series_id)
    message = ""

    if request.method == "POST":
        volume_spec = request.POST.get("volume_spec", "").strip()
        if volume_spec:
            created = create_series_volumes(series, volume_spec)
            message = (
                f"Added {len(created)} volume(s)."
                if created
                else "No new volumes added (already exist)."
            )

    volumes = series.volumes.all().order_by("volume_number")

    # Detect gaps: find missing integers in the numeric range
    numeric_vols = []
    for v in volumes:
        try:
            numeric_vols.append(int(v.volume_number))
        except (ValueError, TypeError):
            pass

    gaps = []
    if numeric_vols:
        full_range = set(range(min(numeric_vols), max(numeric_vols) + 1))
        gaps = sorted(full_range - set(numeric_vols))

    return render(
        request,
        "ingest/series_manage.html",
        {
            "series": series,
            "volumes": volumes,
            "gaps": gaps,
            "message": message,
        },
    )
