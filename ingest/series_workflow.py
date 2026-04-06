"""Series detection and volume management workflow.

Provides helpers for identifying series information in parsed MARC data,
matching against existing Series records, and creating SeriesVolume entries
(including gap placeholders for volumes not yet held).
"""

import re

from catalog.models import Record, Series, SeriesVolume

from ingest.authority import normalize_for_comparison


def detect_series_from_marc(parsed_record: dict) -> dict | None:
    """Check parsed MARC data for series information.

    Expects the dict returned by ``sources.marc.parse_record``, which
    populates ``series_title`` and ``series_volume``.

    Returns a dict with ``series_title`` and ``series_volume`` keys, or
    None if no series information is present.
    """
    series_title = (parsed_record.get("series_title") or "").strip()
    series_volume = (parsed_record.get("series_volume") or "").strip()

    if not series_title:
        return None

    return {
        "series_title": series_title,
        "series_volume": series_volume,
    }


def find_matching_series(series_title: str) -> Series | None:
    """Find an existing Series matching *series_title*.

    Tries an exact title match first, then falls back to a normalized
    comparison across all Series records.
    """
    if not series_title:
        return None

    # Exact match
    exact = Series.objects.filter(title=series_title).first()
    if exact:
        return exact

    # Normalized comparison
    title_norm = normalize_for_comparison(series_title)
    for series in Series.objects.all():
        if normalize_for_comparison(series.title) == title_norm:
            return series

    return None


def _parse_volume_spec(volume_specs: str | list) -> list[str]:
    """Parse a volume specification into a sorted list of volume number strings.

    Accepts:
    - A list of volume numbers (ints or strings): ``[1, 2, 5]``
    - A range string: ``"1-13"``
    - An "all N" string: ``"all 8"`` (creates volumes 1..8)
    """
    if isinstance(volume_specs, list):
        return [str(v) for v in volume_specs]

    spec = str(volume_specs).strip()

    # "all N" pattern
    all_match = re.match(r"^all\s+(\d+)$", spec, re.IGNORECASE)
    if all_match:
        total = int(all_match.group(1))
        return [str(i) for i in range(1, total + 1)]

    # "N-M" range pattern
    range_match = re.match(r"^(\d+)\s*-\s*(\d+)$", spec)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        return [str(i) for i in range(start, end + 1)]

    # Single number or comma-separated
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    return parts


def create_series_volumes(
    series: Series,
    volume_specs: str | list,
    records: dict[str, Record] | None = None,
) -> list[SeriesVolume]:
    """Create SeriesVolume entries for *series*.

    *volume_specs* is parsed by ``_parse_volume_spec`` (accepts a list,
    range string like ``"1-13"``, or ``"all 8"``).

    *records* is an optional mapping of volume number string to Record.
    Volumes with a matching record are created with ``held=True``; volumes
    without are created with ``held=False`` (gap placeholders).

    Existing volumes for the same series/volume_number are skipped (not
    duplicated).

    Returns the list of newly created SeriesVolume objects.
    """
    records = records or {}
    volume_numbers = _parse_volume_spec(volume_specs)

    created: list[SeriesVolume] = []
    for vol_num in volume_numbers:
        record = records.get(vol_num)
        held = record is not None

        sv, was_created = SeriesVolume.objects.get_or_create(
            series=series,
            volume_number=vol_num,
            defaults={"record": record, "held": held},
        )
        if was_created:
            created.append(sv)

    return created
