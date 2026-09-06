"""Look authors up in VIAF and record what it holds for them."""

from django.core.management.base import BaseCommand, CommandError

from catalog.models import Author
from ingest.authority import (
    LINKED,
    AuthorEnrichment,
    apply_author_enrichment,
    enrich_author_from_viaf,
)
from sources.viaf import VIAFClient


class Command(BaseCommand):
    help = (
        "Look up authors in VIAF and record the identifier and name forms "
        "it holds for each. Rows with a VIAF ID are skipped unless named "
        "with --author. One client serves the whole pass, so requests stay "
        "spaced by the configured delay: a pass over N authors takes "
        "roughly N to 4N times the delay in waiting, less whatever the "
        "response cache answers."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what VIAF returns without saving anything.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Look up at most this many authors.",
        )
        parser.add_argument(
            "--author",
            type=int,
            action="append",
            dest="author_ids",
            metavar="ID",
            help="Look up this author, linked or not. Repeatable.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        author_ids = options["author_ids"]
        limit = options["limit"]

        if author_ids:
            authors = Author.objects.filter(pk__in=author_ids).order_by("pk")
            missing = set(author_ids) - {author.pk for author in authors}
            if missing:
                ids = ", ".join(str(pk) for pk in sorted(missing))
                raise CommandError(f"no author with id {ids}")
        else:
            # Newest first: the rows a confirm created most recently are
            # the ones a pass exists for.
            authors = Author.objects.filter(viaf_id="").order_by("-pk")
        if limit is not None:
            authors = authors[:limit]
        authors = list(authors)

        client = VIAFClient()
        count = len(authors)
        low = count * client.delay
        high = 4 * count * client.delay
        self.stdout.write(
            f"{count} authors to look up, {client.delay:g}s between VIAF "
            f"requests: {low:.0f}s to {high:.0f}s of waiting, less what "
            "the cache answers."
        )

        tallies: dict[str, int] = {}
        for author in authors:
            enrichment = enrich_author_from_viaf(author, client=client)
            tallies[enrichment.outcome] = (
                tallies.get(enrichment.outcome, 0) + 1
            )
            self.stdout.write(
                f"  #{author.pk} {author}: {describe(enrichment, dry_run)}"
            )
            for other in enrichment.also_linked:
                self.stdout.write(
                    f"    VIAF {enrichment.viaf_id} is also on "
                    f"#{other.pk} {other}"
                )
            if not dry_run:
                apply_author_enrichment(enrichment)

        summary = ", ".join(
            f"{n} {outcome}" for outcome, n in sorted(tallies.items())
        )
        self.stdout.write(f"Done: {summary or 'nothing to look up'}.")


def describe(enrichment: AuthorEnrichment, dry_run: bool) -> str:
    """One line saying what the lookup found and what happens to it."""
    if enrichment.outcome != LINKED:
        return f"{enrichment.outcome} -- {enrichment.detail}"
    if enrichment.author.viaf_id:
        verb = "already"
    elif dry_run:
        verb = "would link to"
    else:
        verb = "linked to"
    count = len(enrichment.forms)
    forms = f"{count} new form{'' if count == 1 else 's'}"
    if dry_run and count:
        forms = f"would record {forms}"
    return f"{verb} VIAF {enrichment.viaf_id} {enrichment.detail}; {forms}"
