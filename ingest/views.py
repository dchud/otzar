import io
import json
import logging

import qrcode
from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalog.models import Author, Location, Publisher, Record, Series
from catalog.search import ensure_fts_table, index_record
from catalog.utils import strip_marc_punctuation
from ingest.authority import (
    candidate_author_forms,
    find_author_matches,
    find_candidate_author_matches,
    resolve_candidate_author,
    single_strong_match,
)
from ingest.forms import RecordForm
from ingest.models import OCR_LEASE_TIMEOUT, ScanResult
from ingest.ocr import extract_metadata_from_image
from ingest.series_workflow import (
    create_series_volumes,
    detect_series_from_marc,
    link_record_to_series,
)
from sources.cascade import isbn_lookup, search_lc, search_nli
from sources.covers import fetch_cover_url
from sources.score import rank_candidates

logger = logging.getLogger(__name__)


def _close_scan_for_record(scan_id, candidate_index, record, user):
    """Mark the scan that produced this record as confirmed.

    Both routes into the candidates table carry a ScanResult -- the
    title-page search and the ISBN lookup -- and the Use button routes
    through select_candidate and confirm_candidate, which knew nothing
    about it. The scan stayed pending forever, so a title-page card came
    back in the poll pane on every tick and an ISBN lookup sat in the
    review queue, both already catalogued.

    Silent about a scan it will not touch: a candidate can be confirmed
    without any scan behind it, and a scan that was discarded while the
    user was deciding must not be resurrected.
    """
    if not scan_id:
        return
    scan = ScanResult.objects.filter(pk=scan_id).first()
    if scan is None:
        return
    if not user.is_staff and scan.scanned_by != user:
        return
    if scan.status in ("discarded", "confirmed"):
        return

    scan.status = "confirmed"
    scan.created_record = record
    scan.selected_candidate_index = candidate_index
    scan.save(
        update_fields=[
            "status",
            "created_record",
            "selected_candidate_index",
            "updated_at",
        ]
    )


def _in_progress_title_scans(user):
    """Title-page scans the poll pane should be showing.

    Both the poll and the upload response render from this, so an
    upload cannot momentarily drop a card the next poll puts back --
    which is what happened when the upload response listed only the
    uploader's awaiting_ocr rows while the poll listed those plus
    pending-with-output, and every user's rows for staff.
    """
    qs = ScanResult.objects.filter(scan_type="ocr").filter(
        Q(status="awaiting_ocr")
        | Q(status="pending", ocr_output__isnull=False)
    )
    if not user.is_staff:
        qs = qs.filter(scanned_by=user)
    return qs


def _take_ocr_lease(scan):
    """Claim the OCR lease for this scan. True if we got it.

    One conditional UPDATE, so the database arbitrates. Reading
    ocr_started_at and then writing it leaves a window wide enough for
    two polling devices to pass the check together and bill two vision
    calls -- the exact thing the lease exists to stop.

    The same statement reclaims a lease left behind by a run that died
    without releasing it.
    """
    now = timezone.now()
    rows = (
        ScanResult.objects.filter(pk=scan.pk)
        .filter(
            Q(ocr_started_at__isnull=True)
            | Q(ocr_started_at__lt=now - OCR_LEASE_TIMEOUT)
        )
        .update(ocr_started_at=now, updated_at=now)
    )
    return rows == 1


def _notice(request, message, status=200):
    """Render a message htmx will actually put on screen."""
    return render(
        request,
        "ingest/_notice.html",
        {"message": message},
        status=status,
    )


def _candidates_with_json(candidates, matches=None):
    """Pair each candidate with the JSON payload its row posts back.

    The candidate travels to ``select_candidate`` verbatim rather than
    being looked up again, so the row a user picked and the record that
    gets built describe the same thing. The template renders the payload
    into a textarea under autoescaping: the browser resolves the
    character references when it reads the field back, so the JSON
    arrives intact and a title carrying markup cannot close the tag.

    *matches*, when given, runs parallel to *candidates* and carries
    each one's :class:`sources.score.Match`. It rides on the item rather
    than in the candidate, so the score is shown beside the row but
    never posted back or stored as part of the record.
    """
    items = [{"data": c, "json": json.dumps(c)} for c in candidates or []]
    for item, match in zip(items, matches or ()):
        item["match"] = match
    return items


