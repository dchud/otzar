"""Management command to remove C1 control characters from stored text.

MARC brackets the leading article of a heading between a non-sorting
begin and end character so that sorting can skip it. Those convert to
U+0098 and U+009C, which no renderer displays, so a stored heading that
carries them reads as though it had stray whitespace in it.

The parser drops them on the way in. This repairs what was written
before that, and anything another import route lets through.
"""

from django.core.management.base import BaseCommand
from django.db import models

from catalog.models import Author, Publisher, Record, Subject
from catalog.search import ensure_fts_table, index_record
from sources.marc import strip_control_characters

# Scanned in report order. Repairing any of them changes what the FTS
# index holds for a record, because the index copies author, publisher
# and subject text into the record's row.
SCANNED_MODELS = (Record, Author, Publisher, Subject)


def text_field_names(model):
    """Return the names of *model*'s editable text fields.

    Read off the model rather than listed here, so a text field added
    later is scanned without anyone remembering to extend a list.

    Two kinds of column are left out. Non-editable ones hold generated
    values rather than transcribed text: ``Record.record_id`` is derived
    from the primary key and the FTS index is keyed on it, so rewriting
    one would orphan its index row. JSON ones hold a record as its
    source supplied it, which is kept verbatim.
    """
    return [
        field.name
        for field in model._meta.get_fields()
        if getattr(field, "concrete", False)
        and field.editable
        and isinstance(field, models.CharField | models.TextField)
    ]


def find_affected(model):
    """Yield ``(instance, changes)`` for each row carrying the characters.

    ``changes`` is a list of ``(field name, stored value, repaired
    value)`` triples, and is never empty.
    """
    field_names = text_field_names(model)
    for instance in model.objects.all():
        changes = []
        for name in field_names:
            stored = getattr(instance, name)
            repaired = strip_control_characters(stored)
            if repaired != stored:
                changes.append((name, stored, repaired))
        if changes:
            yield instance, changes


def indexed_records(instance):
    """Return the primary keys of the Records whose index text this feeds."""
    if isinstance(instance, Record):
        return [instance.pk]
    return list(instance.records.values_list("pk", flat=True))


def _label(instance):
    """Identify an instance in the report by whatever names it best."""
    record_id = getattr(instance, "record_id", "")
    return record_id if record_id else f"pk={instance.pk}"


class Command(BaseCommand):
    help = (
        "Remove MARC non-sorting delimiters and other C1 control "
        "characters from stored catalog text. Reports what it would "
        "change; pass --apply to write."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the repairs. Without it nothing is saved.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        if not apply_changes:
            self.stdout.write("REPORT ONLY — nothing will be written.\n")

        rows_by_model = {}
        field_total = 0
        record_pks = set()

        for model in SCANNED_MODELS:
            rows, fields = self._repair(model, apply_changes, record_pks)
            rows_by_model[model] = rows
            field_total += fields

        if apply_changes and record_pks:
            self._reindex(record_pks)

        self.stdout.write("\n--- Summary ---")
        for model, rows in rows_by_model.items():
            label = f"{model._meta.verbose_name_plural.title()} changed:"
            self.stdout.write(f"{label:<21}{rows}")
        self.stdout.write(f"{'Fields changed:':<21}{field_total}")
        reindexed = (
            "Records re-indexed:" if apply_changes else "Records to re-index:"
        )
        self.stdout.write(f"{reindexed:<21}{len(record_pks)}")

        if not apply_changes and field_total:
            self.stdout.write("\nRe-run with --apply to write the repairs.")

    def _repair(self, model, apply_changes, record_pks):
        """Repair *model*, returning ``(rows changed, fields changed)``.

        Adds to *record_pks* every Record whose indexed text a repair
        changed, whether the row repaired was the record itself or a
        heading attached to it.
        """
        rows = 0
        fields = 0

        for instance, changes in find_affected(model):
            for name, stored, repaired in changes:
                self.stdout.write(
                    f"  {model.__name__} {_label(instance)} {name}: "
                    f"{stored!r} -> {repaired!r}"
                )
                setattr(instance, name, repaired)
            rows += 1
            fields += len(changes)
            record_pks.update(indexed_records(instance))
            if apply_changes:
                instance.save()

        return rows, fields

    def _reindex(self, record_pks):
        ensure_fts_table()
        records = Record.objects.filter(pk__in=record_pks).prefetch_related(
            "authors", "subjects", "publishers", "external_identifiers"
        )
        for record in records:
            index_record(record)
