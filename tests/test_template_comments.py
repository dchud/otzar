"""Template comments have to actually be comments.

Django's ``{# ... #}`` is a single-line form. An opening ``{#`` whose
``#}`` is on a later line is not a comment at all -- the template
engine renders it as literal text, and it appears on the page.

That failed silently on every record page: a seven-line note explaining
why provenance and ownership marks share one heading was published to
anybody looking at a book. Nothing errored, no test failed, and the
only way to notice was to read a rendered page.

Multi-line notes belong in ``{% comment %}`` ... ``{% endcomment %}``.
"""

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP = {".venv", "staticfiles", "node_modules", ".claude", "tmp", "site"}


def template_files():
    for path in sorted(ROOT.rglob("*.html")):
        if SKIP & set(path.relative_to(ROOT).parts):
            continue
        yield path


def unterminated_hash_comments(path):
    """Lines opening a ``{#`` that does not close on the same line."""
    found = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        start = line.find("{#")
        if start != -1 and "#}" not in line[start:]:
            found.append((number, line.strip()))
    return found


def test_at_least_one_template_is_being_checked():
    """A scan that silently matches nothing proves nothing."""
    assert len(list(template_files())) > 10


@pytest.mark.parametrize(
    "path", list(template_files()), ids=lambda p: str(p.relative_to(ROOT))
)
def test_no_template_opens_a_hash_comment_it_does_not_close(path):
    offenders = unterminated_hash_comments(path)

    assert not offenders, (
        f"{path.relative_to(ROOT)} opens {{# on a line that does not close "
        "it. Django renders that as literal text on the page. Use "
        "{% comment %} ... {% endcomment %} for a multi-line note.\n"
        + "\n".join(f"  line {n}: {line}" for n, line in offenders)
    )
