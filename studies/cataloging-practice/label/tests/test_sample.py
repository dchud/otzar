"""Tests for the labeling sample: the seeded draw, its allocation, the
order, the holdback and pilot, and the exclusion of guide examples.

Run explicitly; they build a synthetic frame and read no scratch data:

    uv run pytest studies/cataloging-practice/label/tests
"""

import collections
import itertools
import json
import pathlib
import random
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import frame
import sample

WORKS = list(frame.WORKS)[:6]
CATALOGS = frame.CATALOGS


def pipeline(stratum, level="neither", work=WORKS[0]):
    p = {
        "title_accepted": stratum in ("S1", "S2", "S3"),
        "title_accepted_for": [work] if stratum in ("S1", "S2", "S3") else [],
        "leader07": "a" if stratum == "S3" else "m",
        "vendor": stratum == "S2",
        "extent": "online" if stratum == "S2" else "single",
        "leader19": "-",
        "t773": False,
        "np": False,
        "t505": False,
    }
    if stratum == "S4" or level == "set_extent":
        p["extent"] = "counted"
    if level == "l19_773_np":
        p["leader19"] = "c"
    return p


def make_frame(sizes=None, s1=None):
    """A frame with every stratum in every catalog.

    `sizes` overrides the S2-S5 counts per (stratum, catalog); `s1`
    maps (work, level) to a count for every catalog.
    """
    sizes = sizes or {}
    s1 = s1 or {
        (w, k): 3 + 4 * i + j
        for i, w in enumerate(WORKS)
        for j, k in enumerate(frame.LEVEL_CLASSES)
    }
    rows = []

    def add(catalog, stratum, level, work):
        n = len(rows)
        rows.append(
            {
                "record_id": f"{catalog}|X:{n}",
                "catalog": catalog,
                "003": "X",
                "001": str(n),
                "works_returned_for": [work],
                "retrieved": "2026-09-07",
                "sha256": "",
                "marcxml": f"<record>{n}</record>",
                "pipeline": pipeline(stratum, level, work),
            }
        )

    for c in CATALOGS:
        for (w, k), count in s1.items():
            for _ in range(count):
                add(c, "S1", k, w)
        defaults = {"S2": 3, "S3": 4, "S4": 60, "S5": 30}
        for s, default in defaults.items():
            for i in range(sizes.get((s, c), default)):
                add(c, s, "neither", WORKS[i % len(WORKS)])
    return rows


def dump(lines, weights):
    return json.dumps([lines, weights], ensure_ascii=False, sort_keys=True)


def test_same_seed_gives_identical_output():
    rows = make_frame()
    first = dump(*sample.make_sample(rows, sample.SEED))
    second = dump(*sample.make_sample(make_frame(), sample.SEED))
    assert first == second


def test_output_does_not_depend_on_frame_order():
    rows = make_frame()
    shuffled = rows[:]
    random.Random(1).shuffle(shuffled)
    assert dump(*sample.make_sample(rows, sample.SEED)) == dump(
        *sample.make_sample(shuffled, sample.SEED)
    )


def test_another_seed_draws_another_sample():
    rows = make_frame()
    a, _ = sample.make_sample(rows, sample.SEED)
    b, _ = sample.make_sample(rows, sample.SEED + 1)
    assert [x["record_id"] for x in a] != [x["record_id"] for x in b]


def test_sample_meets_the_plan():
    rows = make_frame()
    lines, weights = sample.make_sample(rows, sample.SEED)
    assert sample.check(rows, frozenset(), lines) == []
    counts = collections.Counter((x["stratum"], x["catalog"]) for x in lines)
    for c in CATALOGS:
        assert counts[("S1", c)] == 80
        assert counts[("S2", c)] == 3
        assert counts[("S3", c)] == 4
        assert counts[("S4", c)] == 40
        assert counts[("S5", c)] == 20
    assert weights["strata"]["S4"]["lc"] == {
        "population": 60,
        "sample": 40,
        "weight": 1.5,
    }


def test_a_stratum_smaller_than_its_target_is_taken_whole():
    rows = make_frame(sizes={("S4", "lc"): 12, ("S5", "dnb"): 0})
    lines, weights = sample.make_sample(rows, sample.SEED)
    assert sample.check(rows, frozenset(), lines) == []
    assert weights["strata"]["S4"]["lc"]["sample"] == 12
    assert weights["strata"]["S5"]["dnb"] == {
        "population": 0,
        "sample": 0,
        "weight": None,
    }


def test_check_reports_a_short_stratum():
    rows = make_frame()
    lines, _ = sample.make_sample(rows, sample.SEED)
    s4 = next(i for i, x in enumerate(lines) if x["stratum"] == "S4")
    del lines[s4]
    assert any("S4" in p for p in sample.check(rows, frozenset(), lines))


def test_balanced_fills_capped_keys_and_splits_the_rest_evenly():
    caps = {"set_extent": 270, "l19_773_np": 6, "neither": 168}
    assert sample.balanced(80, caps) == {
        "set_extent": 37,
        "l19_773_np": 6,
        "neither": 37,
    }
    assert sample.balanced(80, {"a": 0, "b": 93, "c": 63}) == {
        "a": 0,
        "b": 40,
        "c": 40,
    }
    assert sample.balanced(80, {"a": 81, "b": 30, "c": 218}) == {
        "a": 27,
        "b": 27,
        "c": 26,
    }
    assert sample.balanced(50, {"a": 10, "b": 10}) == {"a": 10, "b": 10}


