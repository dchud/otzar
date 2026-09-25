"""Serve the labeling tool: the sample's records, one at a time, raw.

Run from the repository root, then open the address it prints:

    uv run python studies/cataloging-practice/label/serve.py
    uv run python studies/cataloging-practice/label/serve.py --pass holdback

It uses only the standard library and listens on 127.0.0.1. It reads
`tmp/vagf/sample.jsonl` and `label/GUIDE.md`, and appends to
`tmp/vagf/labels.jsonl`; `--sample` and `--labels` point it elsewhere.

What the page shows. For each record, the catalog's name and the
record as `marc_html` renders it: the leader, control fields and data
fields as retrieved, except leader/19, which is replaced by a mask
character before rendering because it is the coded form of the level
judgment being labeled. The browser is sent the record's id, its
catalog, the rendered record, the count of records labeled and, when a
record is revisited for correction, the label saved for it in the
current pass. The sample's stratum, pilot and holdback flags are
dropped when the sample is read and never reach the page, and the
frame's pipeline outcome is never read.

Vocabulary. The fields, values and keys are read from the key tables
in the guide's "Fields" section, and the guide's "Version:" line is
recorded in every label. The start is refused if the tables do not
parse or break a rule the tool applies: one character per key, keys
unique within a field and not `u` or `n`, and the fields and values
named below present. The rules: `own-title` is asked only when `level`
is `volume`; `none` under `work` records `unrelated` under `relation`
with the work's confidence; `cannot-judge` belongs to `relation` and
`level` only; a note is required when any field is `cannot-judge` or
`other`.

Passes. The main pass serves the sample in its order. `--pass holdback`
serves the held-back records in a new order fixed by a seed, each only
once its latest main-pass label is at least seven days old.

Labels. Each save appends one JSON line: `record_id`, `catalog`, `003`,
`001`, `pass`, one key per field holding its value (`own-title` is null
unless `level` is `volume`), `confidence` mapping each field to `sure`
or `unsure`, `note`, `seconds` from render to save, `idle` when a gap
of over five minutes between keystrokes or clicks was seen,
`guide_version` and a UTC `timestamp`. The file is only appended to. A
correction appends a new line, and the last line for a record in a
pass is its label; saving a record again unchanged appends nothing. On
start, records with a label in the current pass are skipped, so a
session can stop at any record and the next one starts there. A labels
file with a line that does not parse stops the start.
"""

import argparse
import datetime
import hashlib
import http.server
import json
import os
import pathlib
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import marc_html

HERE = pathlib.Path("tmp/vagf")
LABEL_DIR = pathlib.Path(__file__).resolve().parent
GUIDE = LABEL_DIR / "GUIDE.md"
PAGE = LABEL_DIR / "index.html"
PORT = 8765

M = "{http://www.loc.gov/MARC21/slim}"
MASK = "█"
SEED = 20260907
PASSES = ("main", "holdback")
RELABEL_AFTER = datetime.timedelta(days=7)
CATALOG_NAMES = {
    "lc": "LC",
    "oxford": "Oxford",
    "nli": "NLI",
    "dnb": "DNB",
    "k10plus": "K10plus",
}

# Fields and values the tool's rules name, as the guide spells them.
WORK, RELATION, LEVEL, OWN_TITLE = "work", "relation", "level", "own-title"
NONE, UNRELATED, VOLUME = "none", "unrelated", "volume"
CANNOT_JUDGE, OTHER = "cannot-judge", "other"
NOTE_REQUIRED = (CANNOT_JUDGE, OTHER)
CANNOT_JUDGE_FIELDS = (RELATION, LEVEL)
CONFIDENCE = ("sure", "unsure")
UNSURE_KEY, NOTE_KEY = "u", "n"
LABEL_KEYS = (
    "record_id",
    "catalog",
    "003",
    "001",
    "pass",
    "confidence",
    "note",
    "seconds",
    "idle",
    "guide_version",
    "timestamp",
)
SAMPLE_KEYS = ("record_id", "catalog", "003", "001", "marcxml", "holdback")


