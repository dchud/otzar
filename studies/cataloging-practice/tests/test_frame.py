"""Tests for the candidate frame: cache keys, record text, deduplication,
the round-trip check and stratum assignment.

Run explicitly; they read only the fixtures beside them:

    uv run pytest studies/cataloging-practice/tests
"""

import json
import pathlib
import sys
import xml.etree.ElementTree as ET

import httpx
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import frame
import set_report
import sru_fetch
from set_cases import WORKS, describe_record

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
RESPONSE = FIXTURES / "responses" / "lc-efae30b01aa04ba2bff8ffee.xml"
NS = "http://www.loc.gov/MARC21/slim"


# File names of real survey responses, as sru_fetch wrote them. A change
# to the key would leave every cached response unreachable.
@pytest.mark.parametrize(
    "catalog, name",
    [
        ("nli", "nli-6d26f4d0c0194c66573bc19b.xml"),
        ("oxford", "oxford-3e7dcb09c2fc2f4ec346aceb.xml"),
        ("k10plus", "k10plus-dea8a8f659845f12df2da3cd.xml"),
        ("lc", "lc-efae30b01aa04ba2bff8ffee.xml"),
        ("dnb", "dnb-71223bee4e99f5a32d2a9b29.xml"),
    ],
)
def test_cache_name_matches_the_files_fetch_wrote(catalog, name):
    query = WORKS["Talmud Bavli"][catalog]
    assert sru_fetch.cache_name(catalog, query, 50) == name


