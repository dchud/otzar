"""Draw the labeling sample from the frozen frame.

Reads `tmp/vagf/frame.jsonl`, puts each record in one stratum from its
pipeline outcome (`frame.stratum`), draws with a fixed seed, and writes

* `tmp/vagf/sample.jsonl`: one line per sampled record, in the order
  the labeler is served them. Each line holds `record_id`, `catalog`,
  `003`, `001`, `marcxml`, `pilot`, `holdback` and `stratum`. The
  stratum is for scoring; the labeling tool does not display it. No
  pipeline outcome is copied: the scorer joins to the frame on
  `record_id`.
* `tmp/vagf/sample_weights.json`: population and sample sizes, and
  their ratio as the weight, for every stratum in every catalog and for
  every S1 cell, plus the seed and the excluded guide examples.

Strata and targets, per catalog:

* S1, library monographs the title filter accepted: 80. Split across
  the three predicted level classes as evenly as their records allow;
  every work with S1 records gets two (or all it has); the rest of each
  class's share goes to works in proportion to their records in that
  class.
* S2, monographs flagged as publisher-supplied: every record.
* S3, title-accepted records whose leader/07 is not `m`: every record.
* S4, title-rejected records with a set signal: 40, or every record.
* S5, title-rejected records without one: 20, or every record.

Every random choice is a SHA-256 of the seed, a purpose and the
record_id, so the draw does not depend on the order of the frame, and
excluding a record changes the draw only in its own catalog and
stratum.

The order spreads each catalog-stratum cell evenly through the sample,
so catalogs and strata interleave and the pilot, the first 150, is a
proportional cross-section; it is then adjusted so no two consecutive
records were returned for the same work. The holdback, a tenth of the
sample and at least 80, is drawn from each stratum in proportion to
its size, from records after the pilot, so its first labels are made
under the vocabulary the pilot settles.

Guide examples: every record_id cited in `label/GUIDE.md` is excluded.
A cited id that is not in the frame stops the draw. `--no-guide` draws
without exclusions, for a preview before the guide exists.

Run from the repository root:

    uv run python studies/cataloging-practice/label/sample.py
"""

import argparse
import collections
import fractions
import hashlib
import itertools
import json
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import frame

SEED = 20260907
HERE = frame.HERE
GUIDE = pathlib.Path(__file__).resolve().parent / "GUIDE.md"

PER_CATALOG = {"S1": 80, "S4": 40, "S5": 20}
EVERY = ("S2", "S3")
FLOOR = 2
PILOT = 150
HOLDBACK_PERCENT = 10
HOLDBACK_MIN = 80

ID_SHAPE = re.compile(
    r"(?<![\w|])(?:" + "|".join(frame.CATALOGS) + r")\|[\w.-]*:[\w.-]+"
)


def key(seed, purpose, record_id):
    """A record's random key for one purpose, fixed by the seed."""
    text = f"{seed}|{purpose}|{record_id}".encode()
    return int.from_bytes(hashlib.sha256(text).digest()[:8], "big")


def smallest(rows, n, seed, purpose="draw"):
    """The n rows with the smallest keys: a simple random sample."""
    return sorted(
        rows,
        key=lambda r: (key(seed, purpose, r["record_id"]), r["record_id"]),
    )[:n]


def balanced(n, caps):
    """Split n as evenly as caps allow; spare units go to earlier keys.

    A key whose cap is below the even share gets its cap, and the rest
    is shared again among the others.
    """
    alloc = dict.fromkeys(caps, 0)
    left = min(n, sum(caps.values()))
    open_keys = [k for k in caps if caps[k] > 0]
    while open_keys:
        share = left // len(open_keys)
        full = [k for k in open_keys if caps[k] <= share]
        if not full:
            break
        for k in full:
            alloc[k] = caps[k]
            left -= caps[k]
            open_keys.remove(k)
    if open_keys:
        share, extra = divmod(left, len(open_keys))
        for i, k in enumerate(open_keys):
            alloc[k] = share + (i < extra)
    return alloc


