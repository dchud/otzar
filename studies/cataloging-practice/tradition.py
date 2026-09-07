"""Do the clusters recover a cataloging tradition rather than an
institution?

LC, Oxford and NLI do not share one system: a Z39.50 gateway and two
separate Alma installations, in three countries. DNB and K10plus share
PICA. If
the structural clusters track the two-way split rather than the
five-way one, the variation is a property of tradition rather than of
each institution's local practice.
"""
import collections
import json
import pathlib

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist
from sklearn.metrics import adjusted_mutual_info_score as ami

HERE = pathlib.Path("tmp/vagf")
ADMIN = {"010","016","029","035","040","042","049","850","852","883","884"}
TRADITION = {"lc": "anglo", "oxford": "anglo", "nli": "anglo",
             "dnb": "pica", "k10plus": "pica"}


def is_local(f):
    tag = f.split(":", 1)[1].split("$")[0].split(".")[0][:3]
    if not tag.isdigit():
        return True
    return tag[0] == "9" or tag in ADMIN or (tag[0] in "0569" and tag[1] == "9")


data = json.loads((HERE / "features.json").read_text())
rows = data["rows"]
for r in rows:
    r["lab"]["tradition"] = TRADITION[r["lab"]["server"]]


def build(sub, drop_local):
    cols = sorted({f for r in sub for f in r["feat"]
                   if not (drop_local and is_local(f))})
    ci = {f: i for i, f in enumerate(cols)}
    X = np.zeros((len(sub), len(cols)), dtype=bool)
    for i, r in enumerate(sub):
        for f in r["feat"]:
            if f in ci:
                X[i, ci[f]] = True
    k = X.any(axis=0) & ~X.all(axis=0)
    return X[:, k]


for drop_local, tag in ((False, "all fields"), (True, "standard only")):
    X = build(rows, drop_local)
    Z = linkage(pdist(X, metric="jaccard"), method="average")
    print(f"\n{tag} ({X.shape[1]} features)")
    for k in (2, 4, 8, 12):
        lab = fcluster(Z, k, criterion="maxclust")
        trad = ami([r["lab"]["tradition"] for r in rows], lab)
        serv = ami([r["lab"]["server"] for r in rows], lab)
        print(f"  k={k:2}  tradition={trad:.3f}   catalog={serv:.3f}"
              f"   ratio={trad / serv if serv else 0:.2f}")
        if k == 2:
            xt = collections.Counter(
                (r["lab"]["tradition"], int(c)) for r, c in zip(rows, lab))
            print(f"        k=2 split: {dict(xt)}")

# How much of the catalog signal is just the tradition? Score each
# tradition's own members against each other.
print("\nWithin each tradition, do the member catalogs still separate?")
for trad in ("anglo", "pica"):
    sub = [r for r in rows if r["lab"]["tradition"] == trad]
    X = build(sub, True)
    Z = linkage(pdist(X, metric="jaccard"), method="average")
    for k in (4, 8):
        lab = fcluster(Z, k, criterion="maxclust")
        print(f"  {trad:6} k={k:2} catalog={ami([r['lab']['server'] for r in sub], lab):.3f}"
              f"  (n={len(sub)}, {len(set(r['lab']['server'] for r in sub))} catalogs)")
