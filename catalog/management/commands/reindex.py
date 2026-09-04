from django.core.management.base import BaseCommand

from catalog.search import reindex_all


class Command(BaseCommand):
    help = "Rebuild the full-text search index from the catalog records"

    def handle(self, *args, **options):
        indexed, skipped = reindex_all()
        self.stdout.write(f"Indexed {indexed} record(s).")
        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped {len(skipped)} record(s) that could not be "
                    f"indexed: {', '.join(skipped)}"
                )
            )
