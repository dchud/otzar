"""Full analysis over however many catalogs the corpus holds."""
import collections
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist
from sklearn.metrics import adjusted_mutual_info_score as ami

HERE = pathlib.Path("tmp/vagf")
M = "{http://www.loc.gov/MARC21/slim}"
ADMIN = {"010", "016", "029", "035", "040", "042", "049", "850", "852",
         "883", "884"}


def is_local(f):
    tag = f.split(":", 1)[1].split("$")[0].split(".")[0][:3]
    if not tag.isdigit():
        return True
    return tag[0] == "9" or tag in ADMIN or (tag[0] in "0569" and tag[1] == "9")


# ---- markers, straight from the raw MARC, no frequency threshold ----
MARKS = [
    ("LDR/07=d subunit", lambda t, s, b: b == "d"),
    ("LDR/07=a analytic", lambda t, s, b: b == "a"),
    ("773 host item", lambda t, s, b: t["773"] > 0),
    ("490 transcribed series", lambda t, s, b: t["490"] > 0),
    ("830 authorized series", lambda t, s, b: t["830"] > 0),
    ("800/810/811 name-title",
     lambda t, s, b: any(t[x] for x in ("800", "810", "811"))),
    ("440 obsolete series", lambda t, s, b: t["440"] > 0),
    ("245$n or $p", lambda t, s, b: bool(s["245"] & {"n", "p"})),
    ("246 variant title", lambda t, s, b: t["246"] > 0),
    ("505 contents", lambda t, s, b: t["505"] > 0),
    ("740 added title", lambda t, s, b: t["740"] > 0),
    ("730 uniform added", lambda t, s, b: t["730"] > 0),
    ("130/240 uniform title", lambda t, s, b: t["130"] + t["240"] > 0),
    ("880 linked script", lambda t, s, b: t["880"] > 0),
    ("020 isbn", lambda t, s, b: t["020"] > 0),
]

rows_raw = [json.loads(x) for x in
            (HERE / "corpus.jsonl").open(encoding="utf-8")]
servers = sorted({r["server"] for r in rows_raw})
by = collections.defaultdict(collections.Counter)
era_by = collections.defaultdict(collections.Counter)
tot, era_tot = collections.Counter(), collections.Counter()
ERAS = [(1900, 1945, "1900-44"), (1945, 1990, "1945-89"), (1990, 2026, "1990-")]
for r in rows_raw:
    try:
        rec = ET.fromstring(r["xml"])
    except ET.ParseError:
        continue
    leader = rec.findtext(f"{M}leader") or ""
    t, s = collections.Counter(), collections.defaultdict(set)
    for df in rec.findall(f"{M}datafield"):
        t[df.get("tag")] += 1
        for sf in df.findall(f"{M}subfield"):
            s[df.get("tag")].add(sf.get("code"))
    b = leader[7] if len(leader) > 7 else "?"
    tot[r["server"]] += 1
    y = r.get("year")
    era = next((lb for a, z, lb in ERAS if y and a <= y < z), None)
    if era:
        era_tot[era] += 1
    for name, fn in MARKS:
        if fn(t, s, b):
            by[name][r["server"]] += 1
            if era:
                era_by[name][era] += 1

print(f"corpus {sum(tot.values())} records across {len(servers)} catalogs")
print("  " + ", ".join(f"{s}={tot[s]}" for s in servers) + "\n")
print(f"{'marker':25}" + "".join(f"{s[:7].upper():>11}" for s in servers))
for name, _ in MARKS:
    print(f"{name:25}" + "".join(
        f"{by[name][s]:5}{100 * by[name][s] // max(tot[s], 1):4}% "
        for s in servers))
print(f"\n{'marker':25}" + "".join(f"{lb:>11}" for *_, lb in ERAS))
for name, _ in MARKS:
    print(f"{name:25}" + "".join(
        f"{era_by[name][lb]:5}{100 * era_by[name][lb] // max(era_tot[lb], 1):4}% "
        for *_, lb in ERAS))

# ---- clustering ----
data = json.loads((HERE / "features.json").read_text())
rows = data["rows"]


def build(subset, drop_local):
    cols = sorted({f for r in subset for f in r["feat"]
                   if not (drop_local and is_local(f))})
    ci = {f: i for i, f in enumerate(cols)}
    X = np.zeros((len(subset), len(cols)), dtype=bool)
    for i, r in enumerate(subset):
        for f in r["feat"]:
            if f in ci:
                X[i, ci[f]] = True
    keep = X.any(axis=0) & ~X.all(axis=0)
    return X[:, keep], [c for c, k in zip(cols, keep) if k]


KEYS = ("bib_level", "server", "rec_type", "agency", "desc_form", "decade")


def scores(subset, drop_local, ks, title):
    X, cols = build(subset, drop_local)
    Z = linkage(pdist(X, metric="jaccard"), method="average")
    print(f"\n{title}  n={len(subset)} features={X.shape[1]} "
          f"local_dropped={drop_local}")
    for k in ks:
        lab = fcluster(Z, k, criterion="maxclust")
        sc = {key: ami([str(r["lab"][key]) for r in subset], lab)
              for key in KEYS}
        sizes = sorted(collections.Counter(lab).values(), reverse=True)[:5]
        print(f"  k={k:2} " + " ".join(f"{a}={b:.3f}" for a, b in
                                       sorted(sc.items(), key=lambda kv: -kv[1]))
              + f"   sizes={sizes}")


print("\n" + "=" * 70)
scores(rows, False, (4, 8), "ALL CATALOGS, local fields kept")
scores(rows, True, (4, 8, 12), "ALL CATALOGS, local fields dropped")
for s in servers:
    sub = [r for r in rows if r["lab"]["server"] == s]
    if len(sub) >= 200:
        scores(sub, True, (4, 8), f"{s.upper()} only")

alma = [r for r in rows if r["lab"]["server"] in ("nli", "oxford")]
if len({r["lab"]["server"] for r in alma}) == 2:
    print("\n" + "=" * 70)
    print("NLI vs OXFORD -- same Alma software, different institution")
    scores(alma, True, (2, 4, 6), "Alma pair, local fields dropped")
    scores(alma, False, (2, 4, 6), "Alma pair, local fields kept")
