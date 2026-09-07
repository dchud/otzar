import collections, json, pathlib
import xml.etree.ElementTree as ET
import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist
from sklearn.metrics import adjusted_mutual_info_score as ami
M = "{http://www.loc.gov/MARC21/slim}"
HERE = pathlib.Path("tmp/vagf")
l19 = {}
for line in (HERE/"corpus.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    try: rec = ET.fromstring(r["xml"])
    except ET.ParseError: continue
    ldr = rec.findtext(f"{M}leader") or ""
    l19[r["id"]] = ldr[19] if len(ldr) > 19 and ldr[19].strip() else "#"
ADMIN = {"010","016","029","035","040","042","049","850","852","883","884"}
def is_local(f):
    tag = f.split(":",1)[1].split("$")[0].split(".")[0][:3]
    if not tag.isdigit(): return True
    return tag[0]=="9" or tag in ADMIN or (tag[0] in "0569" and tag[1]=="9")
data = json.loads((HERE/"features.json").read_text())
rows = [r for r in data["rows"] if r["id"] in l19]
for r in rows: r["l19"] = l19[r["id"]]
def build(sub, dl):
    cols = sorted({f for r in sub for f in r["feat"] if not (dl and is_local(f))})
    ci = {f:i for i,f in enumerate(cols)}
    X = np.zeros((len(sub), len(cols)), dtype=bool)
    for i,r in enumerate(sub):
        for f in r["feat"]:
            if f in ci: X[i, ci[f]] = True
    k = X.any(axis=0) & ~X.all(axis=0)
    return X[:,k]

for dl, tag in ((True,"standard"),(False,"all fields")):
    X = build(rows, dl); Z = linkage(pdist(X, metric="jaccard"), method="average")
    for k in (4,8,12):
        lab = fcluster(Z, k, criterion="maxclust")
        full = ami([r["l19"] for r in rows], lab)
        idx = [i for i,r in enumerate(rows) if r["lab"]["server"] in ("k10plus","dnb")]
        sub_ami = ami([rows[i]["l19"] for i in idx], lab[idx])
        cvals = [lab[i] for i,r in enumerate(rows) if r["l19"]=="c"]
        big = collections.Counter(lab).most_common(1)[0]
        inbig = sum(1 for v in cvals if v == big[0])
        print(f"{tag:9} k={k:2} corpus-wide AMI(l19)={full:.3f}  "
              f"restricted to K10+DNB={sub_ami:.3f}  "
              f"c-records in largest cluster: {inbig}/{len(cvals)} "
              f"(largest n={big[1]})")

# K10plus alone, fresh partition
sub = [r for r in rows if r["lab"]["server"]=="k10plus"]
X = build(sub, True); Z = linkage(pdist(X, metric="jaccard"), method="average")
print()
for k in (4,8,12):
    lab = fcluster(Z, k, criterion="maxclust")
    print(f"K10plus-only fresh partition k={k:2} AMI(l19)="
          f"{ami([r['l19'] for r in sub], lab):.3f}  "
          f"AMI(l07)={ami([str(r['lab']['bib_level']) for r in sub], lab):.3f}")
