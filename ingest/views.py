import io
import json
import logging
import os
import uuid

import qrcode
from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import Author, Location, Publisher, Record, Series
from catalog.search import ensure_fts_table, index_record
from ingest.authority import find_author_matches
from ingest.forms import RecordForm
from ingest.models import ScanResult
from ingest.ocr import extract_metadata_from_image
from ingest.series_workflow import create_series_volumes
from sources.cascade import isbn_lookup, search_lc, search_nli

logger = logging.getLogger(__name__)


@login_required
def ingest_index(request):
    """Landing page with links to all ingest methods."""
    return render(request, "ingest/index.html")


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
def select_candidate(request):
    """Store a selected candidate's full data in session, redirect to manual entry."""
    if request.method != "POST":
        return redirect("ingest")
    candidate_json = request.POST.get("candidate_data", "")
    if candidate_json:
        try:
            candidate = json.loads(candidate_json)
            request.session["candidate"] = candidate
        except (json.JSONDecodeError, TypeError):
            logger.exception("Failed to parse candidate JSON")
    else:
        logger.warning("select_candidate called with empty candidate_data")
    return redirect("confirm_candidate")


@login_required
def confirm_candidate(request):
    """Review and confirm a candidate record from catalog lookup."""
    candidate = request.session.get("candidate")
    if not candidate:
        return redirect("ingest")

    if request.method == "POST":
        # Create the record from candidate data.
        date_str = candidate.get("date", "")
        date_int = None
        if date_str:
            try:
                date_int = int("".join(c for c in str(date_str) if c.isdigit())[:4])
            except (ValueError, IndexError):
                pass

        record = Record(
            title=candidate.get("title") or "",
            title_romanized=candidate.get("title_alternate") or "",
            date_of_publication=date_int,
            date_of_publication_display=str(date_str)
            if date_str and not date_int
            else "",
            place_of_publication=candidate.get("place") or "",
            language=candidate.get("language") or "",
            source_marc=candidate.get("source_marc"),
            source_catalog=candidate.get("source_catalog") or "",
            notes=request.POST.get("notes") or "",
            created_by=request.user,
        )
        record.save()

        # Primary author
        author_name = candidate.get("author", "").strip()
        if author_name:
            author, _ = Author.objects.get_or_create(name=author_name)
            record.authors.add(author)

        # Publisher
        publisher_name = candidate.get("publisher", "").strip()
        if publisher_name:
            publisher, _ = Publisher.objects.get_or_create(
                name=publisher_name,
                defaults={"place": candidate.get("place", "")},
            )
            record.publishers.add(publisher)

        # Location from form
        location_label = request.POST.get("location_label", "").strip()
        if location_label:
            location, _ = Location.objects.get_or_create(label=location_label)
            record.locations.add(location)

        # Additional data from MARC
        _attach_from_candidate(record, candidate)

        ensure_fts_table()
        index_record(record)

        request.session.pop("candidate", None)
        return redirect(
            "catalog:record_detail", record_id=record.record_id, slug=record.slug
        )

    return render(request, "ingest/confirm_candidate.html", {"candidate": candidate})