def proportional(n, sizes):
    """Split n in proportion to sizes, by largest remainder.

    Never gives a key more than its size. Ties go to earlier keys.
    """
    total = sum(sizes.values())
    if n >= total:
        return dict(sizes)
    alloc = {k: n * s // total for k, s in sizes.items()}
    by_remainder = sorted(sizes, key=lambda k: -(n * sizes[k] % total))
    for k in by_remainder[: n - sum(alloc.values())]:
        alloc[k] += 1
    return alloc


def allocate_s1(cells, n, floor=FLOOR):
    """Allocate n across one catalog's S1 cells.

    `cells` maps (work, level class) to its record count, in work
    order. Level classes get as even a share as their records allow.
    Each work first gets `floor` records, or all it has, taken from its
    classes with the most share left; each class's remainder then goes
    to works in proportion to the records they have left in it.
    """
    classes = frame.LEVEL_CLASSES
    works = list(dict.fromkeys(w for w, _ in cells))
    n = min(n, sum(cells.values()))
    avail = {
        k: sum(c for (_, k2), c in cells.items() if k2 == k) for k in classes
    }
    quota = balanced(n, avail)
    alloc = dict.fromkeys(cells, 0)
    used = dict.fromkeys(classes, 0)
    for w in works:
        mine = [k for k in classes if (w, k) in cells]
        for _ in range(min(floor, sum(cells[w, k] for k in mine))):
            k = max(
                (k for k in mine if alloc[w, k] < cells[w, k]),
                key=lambda k: quota[k] - used[k],
            )
            alloc[w, k] += 1
            used[k] += 1
    if sum(used.values()) > n:
        raise ValueError(f"the floors need {sum(used.values())} of {n}")
    rest = balanced(
        n - sum(used.values()),
        {k: max(0, quota[k] - used[k]) for k in classes},
    )
    for k in classes:
        room = {w: cells[w, k] - alloc[w, k] for w in works if (w, k) in cells}
        for w, extra in proportional(rest[k], room).items():
            alloc[w, k] += extra
    return alloc


def cell_of(row):
    """The design cell a frame row is drawn in."""
    p = row["pipeline"]
    s = frame.stratum(p)
    if s == "S1":
        work = frame.s1_work(p, row["works_returned_for"])
        return (s, row["catalog"], work, frame.level_class(p))
    return (s, row["catalog"])


def draw(rows, seed, exclude=frozenset()):
    """Draw the sample. Returns (drawn rows by cell, allocation, population).

    Population counts every frame row, examples included; allocation
    and the draw use only the rows not excluded.
    """
    population = collections.Counter(cell_of(r) for r in rows)
    eligible = collections.defaultdict(list)
    for r in rows:
        if r["record_id"] not in exclude:
            eligible[cell_of(r)].append(r)
    alloc = {}
    for c in frame.CATALOGS:
        s1 = {
            (w, k): len(eligible[("S1", c, w, k)])
            for w in frame.WORKS
            for k in frame.LEVEL_CLASSES
            if eligible[("S1", c, w, k)]
        }
        for (w, k), n in allocate_s1(s1, PER_CATALOG["S1"]).items():
            alloc[("S1", c, w, k)] = n
        for s in EVERY:
            alloc[(s, c)] = len(eligible[(s, c)])
        for s in ("S4", "S5"):
            alloc[(s, c)] = min(PER_CATALOG[s], len(eligible[(s, c)]))
    drawn = {
        cell: smallest(eligible[cell], n, seed) for cell, n in alloc.items()
    }
    return drawn, alloc, population


def interleave(items, seed):
    """Order items so each catalog-stratum cell is spread evenly.

    The m members of a cell, in key order, sit at positions
    (i + u) / m for a random u in [0, 1), and the order is those
    positions sorted, so every stretch of the order holds each cell in
    about its share of the sample.
    """
    cells = collections.defaultdict(list)
    for it in items:
        cells[(it["catalog"], it["stratum"])].append(it)
    placed = []
    for members in cells.values():
        members.sort(
            key=lambda it: (
                key(seed, "order", it["record_id"]),
                it["record_id"],
            )
        )
        m = len(members)
        for i, it in enumerate(members):
            u = fractions.Fraction(key(seed, "jitter", it["record_id"]), 2**64)
            placed.append(((i + u) / m, it["record_id"], it))
    placed.sort(key=lambda t: t[:2])
    return [it for _, _, it in placed]


def shares_work(a, b):
    return bool(set(a["works"]) & set(b["works"]))


def separate_works(items):
    """Reorder so no two consecutive items were returned for one work.

    Each step takes the earliest waiting item that does not share a
    work with the last one placed. When none can follow, the earliest
    waiting item goes into the latest gap whose neighbours it shares
    no work with.
    """
    out, waiting = [], list(items)
    while waiting:
        for i, it in enumerate(waiting):
            if not out or not shares_work(out[-1], it):
                out.append(waiting.pop(i))
                break
        else:
            it = waiting.pop(0)
            for j in range(len(out) - 1, -1, -1):
                before = out[j - 1] if j else None
                if not shares_work(out[j], it) and not (
                    before and shares_work(before, it)
                ):
                    out.insert(j, it)
                    break
            else:
                raise ValueError(f"no place for {it['record_id']}")
    return out


def holdback_size(n):
    return max(HOLDBACK_MIN, math.ceil(n * HOLDBACK_PERCENT / 100))


def choose_holdback(order, seed, pilot=PILOT):
    """The holdback record ids: across strata, from after the pilot."""
    after = order[pilot:]
    by_stratum = collections.defaultdict(list)
    for it in after:
        by_stratum[it["stratum"]].append(it)
    sizes = {s: len(by_stratum[s]) for s in frame.STRATA if by_stratum[s]}
    share = proportional(holdback_size(len(order)), sizes)
    chosen = set()
    for s, n in share.items():
        picks = smallest(by_stratum[s], n, seed, "holdback")
        chosen.update(it["record_id"] for it in picks)
    return chosen


def make_sample(rows, seed, exclude=frozenset()):
    """The ordered sample lines and the weights document."""
    drawn, alloc, population = draw(rows, seed, exclude)
    items = [
        {
            "record_id": r["record_id"],
            "catalog": r["catalog"],
            "003": r["003"],
            "001": r["001"],
            "marcxml": r["marcxml"],
            "stratum": cell[0],
            "works": r["works_returned_for"],
        }
        for cell, members in drawn.items()
        for r in members
    ]
    order = separate_works(interleave(items, seed))
    held = choose_holdback(order, seed)
    lines = [
        {
            "record_id": it["record_id"],
            "catalog": it["catalog"],
            "003": it["003"],
            "001": it["001"],
            "marcxml": it["marcxml"],
            "pilot": i < PILOT,
            "holdback": it["record_id"] in held,
            "stratum": it["stratum"],
        }
        for i, it in enumerate(order)
    ]
    return lines, weights(alloc, population, seed, exclude, lines)


def _weight(pop, n):
    return {"population": pop, "sample": n, "weight": pop / n if n else None}


def weights(alloc, population, seed, exclude, lines):
    strata = {s: {} for s in frame.STRATA}
    for s in frame.STRATA:
        for c in frame.CATALOGS:
            pop = sum(v for k, v in population.items() if k[:2] == (s, c))
            n = sum(v for k, v in alloc.items() if k[:2] == (s, c))
            strata[s][c] = _weight(pop, n)
    s1_cells = [
        {"catalog": k[1], "work": k[2], "level_class": k[3]}
        | _weight(population[k], alloc.get(k, 0))
        for k in sorted(
            (k for k in population if k[0] == "S1"),
            key=lambda k: (
                frame.CATALOGS.index(k[1]),
                list(frame.WORKS).index(k[2]),
                frame.LEVEL_CLASSES.index(k[3]),
            ),
        )
    ]
    return {
        "seed": seed,
        "excluded": sorted(exclude),
        "size": len(lines),
        "pilot": sum(line["pilot"] for line in lines),
        "holdback": sum(line["holdback"] for line in lines),
        "strata": strata,
        "s1_cells": s1_cells,
    }


def guide_examples(text, known):
    """The record ids a guide cites, each checked against the frame."""
    found = set()
    for m in ID_SHAPE.finditer(text):
        rid = m.group(0).rstrip(".")
        if rid not in known:
            raise ValueError(
                f"the guide cites {rid}, which is not in the frame"
            )
        found.add(rid)
    return found


def check(rows, exclude, lines):
    """Problems with a drawn sample, checked against the frame rows.

    Empty when every line is a frame record in its stratum, no record
    or guide example is drawn twice or at all, each stratum meets its
    target or takes every eligible record, no two consecutive records
    share a work, and the pilot and holdback are the sizes the plan
    sets, with no holdback record in the pilot.
    """
    problems = []
    by_id = {r["record_id"]: r for r in rows}
    ids = [line["record_id"] for line in lines]
    if len(set(ids)) != len(ids):
        problems.append("a record appears twice")
    if set(ids) & set(exclude):
        problems.append("a guide example was drawn")
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        return problems + [f"not in the frame: {unknown}"]
    eligible = collections.Counter(
        (frame.stratum(r["pipeline"]), r["catalog"])
        for r in rows
        if r["record_id"] not in exclude
    )
    drawn = collections.Counter()
    for line in lines:
        row = by_id[line["record_id"]]
        if line["stratum"] != frame.stratum(row["pipeline"]):
            problems.append(f"{line['record_id']}: wrong stratum")
        drawn[(line["stratum"], line["catalog"])] += 1
    for s in frame.STRATA:
        for c in frame.CATALOGS:
            want = eligible[(s, c)]
            if s in PER_CATALOG:
                want = min(PER_CATALOG[s], want)
            if drawn[(s, c)] != want:
                problems.append(f"{s} {c}: drew {drawn[(s, c)]} of {want}")
    for a, b in itertools.pairwise(ids):
        works_a = set(by_id[a]["works_returned_for"])
        if works_a & set(by_id[b]["works_returned_for"]):
            problems.append(f"{a} and {b} are consecutive and share a work")
    pilot = [line for line in lines if line["pilot"]]
    if pilot != lines[: min(PILOT, len(lines))]:
        problems.append("the pilot is not the first records of the order")
    held = [line for line in lines if line["holdback"]]
    if len(held) != holdback_size(len(lines)):
        problems.append(f"holdback holds {len(held)} records")
    if any(line["pilot"] for line in held):
        problems.append("a holdback record is in the pilot")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--guide", type=pathlib.Path, default=GUIDE)
    ap.add_argument(
        "--no-guide",
        action="store_true",
        help="draw without excluding guide examples",
    )
    args = ap.parse_args(argv)

    rows = frame.read_frame(HERE / "frame.jsonl")
    exclude = frozenset()
    if not args.no_guide:
        if not args.guide.exists():
            sys.exit(f"{args.guide} not found; --no-guide draws without it")
        text = args.guide.read_text(encoding="utf-8")
        exclude = frozenset(
            guide_examples(text, {r["record_id"] for r in rows})
        )
    lines, wts = make_sample(rows, SEED, exclude)
    problems = check(rows, exclude, lines)
    for p in problems:
        print(p)
    if problems:
        sys.exit(f"not written: {len(problems)} problems with the sample")
    frame.write_jsonl(HERE / "sample.jsonl", lines)
    (HERE / "sample_weights.json").write_text(
        json.dumps(wts, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(
        f"{len(lines)} records, pilot {wts['pilot']}, "
        f"holdback {wts['holdback']}, {len(exclude)} guide examples "
        f"excluded"
    )
    print(f"{'':4}" + "".join(f"{c:>18}" for c in frame.CATALOGS))
    for s in frame.STRATA:
        cells = "".join(
            f"{w['sample']:>9} of {w['population']:>5}"
            for w in wts["strata"][s].values()
        )
        print(f"{s:4}{cells}")
    print(f"wrote {HERE / 'sample.jsonl'} and {HERE / 'sample_weights.json'}")


if __name__ == "__main__":
    main()