def _scan_for_repeat_search(user, scan_id):
    """The pending scan a repeated search should write its results into.

    A search launched from a queue row belongs to the scan already
    sitting in that row. Starting a fresh one would leave the original
    behind with its empty candidate list, so a user who retried twice
    would end up with three rows for one book.

    Returns None when there is no such scan to reuse -- no id given, the
    scan is gone or already resolved, or it belongs to someone else --
    and the caller creates one instead.
    """
    if not scan_id:
        return None
    scan = ScanResult.objects.filter(pk=scan_id, status="pending").first()
    if scan is None:
        return None
    if not user.is_staff and scan.scanned_by != user:
        return None
    return scan


def _create_record_from_candidate(
    candidate, user, notes="", location_label="", author_choice=None
):
    """Build and save a Record from a catalog candidate.

    Both confirm paths -- the review page at /ingest/confirm/ and the
    queue's "Use this" -- carried their own copy of this, and the copies
    had drifted. The queue's set neither ``source_marc`` nor
    ``date_of_publication_display``, so a MARC date that will not parse
    as an integer ("1994-2003", "c1999", "[1999]") was kept by one path
    and dropped outright by the other. One function, one record.

    The year is taken from the first four digits found anywhere in the
    date rather than by parsing the whole string, because catalog dates
    routinely carry brackets, copyright marks and ranges. Whatever the
    string was is preserved in the display field when no year parses out
    of it, so nothing is lost on the way in.

    Being the one place a candidate becomes a record, it is also the one
    place the candidate's author heading is reconciled against the
    authors the catalog already holds. ``author_choice`` carries what
    the cataloguer said on the confirm page; without one, the reconciler
    reuses an unambiguous match and otherwise creates a row.

    It is likewise the one place a candidate's series statement becomes
    a position in a set, so volumes catalogued one at a time end up on
    one Series rather than one apiece.
    """
    date_str = candidate.get("date", "")
    date_int = None
    if date_str:
        try:
            date_int = int(
                "".join(c for c in str(date_str) if c.isdigit())[:4]
            )
        except (ValueError, IndexError):
            pass

    record = Record(
        title=strip_marc_punctuation(candidate.get("title")),
        title_romanized=strip_marc_punctuation(
            candidate.get("title_alternate")
        ),
        volume_part_number=strip_marc_punctuation(
            candidate.get("volume_part_number")
        ),
        volume_part_title=strip_marc_punctuation(
            candidate.get("volume_part_title")
        ),
        statement_of_responsibility=strip_marc_punctuation(
            candidate.get("statement_of_responsibility")
        ),
        date_of_publication=date_int,
        date_of_publication_display=strip_marc_punctuation(str(date_str))
        if date_str and not date_int
        else "",
        place_of_publication=strip_marc_punctuation(candidate.get("place")),
        language=candidate.get("language") or "",
        source_marc=candidate.get("source_marc"),
        source_catalog=candidate.get("source_catalog") or "",
        notes=notes,
        created_by=user,
    )
    record.save()

    author = resolve_candidate_author(candidate, author_choice)
    if author is not None:
        record.authors.add(author)

    publisher_name = strip_marc_punctuation(candidate.get("publisher"))
    if publisher_name:
        publisher, _ = Publisher.objects.get_or_create(
            name=publisher_name,
            defaults={"place": strip_marc_punctuation(candidate.get("place"))},
        )
        record.publishers.add(publisher)

    if location_label:
        location, _ = Location.objects.get_or_create(label=location_label)
        record.locations.add(location)

    _attach_from_candidate(record, candidate)

    series_info = detect_series_from_marc(candidate)
    if series_info:
        link_record_to_series(
            record,
            series_info["series_title"],
            series_info["series_volume"],
        )

    # Best-effort; a missing cover must not cost the user the record.
    try:
        cover_url = fetch_cover_url(record)
        if cover_url:
            record.cover_url = cover_url
            record.save(update_fields=["cover_url"])
    except Exception:
        logger.exception("Cover fetch failed for record %s", record.record_id)

    ensure_fts_table()
    index_record(record)
    return record


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

    # The scan this candidate came from, so confirming can close it.
    request.session["candidate_scan_id"] = _parse_int(
        request.POST.get("scan_id")
    )
    request.session["candidate_index"] = _parse_int(
        request.POST.get("candidate_index")
    )
    return redirect("confirm_candidate")