@login_required
def manual_entry(request):
    """Create a new record via manual entry form."""
    if request.method == "POST":
        form = RecordForm(request.POST)
        candidate = request.session.get("candidate")
        if form.is_valid():
            record = form.save(commit=False)
            record.created_by = request.user

            # Attach source MARC/catalog from session if available.
            candidate = request.session.pop("candidate", None)
            if candidate:
                record.source_marc = candidate.get("source_marc")
                record.source_catalog = candidate.get("source_catalog", "")

            record.save()

            # If we have candidate data, extract all MARC fields.
            if candidate:
                _attach_from_candidate(record, candidate)
            _attach_related(record, form.cleaned_data)
            ensure_fts_table()
            index_record(record)

            return redirect(
                "catalog:record_detail", record_id=record.record_id, slug=record.slug
            )
    else:
        initial = {}
        candidate = request.session.get("candidate")
        if candidate:
            initial["title"] = candidate.get("title", "")
            initial["title_romanized"] = candidate.get("title_alternate", "")
            initial["author_name"] = candidate.get("author", "")
            initial["publisher_name"] = candidate.get("publisher", "")
            initial["place_of_publication"] = candidate.get("place", "")
            initial["language"] = candidate.get("language", "")
            date = candidate.get("date", "")
            if date:
                try:
                    initial["date_of_publication"] = int(
                        "".join(c for c in str(date) if c.isdigit())[:4]
                    )
                except (ValueError, IndexError):
                    initial["date_of_publication_display"] = str(date)

        # Also accept GET params for simple pre-fill.
        for field_name in _PREFILL_FIELDS:
            value = request.GET.get(field_name, "").strip()
            if value:
                initial[field_name] = value

        form = RecordForm(initial=initial) if initial else RecordForm()

    return render(
        request,
        "ingest/manual_entry.html",
        {"form": form, "candidate": candidate},
    )


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

    # Create a ScanResult so the scan appears in the review queue.
    ScanResult.objects.create(
        scan_type="isbn",
        isbn=isbn,
        candidate_records=candidates,
        scanned_by=request.user,
    )

    # Pair each candidate with its JSON for the select form.
    candidates_with_json = [{"data": c, "json": json.dumps(c)} for c in candidates]

    return render(
        request,
        "ingest/_candidates.html",
        {"candidates": candidates_with_json, "isbn": isbn},
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

    # Create a ScanResult so the OCR scan appears in the review queue.
    ScanResult.objects.create(
        scan_type="ocr",
        ocr_output=metadata,
        scanned_by=request.user,
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


def _attach_from_candidate(record, candidate):
    """Extract all MARC fields from a candidate dict and attach to the record."""
    from catalog.models import ExternalIdentifier, Subject

    # Additional authors from MARC 700 fields
    for author_name in candidate.get("additional_authors", []):
        author_name = author_name.strip()
        if author_name:
            author, _ = Author.objects.get_or_create(name=author_name)
            record.authors.add(author)

    # Subjects from MARC 650 fields
    for heading in candidate.get("subjects", []):
        heading = heading.strip()
        if heading:
            subject, _ = Subject.objects.get_or_create(
                heading=heading,
                defaults={"source": candidate.get("source_catalog", "")},
            )
            record.subjects.add(subject)

    # External identifiers
    isbn = candidate.get("isbn", "")
    if isbn:
        ExternalIdentifier.objects.get_or_create(
            record=record, identifier_type="ISBN", value=isbn.strip()
        )
    lccn = candidate.get("lccn", "")
    if lccn:
        ExternalIdentifier.objects.get_or_create(
            record=record, identifier_type="LCCN", value=lccn.strip()
        )
    oclc = candidate.get("oclc", "")
    if oclc:
        ExternalIdentifier.objects.get_or_create(
            record=record, identifier_type="OCLC", value=oclc.strip()
        )
    lc_class = candidate.get("lc_classification", "")
    if lc_class:
        ExternalIdentifier.objects.get_or_create(
            record=record, identifier_type="LCC", value=lc_class.strip()
        )
    dewey = candidate.get("dewey_classification", "")
    if dewey:
        ExternalIdentifier.objects.get_or_create(
            record=record, identifier_type="DDC", value=dewey.strip()
        )


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


# ---------------------------------------------------------------------------
# Review queue & QR handoff
# ---------------------------------------------------------------------------


@login_required
def review_queue(request):
    """Show pending ScanResults for the current user (or all, for staff)."""
    if request.user.is_staff:
        scans = ScanResult.objects.filter(status="pending")
    else:
        scans = ScanResult.objects.filter(status="pending", scanned_by=request.user)

    return render(request, "ingest/review_queue.html", {"scans": scans})


@login_required
@require_POST
def confirm_scan(request, scan_id):
    """Confirm a ScanResult: create a Record from the selected candidate."""
    scan = get_object_or_404(ScanResult, pk=scan_id)

    # Only the owner or staff can confirm.
    if not request.user.is_staff and scan.scanned_by != request.user:
        return HttpResponse("Forbidden", status=403)

    candidate_index_str = request.POST.get("candidate_index", "0")
    try:
        candidate_index = int(candidate_index_str)
    except (ValueError, TypeError):
        candidate_index = 0

    candidates = scan.candidate_records or []
    if not candidates or candidate_index >= len(candidates):
        return HttpResponseBadRequest("Invalid candidate index.")

    candidate = candidates[candidate_index]

    # Create the Record from candidate data.
    record = Record(
        title=candidate.get("title", ""),
        title_romanized=candidate.get("title_alternate", ""),
        date_of_publication=_parse_int(candidate.get("date")),
        place_of_publication=candidate.get("place", ""),
        language=candidate.get("language", ""),
        source_catalog=candidate.get("source_catalog", ""),
        created_by=request.user,
    )
    record.save()

    # Attach author if present.
    author_name = candidate.get("author", "").strip()
    if author_name:
        author, _ = Author.objects.get_or_create(name=author_name)
        record.authors.add(author)

    # Attach publisher if present.
    publisher_name = candidate.get("publisher", "").strip()
    if publisher_name:
        publisher, _ = Publisher.objects.get_or_create(name=publisher_name)
        record.publishers.add(publisher)

    ensure_fts_table()
    index_record(record)

    # Mark the ScanResult as confirmed.
    scan.status = "confirmed"
    scan.selected_candidate_index = candidate_index
    scan.created_record = record
    scan.save()

    return redirect("review_queue")


@login_required
@require_POST
def discard_scan(request, scan_id):
    """Mark a ScanResult as discarded."""
    scan = get_object_or_404(ScanResult, pk=scan_id)

    if not request.user.is_staff and scan.scanned_by != request.user:
        return HttpResponse("Forbidden", status=403)

    scan.status = "discarded"
    scan.save()

    return redirect("review_queue")


@login_required
def qr_code_view(request):
    """Generate a QR code PNG linking to the phone scanning interface.

    The QR URL contains a signed token (valid for 1 hour) that allows the
    phone browser to authenticate as the current user.
    """
    signer = TimestampSigner()
    token = signer.sign(str(request.user.pk))

    # Build the full URL for the phone auth endpoint.
    # request.is_secure() may be False behind runserver_plus with SSL,
    # so also check CSRF_TRUSTED_ORIGINS for an https:// entry.
    trusted = getattr(settings, "CSRF_TRUSTED_ORIGINS", [])
    has_https_origin = any(o.startswith("https://") for o in trusted)
    scheme = "https" if request.is_secure() or has_https_origin else "http"
    host = request.get_host()
    path = f"/ingest/phone-auth/{token}/"
    url = f"{scheme}://{host}{path}"

    # Generate QR code image.
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return HttpResponse(buf.getvalue(), content_type="image/png")


def phone_scan_auth(request, token):
    """Validate a signed QR token and log the user in for this session."""
    signer = TimestampSigner()
    try:
        # Token is valid for 1 hour (3600 seconds).
        user_pk = signer.unsign(token, max_age=3600)
    except SignatureExpired:
        return HttpResponse(
            "This QR code has expired. Please generate a new one.", status=403
        )
    except BadSignature:
        return HttpResponse("Invalid QR code.", status=400)

    try:
        user = User.objects.get(pk=int(user_pk))
    except (User.DoesNotExist, ValueError):
        return HttpResponse("User not found.", status=404)

    auth_login(request, user)
    return redirect("isbn_scan")


def _parse_int(value):
    """Try to parse an integer from a string, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
