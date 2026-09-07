import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sru_fetch import fetch, inspect

PROBES = [
    # more NLI index names, looking for a subject or classification axis
    ("nli", 'alma.sub="Judaism"', 1, 1),
    ("nli", 'alma.subject_headings="Judaism"', 1, 1),
    ("nli", 'alma.dewey_classification=296', 1, 1),
    ("nli", 'alma.lc_classification=BM', 1, 1),
    ("nli", 'alma.local_subject="Judaism"', 1, 1),
    # booleans and paging
    ("nli", 'alma.language=heb AND alma.main_pub_date=1960', 1, 1),
    ("nli", "alma.language=heb", 1, 400),
    ("lc", 'dc.subject="Judaism" and dc.date=1960', 1, 1),
    ("lc", 'dc.subject="Judaism"', 1, 400),
    ("dnb", "SPR=heb and JHR=1960", 1, 1),
    ("dnb", "SPR=heb", 1, 400),
]
for server, query, n, start in PROBES:
    try:
        xml, cached = fetch(server, query, max_records=n, start_record=start)
    except Exception as exc:
        print(f"{server:4} start={start:<4} {query:52} TRANSPORT {exc}"[:170]); continue
    got, total, diag = inspect(xml)
    note = f" diag={diag}" if diag else ""
    print(f"{server:4} start={start:<4} {query:52} recs={got} total={total}{note}"[:190])
