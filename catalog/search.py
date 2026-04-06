from django.db import connection

FTS_TABLE = "catalog_fts"


def ensure_fts_table():
    """Create the FTS5 virtual table if it doesn't exist."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE}
            USING fts5(
                record_id UNINDEXED,
                title,
                title_romanized,
                subtitle,
                authors,
                subjects,
                notes
            )
            """
        )


def index_record(record):
    """Add or update a record in the FTS index."""

    authors = " ".join(
        f"{a.name} {a.name_romanized}".strip() for a in record.authors.all()
    )
    subjects = " ".join(
        f"{s.heading} {s.heading_romanized}".strip() for s in record.subjects.all()
    )

    with connection.cursor() as cursor:
        # Remove old entry if exists
        cursor.execute(
            f"DELETE FROM {FTS_TABLE} WHERE record_id = %s", [record.record_id]
        )
        cursor.execute(
            f"""
            INSERT INTO {FTS_TABLE}
                (record_id, title, title_romanized, subtitle, authors, subjects, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [
                record.record_id,
                record.title,
                record.title_romanized,
                record.subtitle,
                authors,
                subjects,
                record.notes,
            ],
        )


def remove_from_index(record_id):
    """Remove a record from the FTS index."""
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {FTS_TABLE} WHERE record_id = %s", [record_id])


def _sanitize_query(query):
    """Sanitize a query string for FTS5.

    FTS5 treats punctuation and certain words as syntax. Strip characters
    that cause parse errors and wrap each term in double quotes for literal
    matching.
    """
    import re

    # Remove characters that FTS5 treats as syntax
    cleaned = re.sub(r"[,;:!?@#$%^&*()\[\]{}<>=/\\|~`]", " ", query)
    # Split into words, wrap each in quotes for literal matching
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

    # Preserve FTS rank ordering
    id_to_rank = {r[0]: r[1] for r in results}
    return sorted(records, key=lambda r: id_to_rank.get(r.record_id, 0))


def reindex_all():
    """Rebuild the entire FTS index from all records."""
    from catalog.models import Record

    ensure_fts_table()
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {FTS_TABLE}")

    for record in Record.objects.prefetch_related("authors", "subjects").all():
        index_record(record)
