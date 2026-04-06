import re

from django.db import connection

FTS_TABLE = "catalog_fts"

# Punctuation that FTS5 treats as syntax or that MARC leaves as trailing noise
_PUNCT_RE = re.compile(r"[,;:!?@#$%^&*()\[\]{}<>=/\\|~`]")


def _clean(text):
    """Strip MARC/FTS punctuation from text for indexing and searching."""
    if not text:
        return ""
    return _PUNCT_RE.sub(" ", text).strip()


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
                publishers,
                place,
                notes,
                identifiers
            )
            """
        )


def rebuild_fts_table():
    """Drop and recreate the FTS table (needed when schema changes)."""
    with connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {FTS_TABLE}")
    ensure_fts_table()


def index_record(record):
    """Add or update a record in the FTS index."""
    authors = " ".join(
        _clean(f"{a.name} {a.name_romanized}") for a in record.authors.all()
    )
    subjects = " ".join(
        _clean(f"{s.heading} {s.heading_romanized}") for s in record.subjects.all()
    )
    publishers = " ".join(
        _clean(f"{p.name} {p.name_romanized}") for p in record.publishers.all()
    )
    identifiers = " ".join(ei.value for ei in record.external_identifiers.all())

    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {FTS_TABLE} WHERE record_id = %s", [record.record_id]
        )
        cursor.execute(
            f"""
            INSERT INTO {FTS_TABLE}
                (record_id, title, title_romanized, subtitle, authors,
                 subjects, publishers, place, notes, identifiers)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                record.record_id,
                _clean(record.title),
                _clean(record.title_romanized),
                _clean(record.subtitle),
                authors,
                subjects,
                publishers,
                _clean(record.place_of_publication),
                _clean(record.notes),
                identifiers,
            ],
        )


def remove_from_index(record_id):
    """Remove a record from the FTS index."""
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {FTS_TABLE} WHERE record_id = %s", [record_id])


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
    from catalog.models import Record

    rebuild_fts_table()

    for record in Record.objects.prefetch_related(
        "authors", "subjects", "publishers", "external_identifiers"
    ).all():
        index_record(record)
