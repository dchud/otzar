"""Can the same item be found in more than one catalog?"""
import collections, json, pathlib, re, unicodedata
import xml.etree.ElementTree as ET
M = "{http://www.loc.gov/MARC21/slim}"
HERE = pathlib.Path("tmp/vagf")

def isbn_norm(v):
    s = re.sub(r"[^0-9Xx]", "", (v or "").split("(")[0])[:13]
    if len(s) == 10:
        core = s[:9]
        tot = sum((10 - i) * (10 if c in "Xx" else int(c))
                  for i, c in enumerate(s))
        if tot % 11:
            return None
        body = "978" + core
        chk = (10 - sum((3 if i % 2 else 1) * int(c)
                        for i, c in enumerate(body)) % 10) % 10
        return body + str(chk)
    return s if len(s) == 13 else None

def title_key(v):
    s = unicodedata.normalize("NFKD", (v or "").lower())
    s = re.sub(r"[^\w\s֐-׿]", " ", s)
    return " ".join(s.split())[:60]

isbns = collections.defaultdict(set)
titles = collections.defaultdict(set)
recs = {}
for line in (HERE / "corpus.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    try:
        rec = ET.fromstring(r["xml"])
    except ET.ParseError:
        continue
    recs[r["id"]] = r
    for df in rec.findall(f"{M}datafield"):
        if df.get("tag") == "020":
            for sf in df.findall(f"{M}subfield"):
                if sf.get("code") == "a":
                    n = isbn_norm(sf.text)
                    if n:
                        isbns[n].add(r["id"])
        if df.get("tag") == "245":
            a = "".join(sf.text or "" for sf in df.findall(f"{M}subfield")
                        if sf.get("code") in ("a", "b"))
            k = title_key(a)
            if len(k) > 12:
                titles[k].add(r["id"])

def cross(index, label):
    multi = {k: v for k, v in index.items() if len(v) > 1}
    xcat = {k: v for k, v in multi.items()
            if len({i.split("|")[0] for i in v}) > 1}
    pairs = collections.Counter()
    for v in xcat.values():
        cats = sorted({i.split("|")[0] for i in v})
        for i in range(len(cats)):
            for j in range(i + 1, len(cats)):
                pairs[(cats[i], cats[j])] += 1
    print(f"{label}: {len(index)} keys, {len(multi)} with >1 record, "
          f"{len(xcat)} spanning >1 catalog")
    for p, n in pairs.most_common(12):
        print(f"    {p[0]:8}/{p[1]:8} {n}")
    return xcat

cross(isbns, "ISBN")
cross(titles, "title")
