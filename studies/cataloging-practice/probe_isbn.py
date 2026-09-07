import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sru_fetch import fetch, inspect
ISBN = "9789176370582"
FORMS = [
    ("nli", f'alma.isbn={ISBN}'), ("nli", f'alma.all_for_ui={ISBN}'),
    ("oxford", f'alma.isbn={ISBN}'),
    ("lc", f'bath.isbn={ISBN}'),
    ("dnb", f"NUM={ISBN}"), ("dnb", f"ISB={ISBN}"),
    ("k10plus", f"pica.isb={ISBN}"), ("k10plus", f"pica.all={ISBN}"),
]
for server, q in FORMS:
    try:
        xml, cached = fetch(server, q, max_records=5)
    except Exception as exc:
        print(f"{server:8} {q:34} TRANSPORT {type(exc).__name__}"); continue
    n, total, diag = inspect(xml)
    print(f"{server:8} {q:34} recs={n} total={total}"
          + (f" diag={diag[:44]}" if diag else ""))
