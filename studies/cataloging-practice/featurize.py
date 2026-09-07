"""Turn each MARC record into a binary vector of structural facts.

Features describe only what a record carries: which fields, which
subfields within them, which indicator values, and the 008 date shape.
Labels -- server, 040$a, 040$e, leader/06, leader/07, leader/18, year --
are held out of the vector. Leader/07 and 040$e are the cataloger's own
declaration of treatment and convention, so putting them in the vector
would let the clustering recover them by definition rather than test
whether the structure predicts them.
"""
import collections
import json
import pathlib
import xml.etree.ElementTree as ET

M = "{http://www.loc.gov/MARC21/slim}"
HERE = pathlib.Path(__file__).parent
MIN_FRAC, MAX_FRAC = 0.02, 0.98


def norm_ind(v):
    return "#" if v in (None, "", " ") else v


def parse(rec_xml):
    rec = ET.fromstring(rec_xml)
    leader = rec.findtext(f"{M}leader") or ""
    cfs = {}
    for cf in rec.findall(f"{M}controlfield"):
        cfs.setdefault(cf.get("tag"), cf.text or "")
    dfs = [
        (df.get("tag"), norm_ind(df.get("ind1")), norm_ind(df.get("ind2")),
         [s.get("code") for s in df.findall(f"{M}subfield")],
         {s.get("code"): (s.text or "") for s in df.findall(f"{M}subfield")})
        for df in rec.findall(f"{M}datafield")
    ]
    return leader, cfs, dfs


def features(leader, cfs, dfs):
    f = set()
    counts = collections.Counter(t for t, *_ in dfs)
    for tag, i1, i2, codes, _ in dfs:
        f.add(f"tag:{tag}")
        f.add(f"ind:{tag}.1={i1}")
        f.add(f"ind:{tag}.2={i2}")
        for c in set(codes):
            f.add(f"sub:{tag}${c}")
        if len(codes) != len(set(codes)):
            f.add(f"rep:{tag}$*")
        if "6" in codes:
            f.add("link:script")
    for tag, n in counts.items():
        if n > 1:
            f.add(f"multi:{tag}")
    f008 = cfs.get("008", "")
    if len(f008) >= 15:
        f.add(f"008:datetype={f008[6]}")
        d2 = f008[11:15]
        f.add("008:date2=" + ("open" if d2 == "9999"
                              else "blank" if not d2.strip() or d2 == "||||"
                              else "set"))
    return f


def labels(leader, cfs, dfs, meta):
    a040 = next((s for t, _, _, _, s in dfs if t == "040"), {})
    year = meta.get("year")
    return {
        "server": meta["server"],
        "domain": meta["domain"],
        "year": year,
        "decade": (year // 10 * 10) if year else None,
        "agency": (a040.get("a") or "?").strip().rstrip(".,"),
        "convention": (a040.get("e") or "-").strip().rstrip(".,").lower(),
        "rec_type": leader[6] if len(leader) > 6 else "?",
        "bib_level": leader[7] if len(leader) > 7 else "?",
        "desc_form": leader[18] if len(leader) > 18 else "?",
    }


rows = []
for line in (HERE / "corpus.jsonl").open(encoding="utf-8"):
    meta = json.loads(line)
    try:
        leader, cfs, dfs = parse(meta["xml"])
    except ET.ParseError:
        continue
    rows.append({
        "id": meta["id"],
        "feat": sorted(features(leader, cfs, dfs)),
        "lab": labels(leader, cfs, dfs, meta),
    })

df = collections.Counter(f for r in rows for f in r["feat"])
n = len(rows)
keep = {f for f, c in df.items() if MIN_FRAC * n <= c <= MAX_FRAC * n}
for r in rows:
    r["feat"] = [f for f in r["feat"] if f in keep]

(HERE / "features.json").write_text(
    json.dumps({"vocab": sorted(keep), "rows": rows}), encoding="utf-8")

print(f"records {n}, raw features {len(df)}, kept {len(keep)} "
      f"(present in {MIN_FRAC:.0%}-{MAX_FRAC:.0%} of records)")
print(f"mean features per record: "
      f"{sum(len(r['feat']) for r in rows) / n:.1f}")
for key in ("server", "bib_level", "rec_type", "desc_form", "convention"):
    c = collections.Counter(r["lab"][key] for r in rows)
    print(f"{key:11} {dict(c.most_common(8))}")
c = collections.Counter(r["lab"]["agency"] for r in rows)
print(f"agencies    {len(c)} distinct; top: {dict(c.most_common(10))}")