class GuideError(Exception):
    """A guide whose vocabulary the tool cannot use."""


class InputError(Exception):
    """A sample or labels file the tool cannot use."""


class LabelError(Exception):
    """A label the tool will not save; the message says why."""


# The record as displayed.


def structure(marcxml):
    """The plain record structure `marc_html.render` takes."""
    rec = ET.fromstring(marcxml)
    return {
        "leader": rec.findtext(f"{M}leader") or "",
        "controlfields": [
            (f.get("tag"), f.text or "")
            for f in rec.findall(f"{M}controlfield")
        ],
        "datafields": [
            (
                f.get("tag"),
                f.get("ind1") or " ",
                f.get("ind2") or " ",
                [
                    (s.get("code"), s.text or "")
                    for s in f.findall(f"{M}subfield")
                ],
            )
            for f in rec.findall(f"{M}datafield")
        ],
    }


def mask(record):
    """The record with leader/19 replaced by the mask character."""
    leader = record["leader"]
    if len(leader) > 19:
        leader = leader[:19] + MASK + leader[20:]
    return {**record, "leader": leader}


def record_html(marcxml):
    return marc_html.render(mask(structure(marcxml)))


# The vocabulary, from the guide.

_VERSION = re.compile(r"^Version:\s*(\S+)\s*$", re.MULTILINE)
_FIELD = re.compile(r"^### `([^`]+)`\s*$")
_CODE = re.compile(r"^`([^`]+)`$")


def _cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def parse_guide(text):
    """(version, fields) from the guide's text.

    `fields` is a list of (name, [(key, value), ...]) in the guide's
    order, read from the first table under each "### `name`" heading
    in the "## Fields" section: its Key and Value columns, each cell a
    code span.
    """
    version = _VERSION.search(text)
    if not version:
        raise GuideError("the guide has no 'Version:' line")
    fields, in_fields, current, header, done = [], False, None, None, False
    for n, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            in_fields, current = line.strip() == "## Fields", None
            continue
        heading = _FIELD.match(line) if in_fields else None
        if heading:
            current = (heading.group(1), [])
            fields.append(current)
            header, done = None, False
            continue
        if current is None or done:
            continue
        if not line.startswith("|"):
            done = header is not None
            continue
        cells = _cells(line)
        if header is None:
            if "Key" not in cells or "Value" not in cells:
                raise GuideError(f"line {n}: a table without Key and Value")
            header = (cells.index("Key"), cells.index("Value"))
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        codes = [_CODE.match(cells[i]) for i in header]
        if not all(codes):
            raise GuideError(f"line {n}: key and value must be code spans")
        current[1].append((codes[0].group(1), codes[1].group(1)))
    if not fields:
        raise GuideError("the guide's Fields section has no field tables")
    return version.group(1), fields


