from django.conf import settings
from django.db import models


class ScanResult(models.Model):
    """A pending scan result awaiting review."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("discarded", "Discarded"),
    ]

    SCAN_TYPE_CHOICES = [
        ("isbn", "ISBN/Barcode"),
        ("ocr", "Title Page OCR"),
    ]

    scan_type = models.CharField(max_length=10, choices=SCAN_TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    isbn = models.CharField(max_length=20, blank=True)
    image = models.ImageField(upload_to="staging/%Y/%m/%d/", blank=True)
    ocr_output = models.JSONField(null=True, blank=True)
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
