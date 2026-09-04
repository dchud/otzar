from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

JPEG_SUFFIXES = {".jpg", ".jpeg", ".png"}

# How long a scan may claim to be running OCR before other devices
# stop believing it. Extraction takes 5-9 seconds against a title
# page; the margin is for a slow model, not a crashed one.
OCR_LEASE_TIMEOUT = timedelta(minutes=2)


def staging_image_path(instance, filename):
    """Build a storage path that no other upload can land on.

    Phone captures arrive named image.jpg every time, and discarding a
    scan deletes the stored file, which frees that name for the next
    upload. A path derived from the uploaded filename therefore puts a
    retake on the same URL as the photo it replaced, and any browser
    holding that URL keeps painting the old image. A random stem gives
    every upload its own URL for as long as the file exists.

    The suffix is normalized because the capture form re-encodes to JPEG
    while keeping the original filename, so a photo picked from an iOS
    library arrives as JPEG bytes under a .heic name.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in JPEG_SUFFIXES:
        suffix = ".jpg"
    return f"staging/{timezone.now():%Y/%m/%d}/{uuid4().hex}{suffix}"


class ScanResult(models.Model):
    """A pending scan result awaiting review.

    Status lifecycle:
      awaiting_ocr  Image saved, OCR not yet run (OCR scans only).
      pending       Candidates ready, awaiting record selection.
      confirmed     Record created from a selected candidate.
      discarded     Rejected by user; image file removed on transition.

    ``ocr_started_at`` is a lease, not a status. Two devices share a
    scan, and the spinner htmx puts on a button lives only in the
    browser that clicked it, so the other device polled, saw
    ``awaiting_ocr``, and offered a Run OCR button that would spend a
    second vision call on the same image. A lease is the shared state
    both devices can read. It expires rather than being cleared,
    because a process that dies mid-call (a restart, a dropped
    connection) runs no cleanup, and a status value set the same way
    would strand the row with no way back.
    """

    STATUS_CHOICES = [
        ("awaiting_ocr", "Awaiting OCR"),
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("discarded", "Discarded"),
    ]

    SCAN_TYPE_CHOICES = [
        ("isbn", "ISBN/Barcode"),
        ("ocr", "Title Page OCR"),
    ]

    scan_type = models.CharField(max_length=10, choices=SCAN_TYPE_CHOICES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    isbn = models.CharField(max_length=20, blank=True)
    image = models.ImageField(upload_to=staging_image_path, blank=True)
    ocr_output = models.JSONField(null=True, blank=True)
    ocr_started_at = models.DateTimeField(null=True, blank=True)
    candidate_records = models.JSONField(default=list, blank=True)
    selected_candidate_index = models.IntegerField(null=True, blank=True)
    created_record = models.ForeignKey(
        "catalog.Record",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scan_results",
    )
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="scan_results",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def ocr_is_running(self):
        """True while a live OCR lease is held on this scan.

        A lease older than ``OCR_LEASE_TIMEOUT`` is treated as dead:
        the run that took it cannot report back, and the alternative is
        a card no device can ever act on again.
        """
        if self.ocr_started_at is None:
            return False
        return timezone.now() - self.ocr_started_at < OCR_LEASE_TIMEOUT

    def __str__(self):
        label = self.isbn if self.scan_type == "isbn" else "title page"
        return f"{self.scan_type} scan: {label} ({self.status})"


class APIUsageLog(models.Model):
    """Log of API calls for cost monitoring."""

    api = models.CharField(max_length=50)
    model = models.CharField(max_length=100, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="api_usage",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.api} ({self.created_at:%Y-%m-%d %H:%M})"
