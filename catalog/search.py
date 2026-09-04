import re

from django.db import connection

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
    """
    existing = _table_columns()
    if existing == list(FTS_COLUMNS):
        return

    stale = bool(existing)
    rebuild_fts_table()
    if stale:
        _index_all_records()


def rebuild_fts_table():
    """Drop and recreate the FTS table, leaving it empty."""
    with connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {FTS_TABLE}")
    _create_fts_table()


def _index_all_records():
    """Index every record in the catalog into an empty FTS table."""
    from catalog.models import Record

    for record in Record.objects.prefetch_related(
        "authors", "subjects", "publishers", "external_identifiers"
    ).all():
        index_record(record)


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
    """Rebuild the entire FTS index from all records."""
    rebuild_fts_table()
    _index_all_records()
