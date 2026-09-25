"""Tests that the labeling guide and the tool agree: the tool reads its
fields, values and keys from the guide's tables, and these check that
the guide's tables satisfy the tool's rules, that the work list is the
survey's, and that the worked examples use only the guide's values.

Run explicitly; they read the committed guide and no scratch data:

    uv run pytest studies/cataloging-practice/label/tests
"""

import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import sample
import serve
from set_cases import WORKS

TEXT = serve.GUIDE.read_text(encoding="utf-8")
VERSION, FIELDS = serve.parse_guide(TEXT)
VALUES = {name: [v for _, v in opts] for name, opts in FIELDS}


def section(title):
    """The text of one "## " section of the guide."""
    match = re.search(
        rf"^## {title}\n(.*?)(?=^## |\Z)", TEXT, re.MULTILINE | re.DOTALL
    )
    assert match, title
    return match.group(1)


def test_the_guide_satisfies_the_tools_rules():
    assert VERSION
    assert serve.check_vocabulary(FIELDS) == []
    assert serve.load_guide(serve.GUIDE) == (VERSION, FIELDS)


def test_the_fields_are_the_six_in_order():
    assert list(VALUES) == [
        "work",
        "relation",
        "level",
        "own-title",
        "origin",
        "carrier",
    ]


def test_the_work_list_is_the_surveys():
    assert VALUES[serve.WORK] == [*WORKS, "other-work", serve.NONE]


def test_the_guide_documents_the_tools_control_keys():
    keys = section("Keys in the tool")
    for key in (serve.UNSURE_KEY, serve.NOTE_KEY, "Enter", "Backspace"):
        assert f"| `{key}` |" in keys


def examples():
    """(number, record ids, labels) for each worked example."""
    text = section("Worked examples")
    out = []
    for block in re.split(r"^### ", text, flags=re.MULTILINE)[1:]:
        number = int(block.split(".", 1)[0])
        ids = {m.group(0) for m in sample.ID_SHAPE.finditer(block)}
        rows = [r for r in block.splitlines() if r.startswith("|")]
        header = serve._cells(rows[0])
        cells = serve._cells(rows[2])
        labels = {}
        for name, cell in zip(header, cells, strict=True):
            found = re.findall(r"`([^`]+)`", cell)
            labels[name] = found[0] if found else None
        out.append((number, ids, labels))
    return out


def test_there_are_twelve_examples_each_citing_one_record():
    found = examples()
    assert [n for n, _, _ in found] == list(range(1, 13))
    assert all(len(ids) == 1 for _, ids, _ in found)
    cited = {m.group(0) for m in sample.ID_SHAPE.finditer(TEXT)}
    assert cited == set().union(*(ids for _, ids, _ in found))
    assert len(cited) == 12


@pytest.mark.parametrize("number, ids, labels", examples())
def test_each_example_uses_the_guides_values_and_rules(number, ids, labels):
    assert list(labels) == list(VALUES)
    for name, value in labels.items():
        if name == serve.OWN_TITLE and labels[serve.LEVEL] != serve.VOLUME:
            assert value is None
        else:
            assert value in VALUES[name]
    if labels[serve.WORK] == serve.NONE:
        assert labels[serve.RELATION] == serve.UNRELATED


def guide_with(table_rows, field="relation"):
    rows = "\n".join(table_rows)
    return (
        "Version: 9\n\n## Fields\n\n"
        "### `work`\n\n| Key | Value |\n|---|---|\n"
        "| `a` | `A` |\n| `x` | `none` |\n\n"
        f"### `{field}`\n\n| Key | Value |\n|---|---|\n{rows}\n\n"
        "### `level`\n\n| Key | Value |\n|---|---|\n"
        "| `v` | `volume` |\n| `c` | `cannot-judge` |\n\n"
        "### `own-title`\n\n| Key | Value |\n|---|---|\n"
        "| `s` | `standalone` |\n\n"
        "## Next\n\n| Key | Value |\n|---|---|\n| `z` | `ignored` |\n"
    )


GOOD = ["| `x` | `unrelated` |", "| `c` | `cannot-judge` |"]


def test_parse_reads_only_the_fields_section():
    version, fields = serve.parse_guide(guide_with(GOOD))
    assert version == "9"
    assert [name for name, _ in fields] == [
        "work",
        "relation",
        "level",
        "own-title",
    ]
    assert dict(fields)["relation"] == [
        ("x", "unrelated"),
        ("c", "cannot-judge"),
    ]
    assert serve.check_vocabulary(fields) == []


@pytest.mark.parametrize(
    "rows, problem",
    [
        (GOOD + ["| `x` | `about` |"], "two values share a key"),
        (GOOD + ["| `u` | `about` |"], "reserved"),
        (GOOD + ["| `n` | `about` |"], "reserved"),
        (GOOD + ["| `ab` | `about` |"], "not one character"),
        (GOOD + ["| `A` | `about` |"], "not lower case"),
        (GOOD[:1], "no value cannot-judge"),
        (GOOD[1:], "no value unrelated"),
    ],
)
def test_check_vocabulary_names_each_problem(rows, problem):
    _, fields = serve.parse_guide(guide_with(rows))
    assert any(problem in p for p in serve.check_vocabulary(fields))


def test_cannot_judge_belongs_to_relation_and_level_only():
    text = guide_with(GOOD).replace(
        "| `s` | `standalone` |",
        "| `s` | `standalone` |\n| `c` | `cannot-judge` |",
    )
    _, fields = serve.parse_guide(text)
    assert any(
        "own-title: cannot-judge" in p for p in serve.check_vocabulary(fields)
    )


def test_a_renamed_rule_value_is_caught():
    text = guide_with(GOOD).replace("`volume`", "`part`")
    _, fields = serve.parse_guide(text)
    assert "level: no value volume" in serve.check_vocabulary(fields)


def test_parse_refuses_a_guide_without_a_version_or_code_spans():
    with pytest.raises(serve.GuideError, match="Version"):
        serve.parse_guide(guide_with(GOOD).replace("Version: 9", ""))
    with pytest.raises(serve.GuideError, match="code spans"):
        serve.parse_guide(guide_with(GOOD + ["| `e` | edition |"]))
