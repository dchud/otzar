"""Draw the clustering corpus along axes that do not presuppose structure.

Query axes are language, publication year, subject heading and publisher.
None of them mention a work by name, and none of them reference a field
whose presence the clustering will later test for. Two strata are drawn
outside Judaica entirely, as a control on whether any cluster that
appears is a property of cataloging or of the subject domain.
"""
import json, pathlib, random, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sru_fetch import fetch, inspect, M

YEARS = [1900, 1925, 1950, 1965, 1980, 1995, 2005, 2015, 2022]

JOBS = []  # (server, query, {stratum labels})

for y in YEARS:
    for lang in ("heb", "yid", "eng"):
        JOBS.append(("nli", f"alma.language={lang} AND alma.main_pub_date={y}",
                     {"axis": "language+year", "lang": lang, "year": y,
                      "domain": "judaica"}))
for pub in ("מוסד הרב קוק", "ArtScroll", "Mossad Harav Kook", "Feldheim"):
    JOBS.append(("nli", f'alma.publisher="{pub}"',
                 {"axis": "publisher", "publisher": pub, "year": None,
                  "domain": "judaica"}))

LC_SUBJECTS = ["Judaism", "Jews", "Hebrew literature", "Rabbinical literature"]
for y in YEARS:
    for subj in LC_SUBJECTS:
        JOBS.append(("lc", f'dc.subject="{subj}" and dc.date={y}',
                     {"axis": "subject+year", "subject": subj, "year": y,
                      "domain": "judaica"}))
for y in (1950, 1995, 2015):
    for subj in ("Physics", "Agriculture"):
        JOBS.append(("lc", f'dc.subject="{subj}" and dc.date={y}',
                     {"axis": "control", "subject": subj, "year": y,
                      "domain": "control"}))

for y in YEARS:
    JOBS.append(("dnb", f"SPR=heb and JHR={y}",
                 {"axis": "language+year", "lang": "heb", "year": y,
                  "domain": "judaica"}))
    JOBS.append(("dnb", f"SW=Judentum and JHR={y}",
                 {"axis": "subject+year", "subject": "Judentum", "year": y,
                  "domain": "judaica"}))
for y in (1950, 1995, 2015):
    JOBS.append(("dnb", f"SPR=yid and JHR={y}",
                 {"axis": "language+year", "lang": "yid", "year": y,
                  "domain": "judaica"}))
    JOBS.append(("dnb", f"MAT=books and JHR={y}",
                 {"axis": "control", "subject": None, "year": y,
                  "domain": "control"}))

for y in YEARS:
    JOBS.append(("k10plus", f"pica.spr=heb and pica.jah={y}",
                 {"axis": "language+year", "lang": "heb", "year": y,
                  "domain": "judaica"}))
    JOBS.append(("k10plus", f"pica.slw=Judentum and pica.jah={y}",
                 {"axis": "subject+year", "subject": "Judentum", "year": y,
                  "domain": "judaica"}))
for y in (1950, 1995, 2015):
    JOBS.append(("k10plus", f"pica.spr=yid and pica.jah={y}",
                 {"axis": "language+year", "lang": "yid", "year": y,
                  "domain": "judaica"}))
    JOBS.append(("k10plus", f"pica.slw=Physik and pica.jah={y}",
                 {"axis": "control", "subject": "Physik", "year": y,
                  "domain": "control"}))

# Oxford runs the same Alma software as NLI. Drawing both separates the
# shape the export software imposes from the practice of the cataloging
# institution, which are otherwise inseparable.
for y in YEARS:
    JOBS.append(("oxford", f"alma.language=heb AND alma.main_pub_date={y}",
                 {"axis": "language+year", "lang": "heb", "year": y,
                  "domain": "judaica"}))
for y in (1950, 1995, 2015):
    JOBS.append(("oxford", f"alma.language=yid AND alma.main_pub_date={y}",
                 {"axis": "language+year", "lang": "yid", "year": y,
                  "domain": "judaica"}))
    JOBS.append(("oxford", f"alma.language=eng AND alma.main_pub_date={y}",
                 {"axis": "control", "lang": "eng", "year": y,
                  "domain": "control"}))

# Interleave servers so each host's pacing gap elapses during other work.
random.Random(0).shuffle(JOBS)

def record_id(rec):
    cf = {c.get("tag"): (c.text or "") for c in rec.findall(f"{M}controlfield")}
    return f"{cf.get('003', '')}:{cf.get('001', '')}"

out = pathlib.Path(__file__).parent / "corpus.jsonl"
seen, kept, live, failed = set(), 0, 0, []
with out.open("w", encoding="utf-8") as fh:
    for i, (server, query, labels) in enumerate(JOBS, 1):
        try:
            xml, cached = fetch(server, query, max_records=50)
        except Exception as exc:
            failed.append((server, query, str(exc)[:60])); continue
        live += 0 if cached else 1
        got, total, diag = inspect(xml)
        if diag and not got:
            failed.append((server, query, f"diag: {diag[:50]}")); continue
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            failed.append((server, query, "parse error")); continue
        new = 0
        for rec in root.findall(f".//{M}record"):
            rid = f"{server}|{record_id(rec)}"
            if rid in seen or rid.endswith("|:"):
                continue
            seen.add(rid); new += 1; kept += 1
            fh.write(json.dumps({
                "id": rid, "server": server, "query": query,
                **labels,
                "xml": ET.tostring(rec, encoding="unicode"),
            }) + "\n")
        print(f"[{i:3}/{len(JOBS)}] {server:4} {query[:46]:46} "
              f"got={got:3} new={new:3} total={total}", flush=True)

print(f"\nkept {kept} unique records from {len(JOBS)} queries "
      f"({live} live requests, {len(JOBS) - live} cached)")
for server, query, why in failed:
    print(f"  FAILED {server:4} {query[:50]:50} {why}")
