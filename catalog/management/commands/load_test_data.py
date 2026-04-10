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
from catalog.search import ensure_fts_table, reindex_all


class Command(BaseCommand):
    help = "Load representative test data for development and demos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all existing catalog data before loading",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self._clear_all()

        ensure_fts_table()

        locations = self._create_locations()
        authors = self._create_authors()
        publishers = self._create_publishers()
        subjects = self._create_subjects()
        series_map = self._create_series(publishers)

        created_count = self._create_records(
            authors, publishers, subjects, locations, series_map
        )

        reindex_all()

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {created_count} new records "
                f"({Record.objects.count()} total). "
                f"{Author.objects.count()} authors, "
                f"{Publisher.objects.count()} publishers, "
                f"{Subject.objects.count()} subjects, "
                f"{Series.objects.count()} series, "
                f"{Location.objects.count()} locations."
            )
        )

    def _clear_all(self):
        """Remove all catalog data so the command can reload cleanly."""
        SeriesVolume.objects.all().delete()
        ExternalIdentifier.objects.all().delete()
        Record.objects.all().delete()
        Series.objects.all().delete()
        Author.objects.all().delete()
        Publisher.objects.all().delete()
        Subject.objects.all().delete()
        Location.objects.all().delete()
        self.stdout.write("Cleared existing catalog data.")

    def _create_locations(self):
        g = Location.objects.get_or_create
        return {
            "main": g(label="Floor 1, Main Hall, Shelf A")[0],
            "study": g(label="Floor 2, Study Room, Shelf B")[0],
            "rare": g(label="Floor 1, Rare Books, Case 1")[0],
            "ref": g(label="Floor 1, Reference, Shelf R")[0],
        }

    def _create_authors(self):
        g = Author.objects.get_or_create
        return {
            "rambam": g(
                name="משה בן מימון",
                defaults={
                    "name_romanized": "Maimonides, Moses ben Maimon",
                    "viaf_id": "100185495",
                    "variant_names": [
                        "Rambam",
                        "Maimonides",
                        "Moses ben Maimon",
                        "רמבם",
                    ],
                },
            )[0],
            "soloveitchik": g(
                name="יוסף דוב סולובייצ'יק",
                defaults={
                    "name_romanized": "Soloveitchik, Joseph Dov",
                    "viaf_id": "14820508",
                    "variant_names": [
                        "Joseph B. Soloveitchik",
                        "The Rav",
                    ],
                },
            )[0],
            "karo": g(
                name="יוסף קארו",
                defaults={
                    "name_romanized": "Karo, Joseph ben Ephraim",
                    "viaf_id": "97224401",
                    "variant_names": ["Joseph Caro", "Yosef Karo", "Maran"],
                },
            )[0],
            "heschel": g(
                name="Abraham Joshua Heschel",
                defaults={
                    "name_romanized": "Heschel, Abraham Joshua",
                    "viaf_id": "37017121",
                },
            )[0],
            "steinsaltz": g(
                name="עדין שטיינזלץ",
                defaults={
                    "name_romanized": "Steinsaltz, Adin",
                    "viaf_id": "30346247",
                    "variant_names": [
                        "Adin Even-Israel Steinsaltz",
                        "Rabbi Steinsaltz",
                    ],
                },
            )[0],
            "graetz": g(
                name="Heinrich Graetz",
                defaults={
                    "name_romanized": "Graetz, Heinrich",
                    "viaf_id": "14791833",
                },
            )[0],
            "baron": g(
                name="Salo Wittmayer Baron",
                defaults={
                    "name_romanized": "Baron, Salo Wittmayer",
                    "viaf_id": "36920292",
                },
            )[0],
            "agnon": g(
                name="שמואל יוסף עגנון",
                defaults={
                    "name_romanized": "Agnon, Shmuel Yosef",
                    "viaf_id": "56615336",
                    "variant_names": ["S.Y. Agnon", "Shai Agnon"],
                },
            )[0],
            "bialik": g(
                name="חיים נחמן ביאליק",
                defaults={
                    "name_romanized": "Bialik, Hayyim Nahman",
                    "viaf_id": "51710073",
                    "variant_names": ["C.N. Bialik", "H.N. Bialik"],
                },
            )[0],
            "jastrow": g(
                name="Marcus Jastrow",
                defaults={
                    "name_romanized": "Jastrow, Marcus",
                    "viaf_id": "67259786",
                },
            )[0],
            "even_shoshan": g(
                name="אברהם אבן-שושן",
                defaults={
                    "name_romanized": "Even-Shoshan, Avraham",
                    "viaf_id": "55513580",
                },
            )[0],
            "leibowitz": g(
                name="ישעיהו ליבוביץ'",
                defaults={
                    "name_romanized": "Leibowitz, Yeshayahu",
                    "viaf_id": "108308025",
                },
            )[0],
            "scholem": g(
                name="Gershom Scholem",
                defaults={
                    "name_romanized": "Scholem, Gershom",
                    "viaf_id": "46759938",
                },
            )[0],
            "buber": g(
                name="Martin Buber",
                defaults={
                    "name_romanized": "Buber, Martin",
                    "viaf_id": "27071894",
                },
            )[0],
            "rashi": g(
                name="שלמה יצחקי",
                defaults={
                    "name_romanized": "Rashi, Shlomo Yitzchaki",
                    "viaf_id": "59118514",
                    "variant_names": ["Rashi", "Rabbi Shlomo Yitzchaki"],
                },
            )[0],
            "peretz": g(
                name="יצחק לייבוש פרץ",
                defaults={
                    "name_romanized": "Peretz, Isaac Leib",
                    "viaf_id": "51703093",
                    "variant_names": ["I.L. Peretz"],
                },
            )[0],
            "rosenzweig": g(
                name="Franz Rosenzweig",
                defaults={
                    "name_romanized": "Rosenzweig, Franz",
                    "viaf_id": "41850363",
                },
            )[0],
        }

    def _create_publishers(self):
        g = Publisher.objects.get_or_create
        return {
            "mosad": g(
                name="מוסד הרב קוק",
                defaults={
                    "name_romanized": "Mossad Harav Kook",
                    "place": "Jerusalem",
                },
            )[0],
            "jps": g(
                name="Jewish Publication Society",
                defaults={"place": "Philadelphia"},
            )[0],
            "artscroll": g(
                name="Mesorah Publications",
                defaults={
                    "name_romanized": "Artscroll / Mesorah",
                    "place": "Brooklyn",
                },
            )[0],
            "koren": g(
                name="Koren Publishers",
                defaults={"place": "Jerusalem"},
            )[0],
            "magnes": g(
                name="Magnes Press",
                defaults={"place": "Jerusalem"},
            )[0],
            "schocken": g(
                name="Schocken Books",
                defaults={"place": "New York"},
            )[0],
            "columbia": g(
                name="Columbia University Press",
                defaults={"place": "New York"},
            )[0],
            "am_oved": g(
                name="עם עובד",
                defaults={"name_romanized": "Am Oved", "place": "Tel Aviv"},
            )[0],
            "dvir": g(
                name="דביר",
                defaults={"name_romanized": "Dvir", "place": "Tel Aviv"},
            )[0],
            "suhrkamp": g(
                name="Suhrkamp Verlag",
                defaults={"place": "Frankfurt am Main"},
            )[0],
            "lamed": g(
                name='הוצאת ל"ם',
                defaults={
                    "name_romanized": "Lamed Publishers",
                    "place": "Jerusalem",
                },
            )[0],
        }

    def _create_subjects(self):
        g = Subject.objects.get_or_create
        return {
            "halacha": g(heading="Jewish law", defaults={"source": "LC"})[0],
            "philosophy": g(heading="Jewish philosophy", defaults={"source": "LC"})[0],
            "talmud": g(heading="Talmud -- Commentaries", defaults={"source": "LC"})[0],
            "history": g(heading="Jews -- History", defaults={"source": "LC"})[0],
            "literature_heb": g(heading="Hebrew literature", defaults={"source": "LC"})[
                0
            ],
            "literature_yid": g(
                heading="Yiddish literature", defaults={"source": "LC"}
            )[0],
            "bible": g(heading="Bible -- Commentaries", defaults={"source": "LC"})[0],
            "mysticism": g(heading="Cabala", defaults={"source": "LC"})[0],
            "reference": g(
                heading="Hebrew language -- Dictionaries",
                defaults={"source": "LC"},
            )[0],
            "aramaic": g(
                heading="Aramaic language -- Dictionaries",
                defaults={"source": "LC"},
            )[0],
            "hasidism": g(heading="Hasidism", defaults={"source": "LC"})[0],
            "ethics": g(heading="Jewish ethics", defaults={"source": "LC"})[0],
        }

    def _create_series(self, publishers):
        g = Series.objects.get_or_create
        return {
            "mishneh_torah": g(
                title="משנה תורה",
                defaults={
                    "title_romanized": "Mishneh Torah",
                    "total_volumes": 14,
                    "publisher": publishers["mosad"],
                },
            )[0],
            "steinsaltz_talmud": g(
                title="תלמוד בבלי - מהדורת שטיינזלץ",
                defaults={
                    "title_romanized": "Talmud Bavli - Steinsaltz Edition",
                    "total_volumes": 22,
                    "publisher": publishers["koren"],
                },
            )[0],
            "graetz_history": g(
                title="Geschichte der Juden",
                defaults={
                    "title_romanized": "History of the Jews",
                    "total_volumes": 11,
                },
            )[0],
        }

    def _create_records(self, authors, publishers, subjects, locations, series_map):
        a = authors
        p = publishers
        s = subjects
        loc = locations
        mt = series_map["mishneh_torah"]
        st = series_map["steinsaltz_talmud"]
        gh = series_map["graetz_history"]

        records_data = [
            # --- Mishneh Torah volumes (series with gaps) ---
            {
                "title": "משנה תורה - ספר המדע",
                "title_romanized": "Mishneh Torah - Sefer ha-Madda",
                "date_of_publication": 1957,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "source_catalog": "NLI",
                "authors": [a["rambam"]],
                "subjects": [s["halacha"], s["philosophy"]],
                "publishers": [p["mosad"]],
                "locations": [loc["main"]],
                "identifiers": [("VIAF", "176326832")],
                "series": (mt, "1"),
            },
            {
                "title": "משנה תורה - ספר אהבה",
                "title_romanized": "Mishneh Torah - Sefer Ahavah",
                "date_of_publication": 1957,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "source_catalog": "NLI",
                "authors": [a["rambam"]],
                "subjects": [s["halacha"]],
                "publishers": [p["mosad"]],
                "locations": [loc["main"]],
                "series": (mt, "2"),
            },
            {
                "title": "משנה תורה - ספר זמנים",
                "title_romanized": "Mishneh Torah - Sefer Zemanim",
                "date_of_publication": 1957,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "source_catalog": "NLI",
                "authors": [a["rambam"]],
                "subjects": [s["halacha"]],
                "publishers": [p["mosad"]],
                "locations": [loc["main"]],
                "series": (mt, "3"),
            },
            # --- Steinsaltz Talmud volumes (series with gaps) ---
            {
                "title": "תלמוד בבלי - ברכות",
                "title_romanized": "Talmud Bavli - Berakhot",
                "subtitle": "מהדורת שטיינזלץ",
                "date_of_publication": 1967,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "source_catalog": "NLI",
                "authors": [a["steinsaltz"]],
                "subjects": [s["talmud"]],
                "publishers": [p["koren"]],
                "locations": [loc["main"]],
                "identifiers": [("ISBN", "965-301-001-3")],
                "series": (st, "1"),
            },
            {
                "title": "תלמוד בבלי - שבת",
                "title_romanized": "Talmud Bavli - Shabbat",
                "subtitle": "מהדורת שטיינזלץ",
                "date_of_publication": 1968,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "authors": [a["steinsaltz"]],
                "subjects": [s["talmud"]],
                "publishers": [p["koren"]],
                "locations": [loc["main"]],
                "series": (st, "2"),
            },
            {
                "title": "תלמוד בבלי - פסחים",
                "title_romanized": "Talmud Bavli - Pesahim",
                "subtitle": "מהדורת שטיינזלץ",
                "date_of_publication": 1969,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "authors": [a["steinsaltz"]],
                "subjects": [s["talmud"]],
                "publishers": [p["koren"]],
                "locations": [loc["main"]],
                "series": (st, "4"),
            },
            {
                "title": "תלמוד בבלי - בבא מציעא",
                "title_romanized": "Talmud Bavli - Bava Metzia",
                "subtitle": "מהדורת שטיינזלץ",
                "date_of_publication": 1975,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "authors": [a["steinsaltz"]],
                "subjects": [s["talmud"]],
                "publishers": [p["koren"]],
                "locations": [loc["main"]],
                "series": (st, "12"),
            },
            # --- Shulchan Aruch ---
            {
                "title": "שולחן ערוך - אורח חיים",
                "title_romanized": "Shulchan Aruch - Orach Chaim",
                "date_of_publication": 1870,
                "place_of_publication": "Vilna",
                "language": "heb",
                "authors": [a["karo"]],
                "subjects": [s["halacha"]],
                "locations": [loc["main"]],
            },
            # --- Philosophy ---
            {
                "title": "Halakhic Man",
                "date_of_publication": 1983,
                "place_of_publication": "Philadelphia",
                "language": "eng",
                "source_catalog": "LC",
                "authors": [a["soloveitchik"]],
                "subjects": [s["halacha"], s["philosophy"]],
                "publishers": [p["jps"]],
                "locations": [loc["study"]],
                "identifiers": [
                    ("ISBN", "0-8276-0222-7"),
                    ("LCCN", "83002948"),
                ],
            },
            {
                "title": "The Lonely Man of Faith",
                "date_of_publication": 1965,
                "place_of_publication": "New York",
                "language": "eng",
                "authors": [a["soloveitchik"]],
                "subjects": [s["philosophy"], s["ethics"]],
                "locations": [loc["study"]],
            },
            {
                "title": "God in Search of Man",
                "subtitle": "A Philosophy of Judaism",
                "date_of_publication": 1955,
                "place_of_publication": "New York",
                "language": "eng",
                "source_catalog": "LC",
                "authors": [a["heschel"]],
                "subjects": [s["philosophy"]],
                "locations": [loc["study"]],
                "identifiers": [("LCCN", "55010050")],
            },
            {
                "title": "מורה נבוכים",
                "title_romanized": "Moreh Nevukhim",
                "subtitle": "Guide for the Perplexed",
                "date_of_publication": 1910,
                "date_of_publication_display": "1910 (Ibn Tibbon translation)",
                "place_of_publication": "Vilna",
                "language": "heb",
                "authors": [a["rambam"]],
                "subjects": [s["philosophy"]],
                "publishers": [p["mosad"]],
                "locations": [loc["study"]],
                "identifiers": [("VIAF", "184868082")],
            },
            {
                "title": "Ich und Du",
                "title_romanized": "",
                "subtitle": "",
                "date_of_publication": 1923,
                "place_of_publication": "Leipzig",
                "language": "ger",
                "authors": [a["buber"]],
                "subjects": [s["philosophy"]],
                "publishers": [p["suhrkamp"]],
                "locations": [loc["study"]],
            },
            {
                "title": "Der Stern der Erlosung",
                "title_romanized": "",
                "subtitle": "",
                "date_of_publication": 1921,
                "place_of_publication": "Frankfurt am Main",
                "language": "ger",
                "authors": [a["rosenzweig"]],
                "subjects": [s["philosophy"]],
                "publishers": [p["suhrkamp"]],
                "locations": [loc["study"]],
                "notes": "First edition",
            },
            {
                "title": "שיחות על פרשיות השבוע",
                "title_romanized": "Sihot al Parashot ha-Shavua",
                "subtitle": "",
                "date_of_publication": 2000,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "authors": [a["leibowitz"]],
                "subjects": [s["bible"], s["philosophy"]],
                "publishers": [p["lamed"]],
                "locations": [loc["study"]],
            },
            # --- History ---
            {
                "title": "Geschichte der Juden, Band 1",
                "title_romanized": "History of the Jews, vol. 1",
                "subtitle": "Von den altesten Zeiten bis auf die Gegenwart",
                "date_of_publication": 1853,
                "place_of_publication": "Leipzig",
                "language": "ger",
                "source_catalog": "DNB",
                "authors": [a["graetz"]],
                "subjects": [s["history"]],
                "locations": [loc["rare"]],
                "series": (gh, "1"),
            },
            {
                "title": "Geschichte der Juden, Band 3",
                "title_romanized": "History of the Jews, vol. 3",
                "date_of_publication": 1856,
                "place_of_publication": "Leipzig",
                "language": "ger",
                "source_catalog": "DNB",
                "authors": [a["graetz"]],
                "subjects": [s["history"]],
                "locations": [loc["rare"]],
                "series": (gh, "3"),
            },
            {
                "title": "A Social and Religious History of the Jews",
                "subtitle": "Ancient Times",
                "date_of_publication": 1952,
                "place_of_publication": "New York",
                "language": "eng",
                "source_catalog": "LC",
                "authors": [a["baron"]],
                "subjects": [s["history"]],
                "publishers": [p["columbia"]],
                "locations": [loc["study"]],
                "identifiers": [("LCCN", "52001824")],
            },
            # --- Mysticism ---
            {
                "title": "Major Trends in Jewish Mysticism",
                "date_of_publication": 1941,
                "place_of_publication": "Jerusalem",
                "language": "eng",
                "authors": [a["scholem"]],
                "subjects": [s["mysticism"], s["history"]],
                "publishers": [p["schocken"]],
                "locations": [loc["study"]],
                "identifiers": [("ISBN", "0-8052-0005-7")],
            },
            # --- Literature ---
            {
                "title": "סיפורי אהבים",
                "title_romanized": "Sipure ahavim",
                "subtitle": "",
                "date_of_publication": 1931,
                "place_of_publication": "Berlin",
                "language": "heb",
                "authors": [a["agnon"]],
                "subjects": [s["literature_heb"]],
                "publishers": [p["schocken"]],
                "locations": [loc["main"]],
            },
            {
                "title": "תמול שלשום",
                "title_romanized": "Temol shilshom",
                "subtitle": "",
                "date_of_publication": 1945,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "authors": [a["agnon"]],
                "subjects": [s["literature_heb"]],
                "publishers": [p["schocken"]],
                "locations": [loc["main"]],
            },
            {
                "title": "כל שירי ח. נ. ביאליק",
                "title_romanized": "Kol shire H.N. Bialik",
                "date_of_publication": 1933,
                "place_of_publication": "Tel Aviv",
                "language": "heb",
                "authors": [a["bialik"]],
                "subjects": [s["literature_heb"]],
                "publishers": [p["dvir"]],
                "locations": [loc["main"]],
            },
            {
                "title": "אלע ווערק",
                "title_romanized": "Ale verk",
                "subtitle": "געזאמלטע שריפטן",
                "date_of_publication": 1920,
                "place_of_publication": "New York",
                "language": "yid",
                "authors": [a["peretz"]],
                "subjects": [s["literature_yid"]],
                "locations": [loc["main"]],
                "notes": "Collected works in Yiddish",
            },
            # --- Reference ---
            {
                "title": "A Dictionary of the Targumim, the Talmud Babli and Yerushalmi, and the Midrashic Literature",
                "title_romanized": "",
                "subtitle": "",
                "date_of_publication": 1903,
                "place_of_publication": "London",
                "language": "eng",
                "source_catalog": "LC",
                "authors": [a["jastrow"]],
                "subjects": [s["aramaic"], s["reference"]],
                "locations": [loc["ref"]],
                "identifiers": [("LCCN", "03018513")],
                "notes": "The standard Aramaic-English dictionary for Talmud study",
            },
            {
                "title": "המלון החדש",
                "title_romanized": "ha-Milon he-hadash",
                "subtitle": "",
                "date_of_publication": 2003,
                "place_of_publication": "Jerusalem",
                "language": "heb",
                "source_catalog": "NLI",
                "authors": [a["even_shoshan"]],
                "subjects": [s["reference"]],
                "publishers": [p["am_oved"]],
                "locations": [loc["ref"]],
                "identifiers": [("ISBN", "965-13-1560-5")],
            },
            # --- Rashi commentary (Aramaic) ---
            {
                "title": 'פירוש רש"י על התורה',
                "title_romanized": "Perush Rashi al ha-Torah",
                "date_of_publication": 1880,
                "place_of_publication": "Vilna",
                "language": "heb",
                "authors": [a["rashi"]],
                "subjects": [s["bible"]],
                "locations": [loc["main"]],
                "notes": "Includes Aramaic terms and explanations",
            },
        ]

        created_count = 0
        for data in records_data:
            rec_authors = data.pop("authors", [])
            rec_subjects = data.pop("subjects", [])
            rec_publishers = data.pop("publishers", [])
            rec_locations = data.pop("locations", [])
            rec_identifiers = data.pop("identifiers", [])
            series_info = data.pop("series", None)
            rec_notes = data.pop("notes", "")

            record, created = Record.objects.get_or_create(
                title=data["title"],
                defaults={**data, "notes": rec_notes},
            )

            if created:
                record.authors.set(rec_authors)
                record.subjects.set(rec_subjects)
                record.publishers.set(rec_publishers)
                record.locations.set(rec_locations)

                for id_type, id_value in rec_identifiers:
                    ExternalIdentifier.objects.get_or_create(
                        record=record,
                        identifier_type=id_type,
                        value=id_value,
                    )

                if series_info:
                    series_obj, vol_num = series_info
                    SeriesVolume.objects.get_or_create(
                        series=series_obj,
                        volume_number=vol_num,
                        defaults={"record": record, "held": True},
                    )

                created_count += 1

        # Add gap volumes for Mishneh Torah (vols 4-14 not held)
        for vol_num in range(4, 15):
            SeriesVolume.objects.get_or_create(
                series=mt,
                volume_number=str(vol_num),
                defaults={"held": False},
            )

        # Add gap volumes for Steinsaltz Talmud (selected gaps)
        for vol_num in [
            3,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
        ]:
            SeriesVolume.objects.get_or_create(
                series=st,
                volume_number=str(vol_num),
                defaults={"held": False},
            )

        # Add gap volumes for Graetz History (vols 2, 4-11 not held)
        for vol_num in [2, 4, 5, 6, 7, 8, 9, 10, 11]:
            SeriesVolume.objects.get_or_create(
                series=gh,
                volume_number=str(vol_num),
                defaults={"held": False},
            )

        return created_count