def test_fetch_reads_the_file_cache_name_names(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("fetch went to the network")

    monkeypatch.setattr(sru_fetch, "CACHE", RESPONSE.parent)
    monkeypatch.setattr(httpx, "get", no_network)
    query = WORKS["Talmud Bavli"]["lc"]
    text, cached = sru_fetch.fetch("lc", query, max_records=50)
    assert cached
    assert text == RESPONSE.read_text(encoding="utf-8")


def test_split_records_returns_each_record_as_sent():
    data = RESPONSE.read_bytes()
    decoded = data.decode("utf-8")
    texts = frame.split_records(data)
    assert len(texts) == 2
    for text in texts:
        assert text in decoded
        assert text.startswith('<record xmlns="http://www.loc.gov/MARC21')
        assert text.endswith("</record>")
        assert ET.fromstring(text).tag == f"{{{NS}}}record"
    # The Hebrew before the second record makes byte and character
    # offsets differ; a slice at the wrong one would miss its 001.
    assert '<controlfield tag="001">1002</controlfield>' in texts[1]


def test_split_records_matches_the_namespace_not_the_prefix():
    data = (
        '<r xmlns="http://www.loc.gov/zing/srw/"><record>'
        f'<marc:record xmlns:marc="{NS}"><marc:leader>x</marc:leader>'
        "</marc:record></record></r>"
    ).encode()
    texts = frame.split_records(data)
    assert texts == [
        (
            f'<marc:record xmlns:marc="{NS}"><marc:leader>x</marc:leader>'
            "</marc:record>"
        )
    ]


def marc(f001, title, f003=None, a300="1 v.", tail=""):
    f003 = f'<controlfield tag="003">{f003}</controlfield>' if f003 else ""
    return (
        f'<record xmlns="{NS}"><leader>00000cam a2200000 a 4500</leader>'
        f'<controlfield tag="001">{f001}</controlfield>{f003}'
        '<datafield tag="245" ind1="0" ind2="0">'
        f'<subfield code="a">{title}</subfield></datafield>'
        '<datafield tag="300" ind1=" " ind2=" ">'
        f'<subfield code="a">{a300}</subfield></datafield>{tail}</record>'
    )


TB, ST = "Talmud Bavli", "Schottenstein Talmud"
RESPONSES = [
    (TB, "lc", "a.xml", "2026-09-07", [
        marc("1", "Talmud Bavli"),
        marc("2", "A history of the Talmud"),
        marc("1", "Talmud Bavli"),
    ]),
    (TB, "dnb", "b.xml", "2026-09-07", [
        marc("1", "Talmud Bavli", f003="DE-101"),
    ]),
    (ST, "lc", "c.xml", "2026-09-08", [
        marc("1", "Talmud Bavli", tail=" "),
        marc("3", "Schottenstein edition of the Talmud"),
    ]),
]  # fmt: skip


def test_build_deduplicates_within_a_catalog_on_001():
    rows, occurrences, counts = frame.build(RESPONSES)
    ids = [r["record_id"] for r in rows]
    assert ids == ["lc|:1", "lc|:2", "lc|:3", "dnb|DE-101:1"]
    first = rows[0]
    assert first["works_returned_for"] == [TB, ST]
    assert first["retrieved"] == "2026-09-07"
    assert first["marcxml"] == RESPONSES[0][4][0]
    assert first["003"] == "" and first["001"] == "1"
    assert occurrences[(TB, "lc")] == ["lc|:1", "lc|:2", "lc|:1"]
    assert occurrences[(ST, "lc")] == ["lc|:1", "lc|:3"]
    assert counts["returned:lc"] == 5
    assert counts["returned:dnb"] == 1
    assert counts["duplicate_within_response"] == 1
    assert counts["duplicate_across_works"] == 1
    assert counts["duplicate_differing_text"] == 1


def test_title_filter_is_applied_for_each_work_that_returned_a_record():
    rows, _, _ = frame.build(RESPONSES)
    by_id = {r["record_id"]: r for r in rows}
    p = by_id["lc|:1"]["pipeline"]
    assert p["title_accepted"] is True
    assert p["title_accepted_for"] == [TB]
    assert by_id["lc|:2"]["pipeline"]["title_accepted"] is False
    assert by_id["lc|:3"]["pipeline"]["title_accepted_for"] == [ST]


def published(responses):
    """set_cases.json and set_summary.json as the survey would write them."""
    cases, summary = {}, {}
    for work, catalog, _, _, texts in responses:
        recs = [describe_record(ET.fromstring(t)) for t in texts]
        cases.setdefault(work, {})[catalog] = {"records": recs}
        summary.setdefault(work, {})[catalog] = set_report.cell(work, recs)
    return json.loads(json.dumps(cases)), summary


def round_trip(rows):
    return [json.loads(json.dumps(r, ensure_ascii=False)) for r in rows]


def test_check_passes_on_a_frame_read_back():
    rows, occurrences, _ = frame.build(RESPONSES)
    cases, summary = published(RESPONSES)
    assert frame.check(round_trip(rows), occurrences, cases, summary) == []


def test_check_reports_an_altered_record():
    rows, occurrences, _ = frame.build(RESPONSES)
    cases, summary = published(RESPONSES)
    rows = round_trip(rows)
    rows[1]["marcxml"] = rows[1]["marcxml"].replace("history", "study")
    problems = frame.check(rows, occurrences, cases, summary)
    assert "lc|:2: sha256 differs from the record" in problems


def test_check_reports_a_missing_record():
    rows, occurrences, _ = frame.build(RESPONSES)
    cases, summary = published(RESPONSES)
    rows = [r for r in round_trip(rows) if r["record_id"] != "lc|:3"]
    problems = frame.check(rows, occurrences, cases, summary)
    assert problems == [f"{ST} / lc: ['lc|:3'] not in frame"]


def test_check_reports_a_count_the_summary_does_not_have():
    rows, occurrences, _ = frame.build(RESPONSES)
    cases, summary = published(RESPONSES)
    summary[TB]["lc"]["named"] += 1
    problems = frame.check(round_trip(rows), occurrences, cases, summary)
    assert problems == [f"{TB} / lc: differs from summary"]


def outcome(**changes):
    p = {
        "title_accepted": True,
        "title_accepted_for": [TB],
        "leader07": "m",
        "vendor": False,
        "extent": "single",
        "leader19": "-",
        "t773": False,
        "np": False,
        "t505": False,
    }
    p.update(changes)
    if not p["title_accepted"]:
        p["title_accepted_for"] = []
    return p


@pytest.mark.parametrize(
    "changes, stratum",
    [
        ({}, "S1"),
        ({"vendor": True, "extent": "online"}, "S2"),
        ({"leader07": "a"}, "S3"),
        ({"leader07": "a", "vendor": True}, "S3"),
        ({"title_accepted": False, "extent": "counted"}, "S4"),
        ({"title_accepted": False, "extent": "open"}, "S4"),
        ({"title_accepted": False, "leader19": "c"}, "S4"),
        ({"title_accepted": False, "t773": True}, "S4"),
        ({"title_accepted": False, "np": True}, "S4"),
        ({"title_accepted": False, "vendor": True, "leader07": "a"}, "S5"),
        ({"title_accepted": False, "extent": "online"}, "S5"),
        ({"title_accepted": False, "t505": True}, "S5"),
        ({"title_accepted": False, "leader19": "-"}, "S5"),
        ({"title_accepted": False, "leader19": ""}, "S5"),
    ],
)
def test_stratum_follows_the_filters_in_order(changes, stratum):
    assert frame.stratum(outcome(**changes)) == stratum


@pytest.mark.parametrize(
    "changes, level",
    [
        ({"extent": "counted", "t773": True, "leader19": "c"}, "set_extent"),
        ({"extent": "open"}, "set_extent"),
        ({"leader19": "a"}, "l19_773_np"),
        ({"t773": True}, "l19_773_np"),
        ({"np": True}, "l19_773_np"),
        ({"t505": True}, "neither"),
        ({"leader19": "-"}, "neither"),
    ],
)
def test_level_class_prefers_extent_then_part_signals(changes, level):
    assert frame.level_class(outcome(**changes)) == level


def test_s1_work_is_the_first_work_the_record_names():
    p = outcome(title_accepted_for=[ST, TB])
    assert frame.s1_work(p, [TB, ST]) == TB
