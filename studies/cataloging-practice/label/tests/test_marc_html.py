"""Tests for what the labeling tool displays: the renderer's rules, the
leader/19 mask, and that nothing from the sampler or the pipeline
reaches the page.

Run explicitly; they build their records inline and read no scratch
data:

    uv run pytest studies/cataloging-practice/label/tests
"""

import ast
import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import marc_html
import serve

NS = "http://www.loc.gov/MARC21/slim"
LEADER = "01234nam a2200385 c 4500"

RECORD = {
    "leader": LEADER,
    "controlfields": [("001", "990010968480205171"), ("008", "191105s193u")],
    "datafields": [
        ("041", " ", " ", [("a", "heb")]),
        (
            "245",
            "1",
            "0",
            [
                ("6", "880-01"),
                ("a", "חמשה חומשי תורה :"),
                ("b", "Miḳraʾot gedolot <44> & more"),
                ("n", "2"),
            ],
        ),
        ("300", " ", " ", [("a", "1 כרך ;"), ("c", '24 ס"מ.')]),
        ("880", "1", "0", [("6", "245-01/(2/r"), ("a", "תורה")]),
    ],
}


def marcxml(record):
    """A MARCXML record element for a record structure."""
    parts = [f'<record xmlns="{NS}">']
    parts.append(f"<leader>{html.escape(record['leader'])}</leader>")
    for tag, value in record["controlfields"]:
        parts.append(
            f'<controlfield tag="{tag}">{html.escape(value)}</controlfield>'
        )
    for tag, ind1, ind2, subfields in record["datafields"]:
        subs = "".join(
            f'<subfield code="{c}">{html.escape(v)}</subfield>'
            for c, v in subfields
        )
        parts.append(
            f'<datafield tag="{tag}" ind1="{ind1}" ind2="{ind2}">'
            f"{subs}</datafield>"
        )
    parts.append("</record>")
    return "".join(parts)


def spans(text):
    """The text of every value span, unescaped, in order."""
    found = re.findall(
        r'<span class="marc-value" dir="auto">(.*?)</span>', text, re.DOTALL
    )
    return [html.unescape(s) for s in found]


def test_every_subfield_code_is_visible_before_its_value():
    out = marc_html.render(RECORD)
    for _, _, _, subfields in RECORD["datafields"]:
        for code, value in subfields:
            written = (
                f'<span class="marc-code">${code}</span> '
                f'<span class="marc-value" dir="auto">'
                f"{html.escape(value)}</span>"
            )
            assert written in out


def test_every_value_is_its_own_span_in_record_order():
    out = marc_html.render(RECORD)
    expected = [RECORD["leader"]]
    expected += [v for _, v in RECORD["controlfields"]]
    for _, _, _, subfields in RECORD["datafields"]:
        expected += [v for _, v in subfields]
    assert spans(out) == expected


def test_each_line_starts_with_the_tag_and_indicators():
    out = marc_html.render(RECORD)
    lines = re.findall(r'<div class="marc-line">(.*?)</div>', out)
    assert len(lines) == 1 + 2 + 4
    assert lines[0].startswith('<span class="marc-tag">LDR</span> ')
    assert lines[1].startswith('<span class="marc-tag">001</span> ')
    assert lines[3].startswith(
        '<span class="marc-tag">041</span> <span class="marc-ind">##</span>'
    )
    assert lines[4].startswith(
        '<span class="marc-tag">245</span> <span class="marc-ind">10</span>'
    )


def test_values_are_escaped():
    out = marc_html.render(RECORD)
    assert "<44>" not in out
    assert "&lt;44&gt; &amp; more" in out
    assert "24 ס&quot;מ." in out


def test_css_isolates_values_in_a_monospace_font_with_hebrew():
    css = marc_html.CSS
    assert re.search(r"\.marc-value\s*{[^}]*unicode-bidi:\s*isolate", css)
    assert "monospace" in css
    assert "DejaVu Sans Mono" in css or "Courier New" in css


def test_renderer_imports_only_the_standard_library():
    source = pathlib.Path(marc_html.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module.split(".")[0])
    assert imported <= set(sys.stdlib_module_names)


def test_structure_reads_marcxml_in_order():
    assert serve.structure(marcxml(RECORD)) == RECORD


def test_leader_19_is_masked_and_nothing_else_changes():
    out = serve.record_html(marcxml(RECORD))
    masked = LEADER[:19] + serve.MASK + LEADER[20:]
    assert spans(out)[0] == masked
    assert LEADER not in out
    assert spans(out)[1:] == spans(marc_html.render(RECORD))[1:]


def test_a_short_leader_is_left_alone():
    short = {**RECORD, "leader": "00000nam"}
    assert serve.mask(short) == short


# Everything the frame and the sampler carry about a record that the
# labeler must not see: the pipeline outcome's field names, and the
# sampler's stratum, pilot and holdback fields.
HIDDEN = (
    "stratum",
    "pilot",
    "holdback",
    "pipeline",
    "title_accepted",
    "title_accepted_for",
    "leader07",
    "leader19",
    "t773",
    "t505",
    "works_returned_for",
    "S4",
)


def sample_line():
    return {
        "record_id": "nli|:990010968480205171",
        "catalog": "nli",
        "003": "",
        "001": "990010968480205171",
        "marcxml": marcxml(RECORD),
        "pilot": True,
        "holdback": True,
        "stratum": "S4",
        "pipeline": {"title_accepted": False, "leader19": "c", "t773": True},
        "works_returned_for": ["Miqraot Gedolot"],
    }


def test_the_page_is_sent_nothing_from_the_sampler_or_pipeline(tmp_path):
    path = tmp_path / "sample.jsonl"
    path.write_text(json.dumps(sample_line()) + "\n", encoding="utf-8")
    lines = serve.read_sample(path)
    guide = serve.load_guide(serve.GUIDE)
    for pass_name in serve.PASSES:
        session = serve.Session(
            lines, tmp_path / "labels.jsonl", guide, pass_name
        )
        sent = [json.dumps(session.describe(), ensure_ascii=False)]
        if session.queue:
            sent.append(json.dumps(session.record(0), ensure_ascii=False))
        for text in sent:
            for word in HIDDEN:
                assert word not in text
    assert set(lines[0]) == set(serve.SAMPLE_KEYS)


def test_the_page_itself_names_nothing_hidden():
    page = serve.PAGE.read_text(encoding="utf-8")
    for word in HIDDEN:
        assert word not in page
