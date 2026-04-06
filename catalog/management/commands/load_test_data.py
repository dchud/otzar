from django.core.management.base import BaseCommand

from catalog.models import (
    Author,
    ExternalIdentifier,
    Location,
    Publisher,
    Record,
    Series,
    SeriesVolume,
    Subject,
)
from catalog.search import ensure_fts_table, index_record


class Command(BaseCommand):
    help = "Load representative test data for development and demos"

    def handle(self, *args, **options):
        ensure_fts_table()

        # Locations
        loc_main = Location.objects.get_or_create(label="Floor 1, Main Hall, Shelf A")[
            0
        ]
        loc_study = Location.objects.get_or_create(
            label="Floor 2, Study Room, Shelf B"
        )[0]
        loc_rare = Location.objects.get_or_create(label="Floor 1, Rare Books, Case 1")[
            0
        ]

        # Authors
        rambam = Author.objects.get_or_create(
            name="משה בן מימון",
            defaults={
                "name_romanized": "Maimonides, Moses ben Maimon",
                "viaf_id": "100185495",
                "variant_names": [
                    "Rambam",
                    "Maimonides",
                    "Moses ben Maimon",
                    "רמבם",
                    "משה בן מימון",
                ],
            },
        )[0]

        soloveitchik = Author.objects.get_or_create(
            name="יוסף דוב סולובייצ'יק",
            defaults={
                "name_romanized": "Soloveitchik, Joseph Dov",
                "viaf_id": "14820508",
                "variant_names": [
                    "Joseph B. Soloveitchik",
                    "The Rav",
                    "J.B. Soloveitchik",
                ],
            },
        )[0]

        karo = Author.objects.get_or_create(
            name="יוסף קארו",
            defaults={
                "name_romanized": "Karo, Joseph ben Ephraim",
                "viaf_id": "97224401",
                "variant_names": ["Joseph Caro", "Yosef Karo", "Maran"],
            },
        )[0]

        heschel = Author.objects.get_or_create(
            name="Abraham Joshua Heschel",
            defaults={
                "name_romanized": "Heschel, Abraham Joshua",
                "viaf_id": "37017121",
            },
        )[0]

        # Publishers
        mosad = Publisher.objects.get_or_create(
            name="מוסד הרב קוק",
            defaults={"name_romanized": "Mossad Harav Kook", "place": "Jerusalem"},
        )[0]

        jps = Publisher.objects.get_or_create(
            name="Jewish Publication Society",
            defaults={"place": "Philadelphia"},
        )[0]

        # Subjects
        halacha = Subject.objects.get_or_create(
            heading="Jewish law", defaults={"source": "LC"}
        )[0]
        philosophy = Subject.objects.get_or_create(
            heading="Jewish philosophy", defaults={"source": "LC"}
        )[0]
        Subject.objects.get_or_create(
            heading="Talmud -- Commentaries", defaults={"source": "LC"}
        )

        # Series
        mishneh_torah_series = Series.objects.get_or_create(
            title="משנה תורה",
            defaults={
                "title_romanized": "Mishneh Torah",
                "total_volumes": 14,
                "publisher": mosad,
            },
        )[0]

        # Records
        records_data = [
            {
                "title": "משנה תורה - ספר המדע",
                "title_romanized": "Mishneh Torah - Sefer ha-Madda",
                "date_of_publication": 1957,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "authors": [rambam],
                "subjects": [halacha, philosophy],
                "publishers": [mosad],
                "locations": [loc_main],
                "identifiers": [("VIAF", "176326832")],
                "series": (mishneh_torah_series, "1"),
            },
            {
                "title": "משנה תורה - ספר אהבה",
                "title_romanized": "Mishneh Torah - Sefer Ahavah",
                "date_of_publication": 1957,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "authors": [rambam],
                "subjects": [halacha],
                "publishers": [mosad],
                "locations": [loc_main],
                "series": (mishneh_torah_series, "2"),
            },
            {
                "title": "שולחן ערוך",
                "title_romanized": "Shulchan Aruch",
                "date_of_publication": 1565,
                "date_of_publication_display": 'שכ"ה [1565]',
                "place_of_publication": "Venice",
                "language": "heb",
                "authors": [karo],
                "subjects": [halacha],
                "locations": [loc_rare],
            },
            {
                "title": "Halakhic Man",
                "title_romanized": "",
                "date_of_publication": 1983,
                "place_of_publication": "Philadelphia",
                "language": "eng",
                "authors": [soloveitchik],
                "subjects": [halacha, philosophy],
                "publishers": [jps],
                "locations": [loc_study],
                "identifiers": [
                    ("ISBN", "0-8276-0222-7"),
                    ("LCCN", "83002948"),
                ],
            },
            {
                "title": "God in Search of Man",
                "date_of_publication": 1955,
                "place_of_publication": "New York",
                "language": "eng",
                "authors": [heschel],
                "subjects": [philosophy],
                "locations": [loc_study],
                "identifiers": [("LCCN", "55010050")],
            },
            {
                "title": "מורה נבוכים",
                "title_romanized": "Moreh Nevukhim",
                "subtitle": "Guide for the Perplexed",
                "date_of_publication": 1190,
                "date_of_publication_display": "ca. 1190",
                "place_of_publication": "Unknown",
                "language": "heb",
                "authors": [rambam],
                "subjects": [philosophy],
                "locations": [loc_rare],
                "identifiers": [("VIAF", "184868082")],
            },
        ]

        created_count = 0
        for data in records_data:
            authors = data.pop("authors", [])
            subjects = data.pop("subjects", [])
            publishers = data.pop("publishers", [])
            locations = data.pop("locations", [])
            identifiers = data.pop("identifiers", [])
            series_info = data.pop("series", None)

            record, created = Record.objects.get_or_create(
                title=data["title"],
                defaults=data,
            )

            if created:
                record.authors.set(authors)
                record.subjects.set(subjects)
                record.publishers.set(publishers)
                record.locations.set(locations)

                for id_type, id_value in identifiers:
                    ExternalIdentifier.objects.get_or_create(
                        record=record, identifier_type=id_type, value=id_value
                    )

                if series_info:
                    series, vol_num = series_info
                    SeriesVolume.objects.get_or_create(
                        series=series,
                        volume_number=vol_num,
                        defaults={"record": record},
                    )

                index_record(record)
                created_count += 1

        # Add gap volumes for Mishneh Torah (volumes 3-14 not held)
        for vol_num in range(3, 15):
            SeriesVolume.objects.get_or_create(
                series=mishneh_torah_series,
                volume_number=str(vol_num),
                defaults={"held": False},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {created_count} records, "
                f"{Author.objects.count()} authors, "
                f"{Series.objects.count()} series, "
                f"{Location.objects.count()} locations"
            )
        )
