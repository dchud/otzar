from django.db import migrations, models


def classify_existing_series(apps, schema_editor):
    """Keep the sets a person already declared, default the rest.

    Series rows predate the distinction between a work issued in parts
    and a publisher's line, so every one of them holds volume positions
    whether or not anybody can complete it. A gap placeholder is the one
    thing in the data that only a person makes: it is created from the
    volume specification typed on the series page, and it says "this set
    runs to here and we are missing these". A row carrying one was
    treated as completable by somebody, so it stays a work-set. The rest
    take the field default, which invents nothing, and a person promotes
    the ones that were sets.
    """
    Series = apps.get_model("catalog", "Series")
    with_gaps = set(
        Series.objects.filter(volumes__held=False).values_list("pk", flat=True)
    )
    Series.objects.filter(pk__in=with_gaps).update(kind="work")


def unclassify_existing_series(apps, schema_editor):
    """Reversing drops the kind along with the column; nothing to undo."""


def link_volume_records_as_members(apps, schema_editor):
    """Give every record already placed in a series its membership row.

    Membership and position were one thing before they were two, so the
    records that have a position are exactly the ones that belong.
    """
    SeriesVolume = apps.get_model("catalog", "SeriesVolume")
    Record = apps.get_model("catalog", "Record")
    through = Record.series.through
    through.objects.bulk_create(
        [
            through(record_id=record_id, series_id=series_id)
            for record_id, series_id in SeriesVolume.objects.filter(
                record__isnull=False
            ).values_list("record_id", "series_id")
        ],
        ignore_conflicts=True,
    )


def unlink_volume_records(apps, schema_editor):
    """Reversing drops the join table with the field; nothing to undo."""


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0008_remove_record_cover_url_recordcover"),
    ]

    operations = [
        migrations.AddField(
            model_name="record",
            name="series",
            field=models.ManyToManyField(
                blank=True, related_name="records", to="catalog.series"
            ),
        ),
        migrations.AddField(
            model_name="series",
            name="kind",
            field=models.CharField(
                choices=[
                    ("work", "Multi-volume work"),
                    ("imprint", "Publisher's series"),
                ],
                default="imprint",
                help_text=(
                    "Whether this is a work issued in parts, which can "
                    "be completed and can have gaps, or a publisher's "
                    "line, which cannot."
                ),
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="series",
            name="kind_source",
            field=models.CharField(
                choices=[
                    ("imported", "Read from a record"),
                    ("asserted", "Set by hand"),
                ],
                default="imported",
                help_text=(
                    "Set by hand once a person has decided the kind. "
                    "Incoming records stop changing it from then on."
                ),
                max_length=10,
            ),
        ),
        migrations.RunPython(
            classify_existing_series, unclassify_existing_series
        ),
        migrations.RunPython(
            link_volume_records_as_members, unlink_volume_records
        ),
    ]