def check_vocabulary(fields):
    """Problems with a parsed vocabulary; empty when the tool can use it."""
    problems = []
    names = [name for name, _ in fields]
    values = {name: [v for _, v in opts] for name, opts in fields}
    if len(set(names)) != len(names):
        problems.append("a field appears twice")
    for name in names:
        if name in LABEL_KEYS:
            problems.append(f"{name}: a field cannot be named {name}")
    for name, opts in fields:
        if not opts:
            problems.append(f"{name}: no values")
        keys = [k for k, _ in opts]
        for k in keys:
            if len(k) != 1 or k.isspace():
                problems.append(f"{name}: key {k!r} is not one character")
            if k.lower() in (UNSURE_KEY, NOTE_KEY):
                problems.append(f"{name}: key {k!r} is reserved")
            if k != k.lower():
                problems.append(f"{name}: key {k!r} is not lower case")
        if len(set(keys)) != len(keys):
            problems.append(f"{name}: two values share a key")
        if len(set(values[name])) != len(values[name]):
            problems.append(f"{name}: a value appears twice")
    needed = {
        WORK: [NONE],
        RELATION: [UNRELATED, CANNOT_JUDGE],
        LEVEL: [VOLUME, CANNOT_JUDGE],
        OWN_TITLE: [],
    }
    for name, vals in needed.items():
        if name not in values:
            problems.append(f"no field {name}")
            continue
        for v in vals:
            if v not in values[name]:
                problems.append(f"{name}: no value {v}")
    for name, vals in values.items():
        if name not in CANNOT_JUDGE_FIELDS and CANNOT_JUDGE in vals:
            problems.append(
                f"{name}: {CANNOT_JUDGE} is for relation and level"
            )
    order = {name: i for i, name in enumerate(names)}
    if all(n in order for n in needed):
        if order[RELATION] < order[WORK]:
            problems.append("relation must come after work")
        if order[OWN_TITLE] < order[LEVEL]:
            problems.append("own-title must come after level")
    return problems


def load_guide(path):
    """(version, fields) from the guide at `path`, checked."""
    version, fields = parse_guide(path.read_text(encoding="utf-8"))
    problems = check_vocabulary(fields)
    if problems:
        raise GuideError("the guide's vocabulary: " + "; ".join(problems))
    return version, fields


# The sample, the labels file and the order of each pass.


def read_sample(path):
    """The sample's lines, keeping only what the tool uses."""
    lines, seen = [], set()
    with path.open(encoding="utf-8") as fh:
        for n, text in enumerate(fh, start=1):
            row = json.loads(text)
            missing = [k for k in SAMPLE_KEYS if k not in row]
            if missing:
                raise InputError(f"{path}:{n}: no {', '.join(missing)}")
            if row["record_id"] in seen:
                raise InputError(f"{path}:{n}: {row['record_id']} twice")
            seen.add(row["record_id"])
            lines.append({k: row[k] for k in SAMPLE_KEYS})
    return lines


def read_labels(path):
    """Every line of the labels file, in order; [] when it is absent."""
    if not path.exists():
        return []
    labels = []
    with path.open(encoding="utf-8") as fh:
        for n, text in enumerate(fh, start=1):
            if not text.endswith("\n"):
                raise InputError(f"{path}:{n}: the last line is incomplete")
            try:
                labels.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise InputError(f"{path}:{n}: {exc}") from exc
    return labels


def latest(labels, pass_name):
    """The last label saved for each record in one pass."""
    out = {}
    for label in labels:
        if label.get("pass") == pass_name:
            out[label["record_id"]] = label
    return out


def relabel_key(record_id, seed=SEED):
    text = f"{seed}|relabel|{record_id}".encode()
    return int.from_bytes(hashlib.sha256(text).digest()[:8], "big")


def pass_order(lines, pass_name):
    """The records a pass serves, in its order.

    The main pass is the sample in its order. The holdback pass is the
    held-back records in an order fixed by the seed and unrelated to
    the sample's.
    """
    if pass_name == "main":
        return list(lines)
    held = [line for line in lines if line["holdback"]]
    return sorted(
        held, key=lambda x: (relabel_key(x["record_id"]), x["record_id"])
    )


def timestamp(label):
    return datetime.datetime.fromisoformat(label["timestamp"])


def ready_for_relabel(order, labels, now):
    """The holdback records whose main-pass label is old enough."""
    main = latest(labels, "main")
    return [
        line
        for line in order
        if line["record_id"] in main
        and now - timestamp(main[line["record_id"]]) >= RELABEL_AFTER
    ]


def utcnow():
    return datetime.datetime.now(datetime.UTC).replace(microsecond=0)


# A label, from what the page sends.


