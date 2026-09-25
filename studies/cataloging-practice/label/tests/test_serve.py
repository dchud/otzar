"""Tests for the labeling tool's saving and serving: every save is one
appended line, a restart resumes at the first record without a label,
no record is served twice or lost, and the holdback pass serves only
held-back records, in its own order, after seven days, without their
earlier labels.

Run explicitly; they build a synthetic sample and read no scratch data:

    uv run pytest studies/cataloging-practice/label/tests
"""

import datetime
import json
import pathlib
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import serve

NS = "http://www.loc.gov/MARC21/slim"
GUIDE = serve.load_guide(serve.GUIDE)
FIELDS = dict(GUIDE[1])
NOW = datetime.datetime(2026, 10, 1, 12, tzinfo=datetime.UTC)


def record_xml(n):
    return (
        f'<record xmlns="{NS}"><leader>00000nam a2200000 c 4500</leader>'
        f'<controlfield tag="001">{n}</controlfield>'
        f'<datafield tag="245" ind1="1" ind2="0">'
        f'<subfield code="a">Title {n}</subfield></datafield></record>'
    )


def make_sample(path, n=12, held=(3, 5, 7, 8, 10, 11)):
    lines = [
        {
            "record_id": f"lc|:{i}",
            "catalog": "lc",
            "003": "",
            "001": str(i),
            "marcxml": record_xml(i),
            "pilot": i < 4,
            "holdback": i in held,
            "stratum": "S1",
        }
        for i in range(n)
    ]
    path.write_text(
        "".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8"
    )
    return serve.read_sample(path)


def values(**changes):
    """A complete label: the first value of each field, then changes."""
    out = {name: opts[0][1] for name, opts in GUIDE[1]}
    out[serve.LEVEL] = serve.VOLUME
    out.update(changes)
    return out


def payload(record_id, sure=None, note="", **changes):
    vals = values(**changes)
    conf = {n: "sure" for n, v in vals.items() if v is not None}
    conf.update(sure or {})
    return {
        "record_id": record_id,
        "values": vals,
        "confidence": conf,
        "note": note,
        "seconds": 12.34,
        "idle": False,
    }


@pytest.fixture
def paths(tmp_path):
    lines = make_sample(tmp_path / "sample.jsonl")
    return lines, tmp_path / "labels.jsonl"


def session(paths, pass_name="main", now=NOW):
    lines, labels = paths
    return serve.Session(lines, labels, GUIDE, pass_name, now=now)


def saved_lines(path):
    return [json.loads(x) for x in path.read_text("utf-8").splitlines()]


def label_all_in_order(s, now=NOW):
    served = []
    while (i := s.next_index()) is not None:
        rid = s.record(i)["record_id"]
        served.append(rid)
        s.save(payload(rid), now=now)
    return served


def test_a_new_session_starts_at_the_first_record(paths):
    s = session(paths)
    assert s.next_index() == 0
    assert s.progress() == {"done": 0, "total": 12}
    assert s.record(0)["label"] is None


def test_each_save_appends_one_line_with_ids_and_every_field(paths):
    s = session(paths)
    result = s.save(
        payload("lc|:0", sure={serve.LEVEL: "unsure"}, note=" x "), now=NOW
    )
    assert result == {"next": 1, "done": 1, "total": 12}
    [line] = saved_lines(paths[1])
    names = [name for name, _ in GUIDE[1]]
    assert list(line) == [
        "record_id",
        "catalog",
        "003",
        "001",
        "pass",
        *names,
        "confidence",
        "note",
        "seconds",
        "idle",
        "guide_version",
        "timestamp",
    ]
    assert line["record_id"] == "lc|:0"
    assert (line["catalog"], line["003"], line["001"]) == ("lc", "", "0")
    assert line["pass"] == "main"
    assert line[serve.LEVEL] == serve.VOLUME
    assert line["confidence"][serve.LEVEL] == "unsure"
    assert line["note"] == "x"
    assert line["seconds"] == 12.3
    assert line["idle"] is False
    assert line["guide_version"] == GUIDE[0]
    assert line["timestamp"] == "2026-10-01T12:00:00+00:00"


