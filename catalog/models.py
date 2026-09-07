import os
from typing import ClassVar
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files.base import ContentFile
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
    volume_part_number = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            "Designation of the part of a multi-part title this record "
            'describes, from MARC 245 $n: "Volume 2", "Bd. 4, T. 2".'
        ),
    )
    volume_part_title = models.CharField(
        max_length=500,
        blank=True,
        help_text=(
            'Name of that part, from MARC 245 $p: "Sefer Mishpatim". '
            "A part title, so it is as long as any other title."
        ),
    )
    statement_of_responsibility = models.TextField(
        blank=True,
        help_text=(
            "Responsibility for the work as transcribed from the item, "
            "from MARC 245 $c. Where the added entries carry no relator "
            "term, this is the only record of which contributor did "
            "what."
        ),
    )
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
    notes = models.TextField(blank=True)
    provenance = models.TextField(
        blank=True,
        help_text=(
            "Ownership history of this copy in prose: former owners, how "
            "it was acquired, where it has been. Transcribe a bookplate, "
            "a dedication or a stamp in its own field instead."
        ),
    )
    # The marks of ownership the copy carries, transcribed as they
    # read. Provenance says who owned the item; these say what the item
    # itself shows for it. They are text rather than CharFields because
    # a transcription has no width worth picking: a bookplate can carry
    # a motto and a donor line, a dedication runs to a paragraph, and a
    # copy can bear several stamps, each on its own line.
    bookplate_text = models.TextField(
        blank=True,
        help_text=(
            "Text of any bookplate pasted into this copy, including the "
            "owner's name and any motto."
        ),
    )
    dedication_text = models.TextField(
        blank=True,
        help_text=(
            "Text of any handwritten dedication or presentation "
            "inscription, with who wrote it for whom, if the "
            "inscription says."
        ),
    )
    stamp_text = models.TextField(
        blank=True,
        help_text=(
            "Text of any stamp on this copy — a library, a "
            "bookseller, a private collection. One stamp per line."
        ),
    )
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
    # Which series this record belongs to, whatever kind they are. A
    # record's other groupings are all plain many-to-many, and series
    # membership is the same fact: this book is one of those. Where it
    # sits within one, when the series is a work-set with positions, is
    # SeriesVolume.
    series = models.ManyToManyField(
        "Series", blank=True, related_name="records"
    )

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]

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
        ordering: ClassVar[list[str]] = ["name"]

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
        ordering: ClassVar[list[str]] = ["heading"]

    def __str__(self):
        return self.heading


class Publisher(models.Model):
    name = models.CharField(max_length=500)
    name_romanized = models.CharField(max_length=500, blank=True)
    place = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["name"]

    def __str__(self):
        if self.place:
            return f"{self.name} ({self.place})"
        return self.name


class Series(models.Model):
    """A series title, and otzar's opinion of what kind of thing it is.

    A 490 or 830 series statement carries two different things under one
    field. Some name a work issued in parts -- Talmud Bavli, Miqraot
    Gedolot -- which somebody sets out to complete and can be missing a
    volume of. Others name a publisher's line -- ArtScroll, Studia
    Judaica -- whose books share nothing but their publisher, where
    volume 3 is not something anyone holds or lacks.

    ``kind`` is which of the two this row is. Only a work-set has
    positions and gaps; a publisher's series has members and nothing
    else, because a gap placeholder asserts that a volume exists and is
    not held, and that is false of a line no one completes.

    A numbered monographic series -- ``Schriften des Institutum Judaicum
    in Berlin ; Nr. 38`` -- is a publisher's series whose books are
    counted. It is not a third kind here: the number says the publisher
    keeps a running count, not that the books are one work, and nothing
    downstream would branch on it. Whether a number is present is a
    fact about a record, and naming a kind for it would put in a
    category what the data already says.
    """

    KIND_WORK = "work"
    KIND_IMPRINT = "imprint"
    KIND_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (KIND_WORK, "Multi-volume work"),
        (KIND_IMPRINT, "Publisher's series"),
    ]

    # Where the kind came from. An imported kind was inferred from a
    # record; an asserted one is what a person said, and no incoming
    # record may overwrite it. The vocabulary is the one the rest of
    # the set work uses for the same distinction.
    SOURCE_IMPORTED = "imported"
    SOURCE_ASSERTED = "asserted"
    KIND_SOURCE_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (SOURCE_IMPORTED, "Read from a record"),
        (SOURCE_ASSERTED, "Set by hand"),
    ]

    title = models.CharField(max_length=500)
    title_romanized = models.CharField(max_length=500, blank=True)
    total_volumes = models.IntegerField(null=True, blank=True)
    kind = models.CharField(
        max_length=10,
        choices=KIND_CHOICES,
        default=KIND_IMPRINT,
        help_text=(
            "Whether this is a work issued in parts, which can be "
            "completed and can have gaps, or a publisher's line, which "
            "cannot."
        ),
    )
    kind_source = models.CharField(
        max_length=10,
        choices=KIND_SOURCE_CHOICES,
        default=SOURCE_IMPORTED,
        help_text=(
            "Set by hand once a person has decided the kind. Incoming "
            "records stop changing it from then on."
        ),
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="series_set",
    )

    class Meta:
        ordering: ClassVar[list[str]] = ["title"]
        verbose_name_plural = "series"

    def __str__(self):
        return self.title

    @property
    def is_work_set(self) -> bool:
        """Whether this series has volumes somebody can complete."""
        return self.kind == self.KIND_WORK