def build_label(payload, line, fields, version, pass_name, now):
    """The line to append for one save; LabelError when it is invalid."""
    if payload.get("record_id") != line["record_id"]:
        raise LabelError("the label is for another record")
    values = payload.get("values")
    confidence = payload.get("confidence")
    if not isinstance(values, dict) or not isinstance(confidence, dict):
        raise LabelError("values and confidence must be objects")
    names = [name for name, _ in fields]
    unknown = sorted(set(values) - set(names))
    if unknown:
        raise LabelError(f"not fields in the guide: {', '.join(unknown)}")
    allowed = {name: [v for _, v in opts] for name, opts in fields}
    chosen, sure = {}, {}
    for name in names:
        value, conf = values.get(name), confidence.get(name)
        if name == OWN_TITLE and values.get(LEVEL) != VOLUME:
            if value is not None:
                raise LabelError(f"{OWN_TITLE} is asked only for a volume")
            chosen[name], sure[name] = None, None
            continue
        if name == RELATION and values.get(WORK) == NONE:
            if value not in (None, UNRELATED):
                raise LabelError(f"{WORK} {NONE} records {UNRELATED}")
            value, conf = UNRELATED, confidence.get(WORK)
        if value not in allowed[name]:
            raise LabelError(f"{name}: choose a value")
        if conf not in CONFIDENCE:
            raise LabelError(f"{name}: confidence must be sure or unsure")
        chosen[name], sure[name] = value, conf
    note = payload.get("note", "")
    if not isinstance(note, str):
        raise LabelError("the note must be text")
    note = note.strip()
    needing = [n for n, v in chosen.items() if v in NOTE_REQUIRED]
    if needing and not note:
        raise LabelError(f"a note is required with {chosen[needing[0]]}")
    seconds, idle = payload.get("seconds"), payload.get("idle")
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise LabelError("seconds must be a number")
    if seconds < 0:
        raise LabelError("seconds must not be negative")
    if not isinstance(idle, bool):
        raise LabelError("idle must be true or false")
    return {
        "record_id": line["record_id"],
        "catalog": line["catalog"],
        "003": line["003"],
        "001": line["001"],
        "pass": pass_name,
        **chosen,
        "confidence": sure,
        "note": note,
        "seconds": round(float(seconds), 1),
        "idle": idle,
        "guide_version": version,
        "timestamp": now.isoformat(),
    }


