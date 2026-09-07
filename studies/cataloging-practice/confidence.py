"""Bootstrap intervals on AMI, and cluster stability under resampling."""
import collections, json, pathlib
import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist
from sklearn.metrics import adjusted_mutual_info_score as ami

HERE = pathlib.Path(__file__).parent
RNG = np.random.default_rng(20260907)
data = json.loads((HERE / "features.json").read_text())
rows = data["rows"]
ADMIN = {"010","016","029","035","040","042","049","850","852","883","884"}

def is_local(f):
    tag = f.split(":", 1)[1].split("$")[0].split(".")[0][:3]
    if not tag.isdigit(): return True
    return tag[0] == "9" or tag in ADMIN or (tag[0] in "0569" and tag[1] == "9")

def build(subset, drop_local):
    cols = sorted({f for r in subset for f in r["feat"]
                   if not (drop_local and is_local(f))})
    ci = {f: i for i, f in enumerate(cols)}
    X = np.zeros((len(subset), len(cols)), dtype=bool)
    for i, r in enumerate(subset):
        for f in r["feat"]:
            if f in ci: X[i, ci[f]] = True
    keep = X.any(axis=0) & ~X.all(axis=0)
    return X[:, keep]

KEYS = ("server", "agency", "bib_level", "rec_type", "desc_form", "decade")
out = {}

for drop_local in (False, True):
    X = build(rows, drop_local)
    Z = linkage(pdist(X, metric="jaccard"), method="average")
    tag = "standard_only" if drop_local else "all_fields"
    out[tag] = {}
    for k in (4, 8, 12):
        lab = fcluster(Z, k, criterion="maxclust")
        entry = {}
        for key in KEYS:
            truth = np.array([str(r["lab"][key]) for r in rows])
            point = ami(truth, lab)
            boots = []
            for _ in range(400):
                idx = RNG.integers(0, len(rows), len(rows))
                boots.append(ami(truth[idx], lab[idx]))
            lo, hi = np.percentile(boots, [2.5, 97.5])
            entry[key] = {"ami": point, "lo": lo, "hi": hi}
        out[tag][k] = entry
        best = max(entry.items(), key=lambda kv: kv[1]["ami"])
        print(f"{tag:14} k={k:2}  best={best[0]} "
              f"{best[1]['ami']:.3f} [{best[1]['lo']:.3f},{best[1]['hi']:.3f}]")

# ---- cluster stability: does the same partition come back on a resample?
print("\ncluster stability (mean max-Jaccard recovery over 30 resamples)")
stab = {}
for drop_local in (False, True):
    tag = "standard_only" if drop_local else "all_fields"
    X = build(rows, drop_local)
    n = len(rows)
    base = fcluster(linkage(pdist(X, metric="jaccard"), method="average"),
                    8, criterion="maxclust")
    recov = collections.defaultdict(list)
    for _ in range(30):
        idx = RNG.choice(n, size=int(0.8 * n), replace=False)
        sub = fcluster(linkage(pdist(X[idx], metric="jaccard"),
                               method="average"), 8, criterion="maxclust")
        for c in np.unique(base):
            orig = set(np.where(base[idx] == c)[0])
            if len(orig) < 10:
                continue
            best = max((len(orig & set(np.where(sub == d)[0]))
                        / len(orig | set(np.where(sub == d)[0]))
                        for d in np.unique(sub)), default=0.0)
            recov[int(c)].append(best)
    stab[tag] = {c: {"mean": float(np.mean(v)), "n": len(v),
                     "size": int((base == c).sum())}
                 for c, v in recov.items()}
    for c, d in sorted(stab[tag].items(), key=lambda kv: -kv[1]["size"]):
        flag = "stable" if d["mean"] >= 0.75 else (
            "moderate" if d["mean"] >= 0.5 else "unstable")
        print(f"  {tag:14} cluster {c} size={d['size']:5} "
              f"recovery={d['mean']:.2f}  {flag}")

json.dump({"ami": out, "stability": stab},
          (HERE / "confidence.json").open("w"), indent=1)
print("\nwrote confidence.json")
