"""Build the frozen candidate frame for the set-survey labels.

The frame is every record the set survey's queries returned, one line
per record, so labels can be drawn from what the catalogs returned
rather than from what the title filter accepted. Nothing is fetched:
each query's cache key is recomputed with `sru_fetch.cache_name`, the
function `sru_fetch.fetch` itself uses, and the cached response is
read. A response missing from the cache stops the build.

Each record is kept as the exact text of its MARC `record` element in
the response, with its SHA-256. Records are deduplicated within a
catalog on `001`; the first occurrence, in `set_cases.WORKS` order, is
the one kept, and every work whose query returned the record is listed.
A record's id is `catalog|003:001`, with 003 empty when the record has
none, as at NLI and in most LC records.

The pipeline outcome is computed with the functions `set_report.py`
uses and is stored for stratification and scoring only. The labeling
tool does not read it.

After writing, the build reads `frame.jsonl` back and checks that every
record parses to the stored 001 and hash, that the stored outcome is
what the record yields, and that the records reproduce `set_cases.json`
and `set_summary.json` query by query. Any mismatch exits non-zero.

Run from the repository root:

    uv run python studies/cataloging-practice/frame.py [--cache DIR]
"""

import argparse
import collections
import datetime
import hashlib
import json
import pathlib
import sys
import xml.etree.ElementTree as ET
from xml.parsers import expat

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import set_report
from set_cases import MAX_RECORDS, WORKS, describe_record
from sru_fetch import CACHE, M, cache_name

HERE = pathlib.Path("tmp/vagf")
CATALOGS = set_report.CATALOGS
STRATA = ("S1", "S2", "S3", "S4", "S5")
LEVEL_CLASSES = ("set_extent", "l19_773_np", "neither")
SET_EXTENTS = ("counted", "open")
L19_CODED = ("a", "b", "c")

# expat reports a namespaced name as "<uri>}<local>" with this separator.
_MARC_RECORD = M[1:] + "record"


def split_records(data):
    """Each MARC record element in a response, as the text retrieved.

    `data` is the response as bytes. The slices are taken at expat's
    byte offsets, so each string is the element exactly as the server
    sent it, from its start tag to the end of its end tag.
    """
    parser = expat.ParserCreate(namespace_separator="}")
    opened, spans = [], []

    def start(name, attrs):
        if name == _MARC_RECORD:
            opened.append(parser.CurrentByteIndex)

    def end(name):
        if name == _MARC_RECORD:
            begin = opened.pop()
            if not opened:
                close = data.index(b">", parser.CurrentByteIndex) + 1
                spans.append((begin, close))

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(data, True)
    return [data[a:b].decode("utf-8") for a, b in spans]


def control(rec, tag):
    """The first control field with this tag, or "" when absent."""
    for cf in rec.findall(f"{M}controlfield"):
        if cf.get("tag") == tag:
            return cf.text or ""
    return ""


def record_id(catalog, f003, f001):
    return f"{catalog}|{f003}:{f001}"


def outcome(desc, works):
    """The pipeline's outcome for one described record.

    `desc` is `set_cases.describe_record` output and `works` the works
    whose query returned the record. The title filter is applied for
    each of those works, as `set_report.py` applies it per query.
    `leader19` is the leader/19 character, or "-" when it is blank.
    """
    accepted = [w for w in works if set_report.names_work(w, desc)]
    return {
        "title_accepted": bool(accepted),
        "title_accepted_for": accepted,
        "leader07": desc["l07"],
        "vendor": desc["online"],
        "extent": set_report.extent(desc["a300"]),
        "leader19": desc["l19"],
        "t773": desc["t773"],
        "np": desc["np"],
        "t505": desc["t505"],
    }


def set_signal(p):
    """Whether a pipeline outcome carries any set signal."""
    return (
        p["extent"] in SET_EXTENTS
        or p["leader19"] in L19_CODED
        or p["t773"]
        or p["np"]
    )