def append_label(path, label):
    """Append one line and flush it to disk before returning."""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(label, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _same(a, b, names):
    keys = [*names, "confidence", "note"]
    return all(a.get(k) == b.get(k) for k in keys)


class Session:
    """One pass over the sample, resumed from the labels file."""

    def __init__(self, lines, labels_path, guide, pass_name, now=None):
        if pass_name not in PASSES:
            raise ValueError(f"no pass {pass_name}")
        self.pass_name = pass_name
        self.labels_path = labels_path
        self.version, self.fields = guide
        labels = read_labels(labels_path)
        order = pass_order(lines, pass_name)
        if pass_name == "holdback":
            ready = ready_for_relabel(order, labels, now or utcnow())
            self.waiting = len(order) - len(ready)
            order = ready
        else:
            self.waiting = 0
        self.queue = order
        self.index = {line["record_id"]: i for i, line in enumerate(order)}
        self.saved = latest(labels, pass_name)

    def next_index(self):
        """The first record in the pass's order without a label."""
        for i, line in enumerate(self.queue):
            if line["record_id"] not in self.saved:
                return i
        return None

    def progress(self):
        done = sum(1 for line in self.queue if line["record_id"] in self.saved)
        return {"done": done, "total": len(self.queue)}

    def describe(self):
        """What the page needs to start: vocabulary, rules, position."""
        return {
            "fields": [
                {
                    "name": name,
                    "options": [{"key": k, "value": v} for k, v in opts],
                }
                for name, opts in self.fields
            ],
            "rules": {
                "work": WORK,
                "relation": RELATION,
                "level": LEVEL,
                "own_title": OWN_TITLE,
                "none": NONE,
                "unrelated": UNRELATED,
                "volume": VOLUME,
                "note_required": list(NOTE_REQUIRED),
            },
            "keys": {"unsure": UNSURE_KEY, "note": NOTE_KEY},
            "index": self.next_index(),
            **self.progress(),
        }

    def record(self, index):
        """One record as the page shows it, with this pass's label."""
        line = self.queue[index]
        saved = self.saved.get(line["record_id"])
        label = None
        if saved is not None:
            names = [name for name, _ in self.fields]
            label = {
                "values": {n: saved.get(n) for n in names},
                "confidence": saved.get("confidence", {}),
                "note": saved.get("note", ""),
            }
        return {
            "index": index,
            "record_id": line["record_id"],
            "catalog": CATALOG_NAMES.get(line["catalog"], line["catalog"]),
            "html": record_html(line["marcxml"]),
            "label": label,
            **self.progress(),
        }

    def save(self, payload, now=None):
        """Validate and append one label; returns the next position."""
        rid = payload.get("record_id") if isinstance(payload, dict) else None
        if rid not in self.index:
            raise LabelError("that record is not in this pass")
        line = self.queue[self.index[rid]]
        label = build_label(
            payload,
            line,
            self.fields,
            self.version,
            self.pass_name,
            now or utcnow(),
        )
        names = [name for name, _ in self.fields]
        previous = self.saved.get(rid)
        if previous is None or not _same(previous, label, names):
            append_label(self.labels_path, label)
            self.saved[rid] = label
        return {"next": self.next_index(), **self.progress()}


# HTTP.

MAX_BODY = 1 << 20


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self):
        session = self.server.session
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/":
            page = PAGE.read_bytes()
            self._send(200, page, "text/html; charset=utf-8")
        elif url.path == "/marc.css":
            css = marc_html.CSS.encode("utf-8")
            self._send(200, css, "text/css; charset=utf-8")
        elif url.path == "/api/session":
            self._json(200, session.describe())
        elif url.path == "/api/record":
            query = urllib.parse.parse_qs(url.query)
            try:
                index = int(query["index"][0])
            except (KeyError, ValueError):
                self._json(400, {"error": "index must be a number"})
                return
            if not 0 <= index < len(session.queue):
                self._json(404, {"error": "no record at that index"})
                return
            self._json(200, session.record(index))
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/api/label":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            self._json(400, {"error": "no body, or too large"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            result = self.server.session.save(payload)
        except json.JSONDecodeError:
            self._json(400, {"error": "the body is not JSON"})
        except LabelError as exc:
            self._json(400, {"error": str(exc)})
        else:
            self._json(200, result)

    def log_message(self, format, *args):
        pass


def make_server(session, port=PORT):
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    server.session = session
    return server


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--pass",
        dest="pass_name",
        choices=PASSES,
        default="main",
        help="main, or holdback for the relabel pass (default: main)",
    )
    ap.add_argument(
        "--sample", type=pathlib.Path, default=HERE / "sample.jsonl"
    )
    ap.add_argument(
        "--labels", type=pathlib.Path, default=HERE / "labels.jsonl"
    )
    ap.add_argument("--guide", type=pathlib.Path, default=GUIDE)
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args(argv)

    try:
        guide = load_guide(args.guide)
        lines = read_sample(args.sample)
        session = Session(lines, args.labels, guide, args.pass_name)
    except (GuideError, InputError, OSError) as exc:
        sys.exit(str(exc))
    server = make_server(session, args.port)
    progress = session.progress()
    print(
        f"{args.pass_name} pass: {progress['done']} of {progress['total']} "
        f"labeled; guide version {session.version}; "
        f"writing {args.labels}"
    )
    if session.waiting:
        print(
            f"{session.waiting} held-back records were labeled in the main "
            f"pass less than {RELABEL_AFTER.days} days ago, or not at all, "
            f"and are left out"
        )
    print(f"http://127.0.0.1:{server.server_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
