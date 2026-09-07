"""One tiny request per candidate index, to learn what each server honors."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sru_fetch import fetch, inspect

PROBES = [
    ("nli", 'alma.subject="Judaism"'),
    ("nli", 'alma.subject="יהדות"'),
    ("nli", "alma.language=heb"),
    ("nli", "alma.main_pub_date=1960"),
    ("nli", 'alma.publisher="מוסד הרב קוק"'),
    ("nli", "alma.material_type=BK"),
    ("nli", 'alma.all_for_ui="Judaism"'),
    ("lc", 'dc.subject="Judaism"'),
    ("lc", 'bath.topicalSubject="Judaism"'),
    ("lc", 'dc.language="heb"'),
    ("lc", "dc.date=1960"),
    ("lc", 'dc.publisher="Mossad Harav Kook"'),
    ("lc", 'cql.anywhere="Judaism"'),
    ("dnb", "WOE=Judentum"),
    ("dnb", "SW=Judentum"),
    ("dnb", "JHR=1960"),
    ("dnb", "SPR=heb"),
    ("dnb", "MAT=books"),
    ("dnb", "TIT=Talmud"),
]

for server, query in PROBES:
    try:
        xml, cached = fetch(server, query, max_records=1)
    except Exception as exc:
        print(f"{server:4} {query:40} TRANSPORT {type(exc).__name__}: {exc}"[:150])
        continue
    n, total, diag = inspect(xml)
    mark = "cache" if cached else "live "
    note = f" diag={diag}" if diag else ""
    print(f"{server:4} {query:40} {mark} recs={n} total={total}{note}"[:190])