@login_required
def confirm_candidate(request):
    """Review and confirm a candidate record from catalog lookup.

    The page offers the authors the catalog already holds under any of
    the candidate's headings, so a person catalogued once from each
    source ends up as one Author row rather than one per source. With
    nothing to offer the page is unchanged and the confirm stays a
    single click.
    """
    candidate = request.session.get("candidate")
    if not candidate:
        return redirect("ingest")

    if request.method == "POST":
        record = _create_record_from_candidate(
            candidate,
            request.user,
            notes=request.POST.get("notes") or "",
            location_label=request.POST.get("location_label", "").strip(),
            author_choice=request.POST.get("author_choice"),
        )

        _close_scan_for_record(
            request.session.get("candidate_scan_id"),
            request.session.get("candidate_index"),
            record,
            request.user,
        )

        request.session.pop("candidate", None)
        request.session.pop("candidate_scan_id", None)
        request.session.pop("candidate_index", None)
        return redirect(
            "catalog:record_detail",
            record_id=record.record_id,
            slug=record.slug,
        )

    author_matches = find_candidate_author_matches(candidate)
    default = single_strong_match(author_matches)
    primary, alternate = candidate_author_forms(candidate)

    return render(
        request,
        "ingest/confirm_candidate.html",
        {
            "candidate": candidate,
            "author_matches": author_matches,
            "author_match_default": default.pk if default else None,
            "candidate_author": primary or alternate,
        },
    )


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
                "catalog:record_detail",
                record_id=record.record_id,
                slug=record.slug,
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
    return render(
        request,
        "ingest/isbn_scan.html",
        {"phone_scanner": request.session.get("phone_scanner", False)},
    )


@login_required
def scan_poll(request):
    """Return pending ScanResults for the current user as an HTMX partial."""
    scans = ScanResult.objects.filter(
        status="pending", scanned_by=request.user
    )
    return render(request, "ingest/_scan_poll.html", {"scans": scans})


