"""Score the existing partitions against leader/19, the label the first
run omitted. Features are unchanged, so the partitions are identical."""
import collections, json, pathlib
import xml.etree.ElementTree as ET
import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist
from sklearn.metrics import adjusted_mutual_info_score as ami

HERE = pathlib.Path("tmp/vagf")
M = "{http://www.loc.gov/MARC21/slim}"
ADMIN = {"010","016","029","035","040","042","049","850","852","883","884"}
def is_local(f):
    tag = f.split(":", 1)[1].split("$")[0].split(".")[0][:3]
    if not tag.isdigit(): return True
    return tag[0]=="9" or tag in ADMIN or (tag[0] in "0569" and tag[1]=="9")

# leader/19 per record id, straight from the corpus
l19 = {}
for line in (HERE/"corpus.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    try: rec = ET.fromstring(r["xml"])
    except ET.ParseError: continue
    ldr = rec.findtext(f"{M}leader") or ""
    l19[r["id"]] = (ldr[19] if len(ldr) > 19 and ldr[19].strip() else "#")

data = json.loads((HERE/"features.json").read_text())
rows = [r for r in data["rows"] if r["id"] in l19]
for r in rows:
    r["lab"]["multipart_l19"] = l19[r["id"]]

def build(sub, drop_local):
    cols = sorted({f for r in sub for f in r["feat"]
                   if not (drop_local and is_local(f))})
    ci = {f: i for i, f in enumerate(cols)}
    X = np.zeros((len(sub), len(cols)), dtype=bool)
    for i, r in enumerate(sub):
        for f in r["feat"]:
            if f in ci: X[i, ci[f]] = True
    k = X.any(axis=0) & ~X.all(axis=0)
    return X[:, k]

KEYS = ("multipart_l19","bib_level","server","rec_type","agency","desc_form")
def run(sub, drop_local, ks, title):
    X = build(sub, drop_local)
    Z = linkage(pdist(X, metric="jaccard"), method="average")
    print(f"\n{title}  n={len(sub)} local_dropped={drop_local}")
    dist = collections.Counter(r["lab"]["multipart_l19"] for r in sub)
    print(f"  leader/19 distribution: {dict(dist)}")
    for k in ks:
        lab = fcluster(Z, k, criterion="maxclust")
        sc = {key: ami([str(r["lab"][key]) for r in sub], lab) for key in KEYS}
        print(f"  k={k:2} " + "  ".join(
            f"{a}={b:.3f}" for a, b in sorted(sc.items(), key=lambda kv: -kv[1])))

run(rows, True, (4, 8, 12), "ALL CATALOGS, standard fields")
pop = [r for r in rows if r["lab"]["server"] in ("k10plus", "dnb")]
run(pop, True, (4, 8, 12), "K10PLUS + DNB (the catalogs that populate leader/19)")
books = [r for r in pop if r["lab"]["rec_type"] == "a"]
run(books, True, (4, 8, 12), "K10PLUS + DNB, language material only")
