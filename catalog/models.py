from django.conf import settings
from django.db import models
from django.utils.text import slugify

from catalog.id_generation import generate_record_id


class Record(models.Model):
    """A bibliographic record in the catalog."""

    record_id = models.CharField(
        max_length=50, unique=True, editable=False, db_index=True
    )
    slug = models.SlugField(max_length=255, allow_unicode=True, blank=True)
    title = models.CharField(max_length=500)
    title_romanized = models.CharField(max_length=500, blank=True)
    subtitle = models.CharField(max_length=500, blank=True)
    date_of_publication = models.IntegerField(
        null=True, blank=True, db_index=True
    )
    date_of_publication_display = models.CharField(max_length=100, blank=True)
    place_of_publication = models.CharField(max_length=255, blank=True)
    language = models.CharField(max_length=50, blank=True)
    source_marc = models.JSONField(null=True, blank=True)
    source_catalog = models.CharField(
        max_length=10,
        choices=[("NLI", "NLI"), ("LC", "LC"), ("DNB", "DNB")],
        blank=True,
    )
    cover_url = models.URLField(max_length=500, blank=True, default="")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    authors = models.ManyToManyField(
        "Author", blank=True, related_name="records"
    )
    subjects = models.ManyToManyField(
        "Subject", blank=True, related_name="records"
    )
    publishers = models.ManyToManyField(
        "Publisher", blank=True, related_name="records"
    )
    locations = models.ManyToManyField(
        "Location", blank=True, related_name="records"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.record_id}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.record_id:
            if not self.pk:
                super().save(*args, **kwargs)
                self.record_id = generate_record_id(self.pk)
                kwargs["force_update"] = True
                kwargs.pop("force_insert", None)
            else:
                self.record_id = generate_record_id(self.pk)
        if not self.slug:
            source = self.title_romanized or self.title
            self.slug = slugify(source, allow_unicode=True)[:255]
        super().save(*args, **kwargs)

    def get_date_display(self):
        if self.date_of_publication_display:
            return self.date_of_publication_display
        if self.date_of_publication:
            return str(self.date_of_publication)
        return ""


class Author(models.Model):
    name = models.CharField(max_length=500)
    name_romanized = models.CharField(max_length=500, blank=True)
    viaf_id = models.CharField(max_length=50, blank=True, db_index=True)
    variant_names = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        if self.name_romanized:
            return f"{self.name} / {self.name_romanized}"
        return self.name


class Subject(models.Model):
    heading = models.CharField(max_length=500)
    heading_romanized = models.CharField(max_length=500, blank=True)
    source = models.CharField(
        max_length=10,
        choices=[("LC", "LC"), ("NLI", "NLI"), ("local", "Local")],
        blank=True,
    )

    class Meta:
        ordering = ["heading"]

    def __str__(self):
        return self.heading


class Publisher(models.Model):
    name = models.CharField(max_length=500)
    name_romanized = models.CharField(max_length=500, blank=True)
    place = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        if self.place:
            return f"{self.name} ({self.place})"
        return self.name


class Series(models.Model):
    title = models.CharField(max_length=500)
    title_romanized = models.CharField(max_length=500, blank=True)
    total_volumes = models.IntegerField(null=True, blank=True)
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="series_set",
    )

    class Meta:
        ordering = ["title"]
        verbose_name_plural = "series"

    def __str__(self):
        return self.title


class SeriesVolume(models.Model):
    series = models.ForeignKey(
        Series, on_delete=models.CASCADE, related_name="volumes"
    )
    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="series_volumes",
    )
    volume_number = models.CharField(max_length=50)
    held = models.BooleanField(default=True)

    class Meta:
        ordering = ["volume_number"]
        unique_together = [("series", "volume_number")]

    def __str__(self):
        status = "" if self.held else " (not held)"
        return f"{self.series.title} vol. {self.volume_number}{status}"


class Location(models.Model):
    label = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["label"]

    def __str__(self):
        return self.label


class ExternalIdentifier(models.Model):
    IDENTIFIER_TYPES = [
        ("ISBN", "ISBN"),
        ("LCCN", "LCCN"),
        ("LCC", "LC Classification"),
        ("DDC", "Dewey Decimal"),
        ("NLI", "NLI Control Number"),
        ("VIAF", "VIAF ID"),
        ("OCLC", "OCLC Number"),
    ]

    record = models.ForeignKey(
        Record, on_delete=models.CASCADE, related_name="external_identifiers"
    )
    identifier_type = models.CharField(max_length=10, choices=IDENTIFIER_TYPES)
    value = models.CharField(max_length=100)

    class Meta:
        unique_together = [("record", "identifier_type", "value")]
        ordering = ["identifier_type", "value"]

    def __str__(self):
        return f"{self.identifier_type}: {self.value}"


class TitlePageImage(models.Model):
    record = models.ForeignKey(
        Record,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="title_page_images",
    )
    image = models.ImageField(upload_to="title-pages/%Y/%m/%d/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    staged = models.BooleanField(default=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        if self.record:
            return f"Title page for {self.record.record_id}"
        return f"Staged image ({self.uploaded_at:%Y-%m-%d})"


class SeriesClaim(models.Model):
    """One person's in-progress attempt to catalog a run of volumes.

    A claim holds transient search and review state: which volumes were
    asked for, what each lookup turned up, and what the cataloger chose.
    ``Series`` and ``SeriesVolume`` hold what the collection actually
    contains. Keeping the two apart means an abandoned claim leaves no
    trace in the catalog, and a committed one adds only finished rows.

    Every foreign key out of a claim nulls on delete. A claim records
    work someone did, so removing the series it targeted, the account
    that made it, or the scan it started from must not take that record
    with it.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("committed", "Committed"),
        ("cancelled", "Cancelled"),
    ]

    series = models.ForeignKey(
        Series,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claims",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="series_claims",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    volume_spec = models.CharField(max_length=200)
    originating_scan = models.ForeignKey(
        "ingest.ScanResult",
        on_delete=models.SET_NULL,
        null=True,
        related_name="series_claims",
    )
    originating_volume_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        title = self.series.title if self.series else "unassigned series"
        return f"{title} vols. {self.volume_spec} ({self.status})"


class SeriesClaimRow(models.Model):
    """One volume within a claim, and what searching for it produced.

    ``search_status`` covers both what a lookup found and what the
    cataloger decided about it, because a row has one outcome and a
    single field keeps the two from contradicting each other.
    """

    SEARCH_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("searching", "Searching"),
        ("found", "Found"),
        ("no_match", "No match"),
        ("multiple", "Multiple matches"),
        ("manual_skip", "Skip"),
        ("manual_held", "Mark held"),
    ]

    claim = models.ForeignKey(
        SeriesClaim, on_delete=models.CASCADE, related_name="rows"
    )
    volume_number = models.CharField(max_length=50)
    search_status = models.CharField(
        max_length=20, choices=SEARCH_STATUS_CHOICES, default="pending"
    )
    candidate_records = models.JSONField(default=list, blank=True)
    selected_candidate_index = models.IntegerField(null=True, blank=True)
    created_record = models.ForeignKey(
        "catalog.Record",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="series_claim_rows",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["volume_number"]
        unique_together = [("claim", "volume_number")]

    def __str__(self):
        return f"vol. {self.volume_number} ({self.search_status})"