@login_required
def isbn_lookup_view(request):
    """Look up an ISBN and return candidate records as an HTMX partial."""
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    isbn = request.POST.get("isbn", "").strip()
    if not isbn:
        return HttpResponse(
            '<p class="text-red-600 text-sm">Please enter an ISBN.</p>'
        )

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
    for rec in results.get("dnb_records", []):
        rec["source_catalog"] = "DNB"
        candidates.append(rec)

    # Create a ScanResult so the scan appears in the review queue, or
    # refresh the one this search was launched from.
    scan = _scan_for_repeat_search(
        request.user, _parse_int(request.POST.get("scan_id"))
    )
    if scan is None:
        scan = ScanResult.objects.create(
            scan_type="isbn",
            isbn=isbn,
            candidate_records=candidates,
            scanned_by=request.user,
        )
    else:
        scan.candidate_records = candidates
        scan.save(update_fields=["candidate_records", "updated_at"])

    # Phone scanner mode: return a brief confirmation instead of candidates.
    if request.session.get("phone_scanner"):
        count = len(candidates)
        return render(
            request,
            "ingest/_phone_scan_sent.html",
            {"isbn": isbn, "count": count},
        )

    return render(
        request,
        "ingest/_candidates.html",
        {
            "candidates": _candidates_with_json(candidates),
            "isbn": isbn,
            "scan_id": scan.pk,
        },
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
                "catalog:record_detail",
                record_id=record.record_id,
                slug=record.slug,
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

    return render(
        request, "ingest/manual_entry.html", {"form": form, "record": record}
    )


@login_required
def title_page_scan(request):
    """Render the title page capture/upload page.

    Two render modes:
    - Desktop (default): direct upload form, QR sidebar to hand off to a
      phone, and a poll pane showing photos arriving from the phone.
    - Phone (when the ``phone_scanner`` session key is set): a
      streamlined capture-only view that polls for shared review state.

    Keyed off ``phone_scanner`` rather than ``phone_scan_target``, which
    only ever meant "where to send this phone after authenticating".
    Reading the target here served the desktop layout -- QR sidebar and
    all -- to a phone that authenticated for barcodes and then switched
    to the title-page route.
    """
    phone_mode = request.session.get("phone_scanner", False)
    return render(
        request,
        "ingest/title_page_scan.html",
        {"phone_mode": phone_mode},
    )


@login_required
def title_page_upload(request):
    """Receive a title page image; defer OCR until the user confirms.

    HTMX POST endpoint with two phases:

    - Image upload: saves the photo to ``ScanResult.image`` with
      ``status=awaiting_ocr`` and returns a card partial showing the
      uploaded image. OCR is NOT run here; the user (or a peer device)
      triggers it via ``run_ocr`` after reviewing the photo.
    - Cascade search (``action=search``): runs the catalog search using
      the edited metadata fields and returns candidates.
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
            "author_romanized": request.POST.get(
                "author_romanized", ""
            ).strip(),
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

        # Order by agreement with what was read off the page, across
        # catalogs. Each cascade returns its rows in that catalog's own
        # relevance order, which knows nothing about the photograph, and
        # a title-only fallback query returns every edition of a work
        # in no useful order at all.
        ranked = rank_candidates(metadata, candidates)
        candidates = [candidate for candidate, _ in ranked]
        matches = [match for _, match in ranked]

        # Store what the search found, in the order it was shown, so
        # the scan carries the same record the ISBN path stores and a
        # candidate index means something on the way back through
        # confirm.
        scan_id = _parse_int(request.POST.get("scan_id"))
        if scan_id:
            ScanResult.objects.filter(pk=scan_id).update(
                candidate_records=candidates, updated_at=timezone.now()
            )

        return render(
            request,
            "ingest/_candidates.html",
            {
                "candidates": _candidates_with_json(candidates, matches),
                "scored": True,
                "metadata": metadata,
                "scan_id": scan_id,
            },
        )

    # --- Image upload phase (OCR deferred) ---
    image_file = request.FILES.get("image")
    if not image_file:
        return HttpResponse(
            '<p class="text-red-600 text-sm">No image uploaded.</p>'
        )

    ScanResult.objects.create(
        scan_type="ocr",
        status="awaiting_ocr",
        image=image_file,
        scanned_by=request.user,
    )

    # Return the full poll partial so both upload and poll responses are
    # interchangeable. This avoids a race where the poll cycle would
    # overwrite a single just-uploaded card with the full list.
    return render(
        request,
        "ingest/_title_page_poll.html",
        {"scans": _in_progress_title_scans(request.user)},
    )


@login_required
@require_POST
def run_ocr(request, scan_id):
    """Run (or re-run) OCR on a previously-uploaded title-page image.

    Accepts both ``awaiting_ocr`` (first run) and ``pending`` (re-run
    after the user found the previous extraction unusable). The image
    must still be present — the gate is image presence, not status.
    Returns 409 if the image has been discarded, or if another device
    already has a run in flight on this scan.

    The lease is taken before the vision call and released in a
    ``finally``, so the poll pane on every device showing this scan
    reports the run while it lasts. See ``ScanResult`` on why this is a
    timestamp and not a status.
    """
    scan = get_object_or_404(ScanResult, pk=scan_id)
    if not request.user.is_staff and scan.scanned_by != request.user:
        return HttpResponse("Forbidden", status=403)
    if not scan.image or scan.status == "discarded":
        return _notice(request, "Image is no longer available.", status=409)
    if not _take_ocr_lease(scan):
        return _notice(request, "OCR is already running.", status=409)

    try:
        with scan.image.open("rb") as fh:
            image_bytes = fh.read()
        metadata = extract_metadata_from_image(image_bytes)
    finally:
        ScanResult.objects.filter(pk=scan.pk).update(ocr_started_at=None)

    # The row was read before a call that runs 5-9 seconds. A discard
    # from the other device lands in that gap, and writing the result
    # back resurrected the scan as a card with no image whose only
    # button always 409s.
    scan.refresh_from_db()
    if scan.status == "discarded" or not scan.image:
        return _notice(
            request, "This photo was discarded while OCR was running."
        )

    # Extraction separates a call that produced no reading (None) from a
    # reading with nothing in it (every field null). Both leave the user
    # with no metadata, so both take this path, and the empty reading is
    # dropped rather than stored: keeping it would put the scan in
    # pending with ocr_output set, which the poll pane offers to continue
    # editing — a form of eight empty boxes over an unreadable photo.
    if metadata is None or not any(metadata.values()):
        # Reset to awaiting state so the card in the poll pane keeps its
        # Run OCR button. The response is a notice rather than a card:
        # the card is already on screen, and rendering a second one put
        # the same photo up twice under a duplicated element id.
        scan.status = "awaiting_ocr"
        scan.ocr_output = None
        scan.save(update_fields=["status", "ocr_output", "updated_at"])
        return render(request, "ingest/_ocr_error.html", {"scan": scan})

    scan.status = "pending"
    scan.ocr_output = metadata
    scan.save(update_fields=["status", "ocr_output", "updated_at"])

    return render(
        request,
        "ingest/_ocr_results.html",
        {"metadata": metadata, "scan": scan},
    )


@login_required
def title_page_poll(request):
    """Return image cards for the user's in-progress title-page scans.

    Includes both freshly-uploaded scans (``awaiting_ocr``) and scans
    that have OCR output but haven't been confirmed into a Record yet
    (``pending`` with ``ocr_output``). Without the latter, scans where
    OCR succeeded but the user navigated away would silently disappear
    from the UI even though their image and metadata are still saved.

    Staff users see all in-progress scans, matching review_queue.
    """
    return render(
        request,
        "ingest/_title_page_poll.html",
        {"scans": _in_progress_title_scans(request.user)},
    )


@login_required
@require_POST
def edit_title_metadata(request, scan_id):
    """Re-render the metadata edit form for a pending scan.

    Lets the user resume editing OCR output after navigating away. The
    scan must already have ocr_output (status=pending); otherwise 409.
    """
    scan = get_object_or_404(ScanResult, pk=scan_id)
    if not request.user.is_staff and scan.scanned_by != request.user:
        return HttpResponse("Forbidden", status=403)
    if scan.status != "pending" or not scan.ocr_output:
        return _notice(request, "Scan has no metadata to edit.", status=409)
    return render(
        request,
        "ingest/_ocr_results.html",
        {"metadata": scan.ocr_output, "scan": scan},
    )


@login_required
@require_POST
def discard_title_scan(request, scan_id):
    """Discard a title-page scan: remove the image file and mark the row.

    Idempotent — calling on an already-discarded scan returns an empty
    200 so the caller can rely on the card disappearing either way.
    """
    scan = get_object_or_404(ScanResult, pk=scan_id)
    if not request.user.is_staff and scan.scanned_by != request.user:
        return HttpResponse("Forbidden", status=403)

    if scan.status != "discarded":
        if scan.image:
            scan.image.delete(save=False)
            scan.image = None
        scan.status = "discarded"
        scan.save(update_fields=["status", "image", "updated_at"])

    return HttpResponse("")


def _attach_related(record, cleaned_data):
    """Create or link Author, Publisher, and Location from form data."""
    author_name = cleaned_data.get("author_name", "").strip()
    if author_name:
        author, _ = Author.objects.get_or_create(
            name=author_name,
            defaults={
                "name_romanized": cleaned_data.get(
                    "author_name_romanized", ""
                ).strip()
            },
        )
        record.authors.add(author)

    publisher_name = cleaned_data.get("publisher_name", "").strip()
    if publisher_name:
        publisher, _ = Publisher.objects.get_or_create(
            name=publisher_name,
            defaults={
                "place": cleaned_data.get("publisher_place", "").strip()
            },
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
        author_name = strip_marc_punctuation(author_name)
        if author_name:
            author, _ = Author.objects.get_or_create(name=author_name)
            record.authors.add(author)

    # Subjects from MARC 650 fields
    for heading in candidate.get("subjects", []):
        heading = strip_marc_punctuation(heading)
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
    author_name_romanized = request.POST.get(
        "author_name_romanized", ""
    ).strip()

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
    """Show pending ScanResults for the current user (or all, for staff).

    Each scan carries its candidates paired with their JSON payloads,
    the shape the candidate table partial reads, so the queue renders
    the same rows as the search results it came from.
    """
    if request.user.is_staff:
        scans = ScanResult.objects.filter(status="pending")
    else:
        scans = ScanResult.objects.filter(
            status="pending", scanned_by=request.user
        )

    scans = list(scans)
    for scan in scans:
        scan.candidates = _candidates_with_json(scan.candidate_records)

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

    record = _create_record_from_candidate(candidate, request.user)

    # Mark the ScanResult as confirmed.
    scan.status = "confirmed"
    scan.selected_candidate_index = candidate_index
    scan.created_record = record
    scan.save()

    # Redirect back to where the user came from (scan page or review queue).
    referer = request.META.get("HTTP_REFERER", "")
    if "/ingest/scan/" in referer:
        return redirect("isbn_scan")
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

    # Redirect back to where the user came from (scan page or review queue).
    referer = request.META.get("HTTP_REFERER", "")
    if "/ingest/scan/" in referer:
        return redirect("isbn_scan")
    return redirect("review_queue")


_QR_TARGETS = ("isbn", "title")


@login_required
def qr_code_view(request):
    """Generate a QR code PNG linking to the phone scanning interface.

    The QR URL contains a signed token (valid for 1 hour) that allows the
    phone browser to authenticate as the current user.

    The optional ``target`` query param ("isbn" or "title", default "isbn")
    selects which scan workflow the phone lands on after authentication.
    """
    target = request.GET.get("target", "isbn")
    if target not in _QR_TARGETS:
        return HttpResponseBadRequest("Unknown target.")

    signer = TimestampSigner()
    token = signer.sign(f"{request.user.pk}:{target}")

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
    """Validate a signed QR token and log the user in for this session.

    The token payload is ``"<user_pk>:<target>"``. Legacy tokens carrying
    only the user_pk default to the isbn target so previously-rendered QR
    codes keep working.
    """
    signer = TimestampSigner()
    try:
        # Token is valid for 1 hour (3600 seconds).
        payload = signer.unsign(token, max_age=3600)
    except SignatureExpired:
        return HttpResponse(
            "This QR code has expired. Please generate a new one.", status=403
        )
    except BadSignature:
        return HttpResponse("Invalid QR code.", status=400)

    if ":" in payload:
        user_pk, target = payload.split(":", 1)
    else:
        user_pk, target = payload, "isbn"
    if target not in _QR_TARGETS:
        return HttpResponse("Invalid QR code.", status=400)

    try:
        user = User.objects.get(pk=int(user_pk))
    except (User.DoesNotExist, ValueError):
        return HttpResponse("User not found.", status=404)

    auth_login(request, user)
    request.session["phone_scanner"] = True
    request.session["phone_scan_target"] = target
    return redirect("title_page_scan" if target == "title" else "isbn_scan")


def _parse_int(value):
    """Try to parse an integer from a string, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