def stratum(p):
    """The sampling stratum for a pipeline outcome.

    The strata follow the pipeline's filters in order, so each record
    falls in exactly one: rejected by the title filter (S4 with a set
    signal, S5 without), accepted but not leader/07 `m` (S3), a
    monograph flagged as publisher-supplied (S2), or a library
    monograph the survey counted (S1).
    """
    if not p["title_accepted"]:
        return "S4" if set_signal(p) else "S5"
    if p["leader07"] != "m":
        return "S3"
    if p["vendor"]:
        return "S2"
    return "S1"


def level_class(p):
    """The predicted level class that balances S1 within a catalog."""
    if p["extent"] in SET_EXTENTS:
        return "set_extent"
    if p["leader19"] in L19_CODED or p["t773"] or p["np"]:
        return "l19_773_np"
    return "neither"


def s1_work(p, works):
    """The work an S1 record is allocated under: the first it names."""
    accepted = set(p["title_accepted_for"])
    return next(w for w in works if w in accepted)


def retrieved(path):
    """The cache file's modification date, in UTC."""
    ts = path.stat().st_mtime
    return datetime.datetime.fromtimestamp(ts, datetime.UTC).date().isoformat()


def read_responses(cache_dir):
    """Every survey response, in `set_cases.WORKS` order.

    Each is (work, catalog, file name, retrieved date, [record text]).
    """
    out = []
    for work, queries in WORKS.items():
        for catalog in CATALOGS:
            name = cache_name(catalog, queries[catalog], MAX_RECORDS)
            path = cache_dir / name
            if not path.exists():
                sys.exit(f"no cached response for {work} / {catalog}: {path}")
            texts = split_records(path.read_bytes())
            out.append((work, catalog, name, retrieved(path), texts))
    return out


def build(responses):
    """Deduplicate the responses into frame rows.

    Returns (rows, occurrences, counts). `occurrences` maps each
    (work, catalog) to the record ids of its response in order, with
    repeats, which is what the round-trip check replays.
    """
    kept = {}
    occurrences = {}
    counts = collections.Counter()
    for work, catalog, source, date, texts in responses:
        occurrences[(work, catalog)] = ids = []
        seen_here = set()
        for text in texts:
            rec = ET.fromstring(text)
            f001 = control(rec, "001")
            if not f001:
                raise ValueError(f"record without 001 in {source}")
            key = (catalog, f001)
            counts[f"returned:{catalog}"] += 1
            if key in seen_here:
                counts["duplicate_within_response"] += 1
            elif key in kept:
                counts["duplicate_across_works"] += 1
            seen_here.add(key)
            if key not in kept:
                kept[key] = {
                    "record_id": record_id(catalog, control(rec, "003"), f001),
                    "catalog": catalog,
                    "003": control(rec, "003"),
                    "001": f001,
                    "works_returned_for": [],
                    "retrieved": date,
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "marcxml": text,
                    "_desc": describe_record(rec),
                }
            elif kept[key]["marcxml"] != text:
                counts["duplicate_differing_text"] += 1
            row = kept[key]
            if work not in row["works_returned_for"]:
                row["works_returned_for"].append(work)
            ids.append(row["record_id"])
    rows = []
    for catalog in CATALOGS:
        for key, row in kept.items():
            if key[0] != catalog:
                continue
            desc = row.pop("_desc")
            row["pipeline"] = outcome(desc, row["works_returned_for"])
            rows.append(row)
    return rows, occurrences, counts


def frame_counts(rows, occurrences, counts):
    """Population sizes: returned, deduplicated, and per stratum."""
    by_cat = collections.Counter(r["catalog"] for r in rows)
    strata = {s: collections.Counter() for s in STRATA}
    s1_level = {c: collections.Counter() for c in CATALOGS}
    s1_cells = {c: collections.Counter() for c in CATALOGS}
    accepted = collections.Counter()
    for r in rows:
        p, c = r["pipeline"], r["catalog"]
        accepted[c] += p["title_accepted"]
        s = stratum(p)
        strata[s][c] += 1
        if s == "S1":
            s1_level[c][level_class(p)] += 1
            s1_cells[c][s1_work(p, r["works_returned_for"])] += 1

    def per_catalog(counter):
        out = {c: counter[c] for c in CATALOGS}
        out["total"] = sum(out.values())
        return out

    return {
        "queries": len(occurrences),
        "retrieved": sorted({r["retrieved"] for r in rows}),
        "returned": per_catalog(
            collections.Counter({c: counts[f"returned:{c}"] for c in CATALOGS})
        ),
        "deduplicated": per_catalog(by_cat),
        "duplicates": {
            "across_works": counts["duplicate_across_works"],
            "within_one_response": counts["duplicate_within_response"],
            "differing_text": counts["duplicate_differing_text"],
        },
        "title_accepted": per_catalog(accepted),
        "strata": {s: per_catalog(strata[s]) for s in STRATA},
        "s1_level_class": {
            c: {k: s1_level[c][k] for k in LEVEL_CLASSES} for c in CATALOGS
        },
        "s1_work": {
            c: {w: s1_cells[c][w] for w in WORKS if s1_cells[c][w]}
            for c in CATALOGS
        },
    }