def test_a_restart_resumes_at_the_record_that_was_not_saved(paths):
    s = session(paths)
    s.save(payload("lc|:0"), now=NOW)
    s.save(payload("lc|:1"), now=NOW)
    # The labeler is part way through record 2 when the tool stops;
    # nothing about it was saved.
    assert s.record(s.next_index())["record_id"] == "lc|:2"
    again = session(paths)
    assert again.next_index() == 2
    assert again.record(2)["record_id"] == "lc|:2"
    assert again.progress() == {"done": 2, "total": 12}


def test_every_record_is_served_once_across_restarts(paths):
    served = []
    for stop_after in (3, 4, 100):
        s = session(paths)
        for _ in range(stop_after):
            i = s.next_index()
            if i is None:
                break
            rid = s.record(i)["record_id"]
            served.append(rid)
            s.save(payload(rid), now=NOW)
    assert served == [f"lc|:{i}" for i in range(12)]
    assert [x["record_id"] for x in saved_lines(paths[1])] == served
    assert session(paths).next_index() is None


def test_a_correction_appends_and_the_later_line_stands(paths):
    s = session(paths)
    s.save(payload("lc|:0"), now=NOW)
    s.save(payload("lc|:1"), now=NOW)
    shown = s.record(0)["label"]
    assert shown["values"] == values()
    level = FIELDS[serve.LEVEL]
    other = next(v for _, v in level if v != serve.VOLUME)
    result = s.save(
        payload("lc|:0", **{serve.LEVEL: other, serve.OWN_TITLE: None}),
        now=NOW,
    )
    assert result["next"] == 2
    lines = saved_lines(paths[1])
    assert [x["record_id"] for x in lines] == ["lc|:0", "lc|:1", "lc|:0"]
    assert lines[-1][serve.LEVEL] == other
    assert lines[-1][serve.OWN_TITLE] is None
    again = session(paths)
    assert again.record(0)["label"]["values"][serve.LEVEL] == other
    assert again.next_index() == 2


def test_saving_again_unchanged_appends_nothing(paths):
    s = session(paths)
    s.save(payload("lc|:0"), now=NOW)
    s.save(payload("lc|:0"), now=NOW)
    assert len(saved_lines(paths[1])) == 1


def test_none_records_unrelated_with_the_works_confidence(paths):
    s = session(paths)
    p = payload(
        "lc|:0",
        sure={serve.WORK: "unsure"},
        **{serve.WORK: serve.NONE, serve.RELATION: None},
    )
    assert serve.RELATION not in p["confidence"]
    s.save(p, now=NOW)
    [line] = saved_lines(paths[1])
    assert line[serve.RELATION] == serve.UNRELATED
    assert line["confidence"][serve.RELATION] == "unsure"


@pytest.mark.parametrize(
    "change, error",
    [
        ({serve.WORK: "Talmud Babli"}, "work: choose a value"),
        ({serve.LEVEL: None}, "level: choose a value"),
        ({"stratum": "S1"}, "not fields in the guide"),
        (
            {serve.LEVEL: serve.CANNOT_JUDGE, serve.OWN_TITLE: None},
            "a note is required",
        ),
        ({serve.RELATION: serve.CANNOT_JUDGE}, "a note is required"),
        ({serve.LEVEL: "single"}, "asked only for a volume"),
        (
            {serve.WORK: serve.NONE, serve.RELATION: "edition"},
            "records unrelated",
        ),
    ],
)
def test_invalid_labels_are_refused_and_nothing_is_written(
    paths, change, error
):
    s = session(paths)
    p = payload("lc|:0", **change)
    with pytest.raises(serve.LabelError, match=error):
        s.save(p, now=NOW)
    assert not paths[1].exists()
    assert s.next_index() == 0


def test_a_note_satisfies_the_requirement(paths):
    s = session(paths)
    change = {serve.LEVEL: serve.OTHER, serve.OWN_TITLE: None}
    s.save(payload("lc|:0", note="serial", **change), now=NOW)
    assert saved_lines(paths[1])[0]["note"] == "serial"


def test_confidence_must_be_sure_or_unsure(paths):
    s = session(paths)
    with pytest.raises(serve.LabelError, match="confidence"):
        s.save(payload("lc|:0", sure={serve.WORK: "maybe"}), now=NOW)


def test_a_record_outside_the_pass_is_refused(paths):
    s = session(paths)
    with pytest.raises(serve.LabelError, match="not in this pass"):
        s.save(payload("lc|:99"), now=NOW)


