"""Reachability and record-format probe for candidate new sources."""
import time
import xml.etree.ElementTree as ET
import httpx

M = "{http://www.loc.gov/MARC21/slim}"

SRU = [
    ("k10plus", "https://sru.k10plus.de/opac-de-627",
     [("pica.spr=heb", "marcxml"), ("pica.slw=Judentum", "marcxml"),
      ("pica.jah=1960", "marcxml"),
      ("pica.spr=heb and pica.jah=1960", "marcxml")]),
    ("libhub", "https://discover.libraryhub.jisc.ac.uk/sru-api",
     [('cql.anywhere="Judaism"', "marcxml"),
      ('dc.subject="Judaism"', "marcxml"),
      ('bath.topicalSubject="Judaism"', "marcxml")]),
]

for name, base, queries in SRU:
    for q, schema in queries:
        params = {"operation": "searchRetrieve", "version": "1.1",
                  "query": q, "maximumRecords": "1", "recordSchema": schema}
        try:
            r = httpx.get(base, params=params, timeout=45,
                          follow_redirects=True)
            body = r.text
            status = r.status_code
        except Exception as exc:
            print(f"{name:8} {q:38} TRANSPORT {type(exc).__name__}: {exc}"[:150])
            time.sleep(4); continue
        info = f"HTTP {status} len={len(body)}"
        try:
            root = ET.fromstring(body)
            nrec = len(root.findall(f".//{M}record"))
            total = next((e.text for e in root.iter()
                          if e.tag.endswith('numberOfRecords')), None)
            diag = next((e.text for e in root.iter()
                         if e.tag.endswith('message') and e.text), None)
            info += f" marcrecs={nrec} total={total}"
            if diag: info += f" diag={diag[:60]}"
        except ET.ParseError as exc:
            info += f" NOT-XML/parse: {str(exc)[:40]} :: {body[:60]!r}"
        print(f"{name:8} {q:38} {info}"[:190])
        time.sleep(4)

# Harvard LibraryCloud: REST, no key, MODS by default.
for path, q in [("items.json", "judaism"), ("items.dc.json", "judaism")]:
    url = f"https://api.lib.harvard.edu/v2/{path}"
    try:
        r = httpx.get(url, params={"q": q, "limit": 1}, timeout=45,
                      follow_redirects=True)
        head = r.text[:220].replace("\n", " ")
        print(f"harvard  {path:38} HTTP {r.status_code} len={len(r.text)} :: {head}"[:260])
    except Exception as exc:
        print(f"harvard  {path:38} TRANSPORT {type(exc).__name__}: {exc}"[:150])
    time.sleep(4)
