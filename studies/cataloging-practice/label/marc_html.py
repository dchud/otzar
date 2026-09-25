"""Render one MARC record as HTML for reading.

The input is a plain record structure:

    {
        "leader": "00000cam a2200000 i 4500",
        "controlfields": [("001", "..."), ("008", "..."), ...],
        "datafields": [("245", "1", "0", [("a", "..."), ...]), ...],
    }

`render` returns the HTML for one record and `CSS` holds the style
block it needs. The module reads nothing but that structure and knows
nothing about what any position or field means: a caller that hides
part of a record changes the structure before rendering it.

Rendering rules, which callers can rely on:

1. Subfield codes are visible. Each subfield is written as `$` and its
   code, then its value.
2. Every value sits in its own span: the leader, each control field
   and each subfield.
3. Each value span carries `dir="auto"` and `unicode-bidi: isolate`, so
   a Hebrew value lays out right to left inside a left-to-right line
   and cannot reorder the codes or values around it.
4. Each line starts with the tag (`LDR` for the leader), and a data
   field's tag is followed by its two indicators, a blank indicator
   shown as `#`.
5. The font is monospace with Hebrew coverage.

Only the standard library is imported.
"""

import html

CSS = """\
.marc {
  font-family: "DejaVu Sans Mono", "Liberation Mono", "Courier New",
    "Miriam Fixed", monospace;
  font-size: 15px;
  line-height: 1.55;
}
.marc-line {
  direction: ltr;
  padding-left: 8ch;
  text-indent: -8ch;
}
.marc-tag { font-weight: bold; }
.marc-ind { color: #555; }
.marc-code { color: #7a2e8e; font-weight: bold; }
.marc-value {
  unicode-bidi: isolate;
  white-space: pre-wrap;
}
"""


def _value(text):
    return f'<span class="marc-value" dir="auto">{html.escape(text)}</span>'


def _indicator(ind):
    return html.escape(ind if ind and ind.strip() else "#")


def _line(prefix, body):
    return f'<div class="marc-line">{prefix} {body}</div>'


def _tag(tag):
    return f'<span class="marc-tag">{html.escape(tag)}</span>'


def render(record):
    """The HTML for one record structure."""
    lines = [_line(_tag("LDR"), _value(record["leader"]))]
    for tag, value in record["controlfields"]:
        lines.append(_line(_tag(tag), _value(value)))
    for tag, ind1, ind2, subfields in record["datafields"]:
        prefix = (
            f'{_tag(tag)} <span class="marc-ind">'
            f"{_indicator(ind1)}{_indicator(ind2)}</span>"
        )
        body = " ".join(
            f'<span class="marc-code">${html.escape(code)}</span> '
            f"{_value(value)}"
            for code, value in subfields
        )
        lines.append(_line(prefix, body))
    return '<div class="marc">\n' + "\n".join(lines) + "\n</div>"
