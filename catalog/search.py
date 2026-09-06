import logging
import re

from django.db import connection, transaction

logger = logging.getLogger(__name__)

FTS_TABLE = "catalog_fts"

# Columns fed straight from a text attribute on Record, mapped to the
# attribute they hold. Making another Record field searchable means
# adding one entry here: the table schema, the insert statement and the
# indexed values all follow from this mapping, so they cannot drift
# apart.
FTS_TEXT_COLUMNS = {
    "title": "title",
    "title_romanized": "title_romanized",
    "subtitle": "subtitle",
    "place": "place_of_publication",
    "notes": "notes",
    "provenance": "provenance",
    "bookplate": "bookplate_text",
    "dedication": "dedication_text",
    "stamp": "stamp_text",
}

# Columns assembled from related objects rather than a single attribute.
FTS_RELATED_COLUMNS = ("authors", "subjects", "publishers", "identifiers")

# The full column list, in the order the table declares them.
FTS_COLUMNS = ("record_id", *FTS_TEXT_COLUMNS, *FTS_RELATED_COLUMNS)

# Punctuation that FTS5 treats as syntax or that MARC leaves as trailing noise
_PUNCT_RE = re.compile(r"[,;:!?@#$%^&*()\[\]{}<>=/\\|~`]")


def _clean(text):
    """Strip MARC/FTS punctuation from text for indexing and searching."""
    if not text:
        return ""
    return _PUNCT_RE.sub(" ", text).strip()


def _table_columns():
    """Return the FTS table's columns, or an empty list if it has none."""
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({FTS_TABLE})")
        return [row[1] for row in cursor.fetchall()]


def _create_fts_table():
    """Create the FTS5 virtual table from the current column list."""
    columns = ",\n".join(
        f"{name} UNINDEXED" if name == "record_id" else name
        for name in FTS_COLUMNS
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} "
            f"USING fts5({columns})"
        )


def ensure_fts_table():
    """Create the FTS5 virtual table, rebuilding it if its shape is stale.

    The table is not a Django model, so its column list sits outside the
    migration system: a database keeps whatever columns its table was
    created with, and an insert supplying a different number of values
    fails. A table whose columns do not match the current list is
    therefore dropped, recreated and repopulated from the records
    themselves. That is what makes a change to the column list take
    effect on a catalog already in use, and not only in a database
    created from scratch.

    The shape is the only thing this can compare cheaply -- it runs
    ahead of every search, so it cannot go counting records -- and a
    table with the right columns and no rows looks exactly like one
    that is up to date. `reindex_all` is what keeps that state from
    arising: it recreates and fills the table in a single transaction,
    so an interruption between the two rolls back to the table that was
    working, which fails the comparison here and gets rebuilt on the
    next call.
    """
    if _table_columns() == list(FTS_COLUMNS):
        return
    reindex_all()


def _rebuild_fts_table():
    """Drop and recreate the FTS table, leaving it empty."""
    with connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {FTS_TABLE}")
    _create_fts_table()


def _index_all_records():
    """Index every record in the catalog into an empty FTS table.

    A record the index cannot hold is skipped and reported rather than
    aborting the rebuild: the index serves discovery, and one record
    whose text the index chokes on should not cost the catalog its
    search. A rebuild that indexes nothing at all is a different
    failure -- systematic, not per-record -- so the first error is
    raised rather than swallowed.

    Returns ``(indexed, skipped)``: the number of records indexed and
    the ids of the ones that were not.
    """
    from catalog.models import Record

    indexed = 0
    skipped = []
    first_error = None

    for record in Record.objects.prefetch_related(
        "authors", "subjects", "publishers", "external_identifiers"
    ).all():
        try:
            # A savepoint per record, so a database error rolls back to
            # a usable transaction instead of poisoning the rebuild.
            with transaction.atomic():
                index_record(record)
        except Exception as error:
            skipped.append(record.record_id)
            if first_error is None:
                first_error = error
            logger.warning(
                "Could not index record %s: %s", record.record_id, error
            )
        else:
            indexed += 1

    if skipped and not indexed:
        raise first_error

    return indexed, skipped


def _row_values(record):
    """Return one record's indexed values, ordered to match FTS_COLUMNS."""
    row = {"record_id": record.record_id}
    for column, attribute in FTS_TEXT_COLUMNS.items():
        row[column] = _clean(getattr(record, attribute))
    row["authors"] = " ".join(
        _clean(f"{a.name} {a.name_romanized}") for a in record.authors.all()
    )
    row["subjects"] = " ".join(
        _clean(f"{s.heading} {s.heading_romanized}")
        for s in record.subjects.all()
    )
    row["publishers"] = " ".join(
        _clean(f"{p.name} {p.name_romanized}") for p in record.publishers.all()
    )
    row["identifiers"] = " ".join(
        ei.value for ei in record.external_identifiers.all()
    )
    return [row[column] for column in FTS_COLUMNS]


def index_record(record):
    """Add or update a record in the FTS index."""
    columns = ", ".join(FTS_COLUMNS)
    placeholders = ", ".join(["%s"] * len(FTS_COLUMNS))

    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {FTS_TABLE} WHERE record_id = %s", [record.record_id]
        )
        cursor.execute(
            f"INSERT INTO {FTS_TABLE} ({columns}) VALUES ({placeholders})",
            _row_values(record),
        )


def remove_from_index(record_id):
    """Remove a record from the FTS index."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {FTS_TABLE} WHERE record_id = %s", [record_id]
        )


def _sanitize_query(query):
    """Sanitize a query string for FTS5."""
    cleaned = _clean(query)
    words = [w.strip() for w in cleaned.split() if w.strip()]
    if not words:
        return None
    return " ".join(f'"{w}"' for w in words)


def search(query, limit=50):
    """Search the FTS index. Returns a list of (record_id, rank) tuples."""
    ensure_fts_table()
    if not query or not query.strip():
        return []

    sanitized = _sanitize_query(query)
    if not sanitized:
        return []

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT record_id, rank
            FROM {FTS_TABLE}
            WHERE {FTS_TABLE} MATCH %s
            ORDER BY rank
            LIMIT %s
            """,
            [sanitized, limit],
        )
        return cursor.fetchall()


def search_records(query, limit=50):
    """Search and return Record instances, ordered by relevance."""
    from catalog.models import Record

    results = search(query, limit)
    if not results:
        return Record.objects.none()

    record_ids = [r[0] for r in results]
    records = Record.objects.filter(record_id__in=record_ids)

    id_to_rank = {r[0]: r[1] for r in results}
    return sorted(records, key=lambda r: id_to_rank.get(r.record_id, 0))


def reindex_all():
    """Rebuild the entire FTS index from all records, in one transaction.

    Returns ``(indexed, skipped)``: the number of records indexed and
    the ids of the ones that were not.
    """
    with transaction.atomic():
        _rebuild_fts_table()
        return _index_all_records()


def reindex_records(record_ids):
    """Bring the index into line with the named records.

    Each id is reindexed from the record that holds it, or dropped from
    the index if no record holds it any more. One call therefore covers
    an edit, a delete, and a change to an author, subject or publisher
    whose text the record's index entry is built from.
    """
    from catalog.models import Record

    record_ids = list(dict.fromkeys(record_ids))
    if not record_ids:
        return

    ensure_fts_table()
    records = {
        record.record_id: record
        for record in Record.objects.filter(
            record_id__in=record_ids
        ).prefetch_related(
            "authors", "subjects", "publishers", "external_identifiers"
        )
    }
    for record_id in record_ids:
        record = records.get(record_id)
        if record is None:
            remove_from_index(record_id)
        else:
            index_record(record)