def test_proportional_uses_largest_remainders_and_never_exceeds_a_size():
    assert sample.proportional(10, {"a": 50, "b": 30, "c": 20}) == {
        "a": 5,
        "b": 3,
        "c": 2,
    }
    assert sample.proportional(4, {"a": 5, "b": 3, "c": 1}) == {
        "a": 2,
        "b": 1,
        "c": 1,
    }
    assert sample.proportional(20, {"a": 5, "b": 3}) == {"a": 5, "b": 3}


def test_s1_allocation_meets_the_floor_and_balances_classes():
    cells = {
        ("w1", "set_extent"): 200,
        ("w1", "neither"): 50,
        ("w2", "neither"): 1,
        ("w3", "l19_773_np"): 4,
        ("w4", "set_extent"): 1,
        ("w4", "neither"): 1,
        ("w5", "neither"): 90,
    }
    alloc = sample.allocate_s1(cells, 80)
    assert sum(alloc.values()) == 80
    assert all(0 <= alloc[c] <= cells[c] for c in cells)
    per_work = collections.Counter()
    per_class = collections.Counter()
    for (w, k), n in alloc.items():
        per_work[w] += n
        per_class[k] += n
    assert per_work["w2"] == 1
    assert per_work["w3"] >= 2
    assert per_work["w4"] == 2
    assert per_class == {"set_extent": 38, "l19_773_np": 4, "neither": 38}


def test_no_two_consecutive_records_share_a_work():
    rows = make_frame()
    works = {r["record_id"]: set(r["works_returned_for"]) for r in rows}
    lines, _ = sample.make_sample(rows, sample.SEED)
    ids = [x["record_id"] for x in lines]
    assert all(not (works[a] & works[b]) for a, b in itertools.pairwise(ids))


def test_separate_works_refuses_an_impossible_order():
    items = [{"record_id": str(i), "works": ["w"]} for i in range(3)]
    with pytest.raises(ValueError):
        sample.separate_works(items)


def test_catalogs_and_strata_interleave_in_the_pilot():
    rows = make_frame()
    lines, _ = sample.make_sample(rows, sample.SEED)
    pilot = [x for x in lines if x["pilot"]]
    assert pilot == lines[: sample.PILOT]
    by_catalog = collections.Counter(x["catalog"] for x in pilot)
    by_stratum = collections.Counter(x["stratum"] for x in pilot)
    assert set(by_catalog) == set(CATALOGS)
    assert all(abs(n - 30) <= 3 for n in by_catalog.values())
    assert set(by_stratum) == set(frame.STRATA)


def test_holdback_is_a_tenth_across_strata_and_outside_the_pilot():
    rows = make_frame()
    lines, weights = sample.make_sample(rows, sample.SEED)
    held = [x for x in lines if x["holdback"]]
    assert len(held) == weights["holdback"] == max(80, -(-len(lines) // 10))
    assert not any(x["pilot"] for x in held)
    by_stratum = collections.Counter(x["stratum"] for x in held)
    in_sample = collections.Counter(x["stratum"] for x in lines)
    for s in frame.STRATA:
        expected = len(held) * in_sample[s] / len(lines)
        assert abs(by_stratum[s] - expected) <= 2


def test_holdback_size_is_ten_per_cent_but_at_least_eighty():
    assert sample.holdback_size(700) == 80
    assert sample.holdback_size(800) == 80
    assert sample.holdback_size(823) == 83


def test_guide_examples_are_excluded_and_checked_against_the_frame():
    rows = make_frame()
    known = {r["record_id"] for r in rows}
    cited = sorted(known)[:2]
    guide = f"Example one is `{cited[0]}`.\n\nExample two: {cited[1]}.\n"
    exclude = frozenset(sample.guide_examples(guide, known))
    assert exclude == set(cited)
    lines, weights = sample.make_sample(rows, sample.SEED, exclude)
    assert not exclude & {x["record_id"] for x in lines}
    assert weights["excluded"] == cited
    assert sample.check(rows, exclude, lines) == []
    with pytest.raises(ValueError):
        sample.guide_examples("see lc|X:999999", known)


def test_excluding_a_record_changes_only_its_catalog_and_stratum():
    rows = make_frame()
    before, _ = sample.make_sample(rows, sample.SEED)
    s4 = next(x for x in before if x["stratum"] == "S4")
    after, _ = sample.make_sample(rows, sample.SEED, {s4["record_id"]})

    def drawn(lines):
        out = collections.defaultdict(set)
        for x in lines:
            out[(x["stratum"], x["catalog"])].add(x["record_id"])
        return out

    a, b = drawn(before), drawn(after)
    cell = (s4["stratum"], s4["catalog"])
    assert all(a[k] == b[k] for k in a if k != cell)
    assert len(a[cell] - b[cell]) == 1


def test_sample_lines_carry_only_what_the_tool_and_scorer_need():
    lines, _ = sample.make_sample(make_frame(), sample.SEED)
    assert {tuple(x) for x in lines} == {
        (
            "record_id",
            "catalog",
            "003",
            "001",
            "marcxml",
            "pilot",
            "holdback",
            "stratum",
        )
    }