class SeriesVolume(models.Model):
    """One position in a work-set, held or waiting to be.

    Membership in a series is ``Record.series``; this says where in the
    set a record sits, which only a work-set has. A row with no record
    is a gap: a volume the set is known to contain and the collection
    does not hold.
    """

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
        ordering: ClassVar[list[str]] = ["volume_number"]
        unique_together: ClassVar[list[tuple[str, str]]] = [
            ("series", "volume_number")
        ]

    def __str__(self):
        status = "" if self.held else " (not held)"
        if not self.volume_number:
            return f"{self.series.title} (unnumbered){status}"
        return f"{self.series.title} vol. {self.volume_number}{status}"


class Location(models.Model):
    label = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["label"]

    def __str__(self):
        return self.label


class ExternalIdentifier(models.Model):
    IDENTIFIER_TYPES: ClassVar[list[tuple[str, str]]] = [
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
        unique_together: ClassVar[list[tuple[str, str, str]]] = [
            ("record", "identifier_type", "value")
        ]
        ordering: ClassVar[list[str]] = ["identifier_type", "value"]

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
        ordering: ClassVar[list[str]] = ["-uploaded_at"]

    def __str__(self):
        if self.record:
            return f"Title page for {self.record.record_id}"
        return f"Staged image ({self.uploaded_at:%Y-%m-%d})"


class RecordCover(models.Model):
    """An edition cover image fetched from a third-party source and
    cached locally.

    Kept under its own prefix (``covers/``) rather than sharing
    ``title-pages/``: a cover belongs to Open Library, not to this
    collection, and can be re-fetched at will if it is lost. A
    photograph of a title page cannot be retaken once the book is sold,
    so the two need different backup and retention rules -- one tree
    cannot express both.

    One record has at most one cover, hence a one-to-one rather than
    the foreign key ``TitlePageImage`` uses: a record can carry several
    photographs of the copy it holds, but Open Library offers a single
    edition image.
    """

    record = models.OneToOneField(
        Record, on_delete=models.CASCADE, related_name="cover"
    )
    image = models.ImageField(upload_to="covers/%Y/%m/%d/")
    source_url = models.URLField(
        max_length=500,
        help_text=(
            "Where the image was fetched from, kept for attribution "
            "and for re-fetching if the stored file is lost."
        ),
    )
    fetched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cover for {self.record.record_id}"

    @classmethod
    def store(cls, record, source_url, content):
        """Save cover bytes a lookup already retrieved.

        Takes the URL and bytes an :mod:`sources.covers` lookup already
        holds, so nothing is fetched twice. Replaces any cover already
        stored for this record.
        """
        extension = os.path.splitext(urlsplit(source_url).path)[1] or ".jpg"
        filename = f"{record.record_id}{extension}"
        cover, _ = cls.objects.get_or_create(record=record)
        cover.source_url = source_url
        cover.image.save(filename, ContentFile(content), save=True)
        return cover


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

    STATUS_CHOICES: ClassVar[list[tuple[str, str]]] = [
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
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self):
        title = self.series.title if self.series else "unassigned series"
        return f"{title} vols. {self.volume_spec} ({self.status})"


class SeriesClaimRow(models.Model):
    """One volume within a claim, and what searching for it produced.

    ``search_status`` covers both what a lookup found and what the
    cataloger decided about it, because a row has one outcome and a
    single field keeps the two from contradicting each other.
    """

    SEARCH_STATUS_CHOICES: ClassVar[list[tuple[str, str]]] = [
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
        ordering: ClassVar[list[str]] = ["volume_number"]
        unique_together: ClassVar[list[tuple[str, str]]] = [
            ("claim", "volume_number")
        ]

    def __str__(self):
        return f"vol. {self.volume_number} ({self.search_status})"