def test_an_incomplete_last_line_stops_the_start(paths):
    s = session(paths)
    s.save(payload("lc|:0"), now=NOW)
    with paths[1].open("a", encoding="utf-8") as fh:
        fh.write('{"record_id": "lc|:1", "pass": "ma')
    with pytest.raises(serve.InputError, match="incomplete"):
        session(paths)


def test_holdback_pass_serves_only_held_records_in_a_fixed_new_order(paths):
    label_all_in_order(session(paths), now=NOW - datetime.timedelta(days=8))
    first = session(paths, "holdback")
    second = session(paths, "holdback")
    order = [x["record_id"] for x in first.queue]
    held = [f"lc|:{i}" for i in (3, 5, 7, 8, 10, 11)]
    assert sorted(order) == sorted(held)
    assert order == [x["record_id"] for x in second.queue]
    assert order != held
    assert order == sorted(held, key=lambda r: (serve.relabel_key(r), r))


def test_holdback_pass_waits_seven_days_after_the_main_label(paths):
    s = session(paths)
    for i in range(12):
        days = 8 if i in (3, 5, 7) else 6
        s.save(payload(f"lc|:{i}"), now=NOW - datetime.timedelta(days=days))
    # Record 3's main label was corrected two days ago; the relabel
    # waits for seven days after the label that stands.
    level = FIELDS[serve.LEVEL]
    other = next(v for _, v in level if v != serve.VOLUME)
    s.save(
        payload("lc|:3", **{serve.LEVEL: other, serve.OWN_TITLE: None}),
        now=NOW - datetime.timedelta(days=2),
    )
    h = session(paths, "holdback")
    assert sorted(x["record_id"] for x in h.queue) == ["lc|:5", "lc|:7"]
    assert h.waiting == 4


def test_holdback_pass_never_shows_the_main_label(paths):
    label_all_in_order(session(paths), now=NOW - datetime.timedelta(days=8))
    h = session(paths, "holdback")
    for i in range(len(h.queue)):
        assert h.record(i)["label"] is None


def test_holdback_labels_are_their_own_pass(paths):
    label_all_in_order(session(paths), now=NOW - datetime.timedelta(days=8))
    h = session(paths, "holdback")
    relabeled = label_all_in_order(h)
    assert len(relabeled) == 6
    lines = saved_lines(paths[1])
    assert [x["pass"] for x in lines] == ["main"] * 12 + ["holdback"] * 6
    assert session(paths, "holdback").next_index() is None
    main = session(paths)
    assert main.next_index() is None
    assert main.progress() == {"done": 12, "total": 12}


def test_holdback_resumes_where_it_stopped(paths):
    label_all_in_order(session(paths), now=NOW - datetime.timedelta(days=8))
    h = session(paths, "holdback")
    first = h.record(h.next_index())["record_id"]
    h.save(payload(first), now=NOW)
    again = session(paths, "holdback")
    assert again.next_index() == 1
    assert again.record(0)["label"]["values"] == values()


@pytest.mark.enable_socket
def test_the_server_serves_the_page_a_record_and_saves_a_label(paths):
    server = serve.make_server(session(paths), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(base + "/") as r:
            assert b'href="marc.css"' in r.read()
        with urllib.request.urlopen(base + "/marc.css") as r:
            assert r.read().decode() == serve.marc_html.CSS
        with urllib.request.urlopen(base + "/api/session") as r:
            start = json.load(r)
        assert start["index"] == 0
        assert [f["name"] for f in start["fields"]] == list(FIELDS)
        with urllib.request.urlopen(base + "/api/record?index=0") as r:
            rec = json.load(r)
        assert rec["record_id"] == "lc|:0"
        assert rec["catalog"] == "LC"
        body = json.dumps(payload("lc|:0")).encode()
        request = urllib.request.Request(
            base + "/api/label",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as r:
            assert json.load(r)["next"] == 1
        bad = json.dumps(payload("lc|:1", **{serve.WORK: "x"})).encode()
        request = urllib.request.Request(base + "/api/label", data=bad)
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(request)
        assert err.value.code == 400
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(base + "/api/record?index=12")
        assert err.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
    assert len(saved_lines(paths[1])) == 1