def read_frame(path):
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def check(rows, occurrences, cases, summary):
    """Round-trip checks on frame rows read back from disk.

    Returns a list of problems; empty means the frame holds every
    record the survey counted, each parses to its stored 001 and hash,
    its stored outcome is what it yields, and the records reproduce
    `set_cases.json` and `set_summary.json` for every query.
    """
    problems = []
    by_id, desc = {}, {}
    for r in rows:
        rid = r["record_id"]
        if rid in by_id:
            problems.append(f"{rid}: duplicate record_id")
        by_id[rid] = r
        try:
            rec = ET.fromstring(r["marcxml"])
        except ET.ParseError as exc:
            problems.append(f"{rid}: does not parse: {exc}")
            continue
        if control(rec, "001") != r["001"]:
            problems.append(f"{rid}: 001 differs from the record")
        if hashlib.sha256(r["marcxml"].encode()).hexdigest() != r["sha256"]:
            problems.append(f"{rid}: sha256 differs from the record")
        desc[rid] = describe_record(rec)
        if outcome(desc[rid], r["works_returned_for"]) != r["pipeline"]:
            problems.append(f"{rid}: stored pipeline outcome differs")
    for work in summary:
        for catalog in summary[work]:
            ids = occurrences.get((work, catalog))
            if ids is None:
                problems.append(f"{work} / {catalog}: no response")
                continue
            missing = [i for i in ids if i not in desc]
            if missing:
                problems.append(f"{work} / {catalog}: {missing} not in frame")
                continue
            if any(work not in by_id[i]["works_returned_for"] for i in ids):
                problems.append(f"{work} / {catalog}: work not listed")
            recs = [desc[i] for i in ids]
            published = cases.get(work, {}).get(catalog, {}).get("records")
            if recs != published:
                problems.append(f"{work} / {catalog}: differs from set_cases")
            if set_report.cell(work, recs) != summary[work][catalog]:
                problems.append(f"{work} / {catalog}: differs from summary")
    return problems


def write_jsonl(path, rows):
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    path.write_text(text, encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--cache",
        type=pathlib.Path,
        default=CACHE,
        help="directory holding the cached survey responses "
        "(default: the one sru_fetch.py writes)",
    )
    args = ap.parse_args(argv)

    rows, occurrences, counts = build(read_responses(args.cache))
    write_jsonl(HERE / "frame.jsonl", rows)
    fc = frame_counts(rows, occurrences, counts)
    (HERE / "frame_counts.json").write_text(
        json.dumps(fc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    cases = json.loads((HERE / "set_cases.json").read_text(encoding="utf-8"))
    summary = json.loads((HERE / "set_summary.json").read_text())
    problems = check(
        read_frame(HERE / "frame.jsonl"), occurrences, cases, summary
    )
    for p in problems:
        print(p)
    print(
        f"{fc['queries']} queries, {fc['returned']['total']} records "
        f"returned, {fc['deduplicated']['total']} after deduplication"
    )
    for s in STRATA:
        print(f"  {s}: {fc['strata'][s]}")
    print(f"wrote {HERE / 'frame.jsonl'} and {HERE / 'frame_counts.json'}")
    if problems:
        sys.exit(f"round trip failed: {len(problems)} problems")
    print("round trip: every record parses and reproduces the survey")


if __name__ == "__main__":
    main()
