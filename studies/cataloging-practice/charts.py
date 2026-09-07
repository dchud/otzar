import json, pathlib
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = pathlib.Path("tmp/vagf")
FIG = pathlib.Path("docs/practice-study/figures"); FIG.mkdir(parents=True, exist_ok=True)
D = json.loads((HERE/"final_stats.json").read_text())
GREY = "#8a8a8a"
plt.rcParams.update({"savefig.transparent": True, "figure.facecolor": "none",
    "axes.facecolor": "none", "text.color": GREY, "axes.labelcolor": GREY,
    "xtick.color": GREY, "ytick.color": GREY, "axes.edgecolor": GREY,
    "font.size": 9})
NAMES = {"nli":"NLI","lc":"LC","dnb":"DNB","k10plus":"K10plus","oxford":"Oxford"}
SV, MARKS, BL = D["servers"], D["marks"], D["bin_labels"]

def save(fig, n):
    fig.savefig(FIG/n, bbox_inches="tight", format="svg"); plt.close(fig)
    print("wrote", n)

# Fig 1: books-only marker x catalog
mat = np.array([[D["books_by_cat"][m]["cells"][s]["p"] for s in SV] for m in MARKS])
fig, ax = plt.subplots(figsize=(6.0, 6.4))
ax.imshow(mat, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(SV)))
ax.set_xticklabels([f"{NAMES[s]}\n(n={D['per_server_books'][s]})" for s in SV],
                   fontsize=8)
ax.set_yticks(range(len(MARKS))); ax.set_yticklabels(MARKS, fontsize=8)
for i in range(len(MARKS)):
    for j in range(len(SV)):
        ax.text(j, i, f"{mat[i,j]*100:.0f}", ha="center", va="center",
                fontsize=7.5, color="white" if mat[i,j] > .55 else "#333")
ax.set_title("Marker prevalence by catalog, language material only\n"
             "(% of records)", color=GREY, pad=10)
save(fig, "fig1-marker-heatmap.svg")

# Fig 2: forest plot
KEY = ["773 host item","490 series stmt","830 series entry","245$n/$p",
       "505 contents","880 linked script","300$c dimensions"]
fig, axes = plt.subplots(1, len(KEY), figsize=(15, 3.4), sharey=True)
for ax, m in zip(axes, KEY):
    for i, s in enumerate(SV):
        c = D["books_by_cat"][m]["cells"][s]
        ax.plot([c["lo"]*100, c["hi"]*100], [i, i], color="#4878a8", lw=2.2)
        ax.plot([c["p"]*100], [i], "o", color="#1f4e79", ms=5)
    v = D["books_by_cat"][m]["cramer_v"]
    ax.set_title(f"{m}\nV={v:.2f}", fontsize=8, color=GREY)
    ax.set_xlim(-3, 100); ax.grid(axis="x", alpha=.2)
axes[0].set_yticks(range(len(SV)))
axes[0].set_yticklabels([NAMES[s] for s in SV])
fig.suptitle("Books only: marker prevalence, 95% Wilson intervals, "
             "with Cramer's V for the catalog effect", color=GREY, y=1.06)
save(fig, "fig2-forest.svg")

# Fig 3: books-only time trends
TREND = ["490 series stmt","830 series entry","773 host item","440 obsolete",
         "505 contents","020 ISBN"]
fig, ax = plt.subplots(figsize=(7.4, 4.2)); cmap = plt.get_cmap("tab10")
for i, m in enumerate(TREND):
    c = D["books_by_epoch"][m]["cells"]
    ax.plot(BL, [c[b]["p"]*100 for b in BL], "-o", ms=4, color=cmap(i), label=m)
    ax.fill_between(BL, [c[b]["lo"]*100 for b in BL],
                    [c[b]["hi"]*100 for b in BL], color=cmap(i), alpha=.15)
ax.set_ylabel("% of records"); ax.grid(alpha=.2)
ax.legend(fontsize=7.5, ncol=2, frameon=False, labelcolor=GREY)
ax.set_title("Books only: marker prevalence by publication era\n"
             "(bands are 95% Wilson intervals)", color=GREY)
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
save(fig, "fig3-time-trends.svg")

# Fig 4: per catalog trends
fig, axes = plt.subplots(1, len(SV), figsize=(15, 3.0), sharey=True)
for ax, s in zip(axes, SV):
    for m, col in (("773 host item","#c44e52"),("490 series stmt","#4878a8"),
                   ("830 series entry","#55a868")):
        pts = [(b, D["books_by_epoch_cat"][m][s][b]["p"]) for b in BL
               if D["books_by_epoch_cat"][m][s][b]["n"] >= 25]
        if pts:
            ax.plot([p[0] for p in pts], [p[1]*100 for p in pts], "-o",
                    ms=4, color=col, label=m.split()[0])
    ax.set_title(NAMES[s], color=GREY); ax.grid(alpha=.2)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=7)
axes[0].set_ylabel("% of records")
axes[-1].legend(fontsize=7, frameon=False, labelcolor=GREY)
fig.suptitle("Books only: how each catalog expresses a part-whole relation "
             "over time", color=GREY, y=1.08)
save(fig, "fig4-time-by-catalog.svg")

# Fig 5: material types
MATS = list(D["rec_types"])
m2 = np.array([[D["all_by_mat"][m]["cells"][t]["p"] for t in MATS] for m in MARKS])
fig, ax = plt.subplots(figsize=(6.6, 6.4))
ax.imshow(m2, cmap="YlOrBr", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(MATS)))
ax.set_xticklabels([f"{D['rec_types'][t]}\n(n={D['all_by_mat'][MARKS[0]]['cells'][t]['n']})"
                    for t in MATS], rotation=40, ha="right", fontsize=7)
ax.set_yticks(range(len(MARKS))); ax.set_yticklabels(MARKS, fontsize=8)
for i in range(len(MARKS)):
    for j in range(len(MATS)):
        ax.text(j, i, f"{m2[i,j]*100:.0f}", ha="center", va="center",
                fontsize=7, color="white" if m2[i,j] > .55 else "#333")
ax.set_title("All material: marker prevalence by type of record\n"
             "(leader/06; % of records)", color=GREY, pad=10)
save(fig, "fig5-material-types.svg")

# --- Fig 6: the four idioms, from the set survey ----------------------
S = json.loads((HERE / "set_summary.json").read_text())
CATS = ["lc", "oxford", "nli", "dnb", "k10plus"]
tot = {c: {"n": 0, "c": 0, "773": 0, "np": 0, "vol": 0, "505": 0} for c in CATS}  # noqa
for work, cats in S.items():
    for c in CATS:
        v = cats[c]
        tot[c]["n"] += v["library"]
        tot[c]["c"] += v["l19_a"] + v["l19_b"] + v["l19_c"]
        tot[c]["773"] += v["t773"]; tot[c]["np"] += v["np"]
        tot[c]["vol"] += v["set_level_extent"]; tot[c]["505"] += v["t505"]
SERIES = [("leader/19 coded", "c", "#1f4e79"),
          ("773 host link", "773", "#c44e52"),
          ("245 $n/$p enumerated", "np", "#dd8452"),
          ("300 volume count", "vol", "#55a868"),
          ("505 contents note", "505", "#8172b3")]
fig, ax = plt.subplots(figsize=(8.6, 4.4))
w = 0.16
x = np.arange(len(CATS))
for i, (lab, key, col) in enumerate(SERIES):
    vals = [100 * tot[c][key] / max(tot[c]["n"], 1) for c in CATS]
    ax.bar(x + (i - 2) * w, vals, w, label=lab, color=col)
ax.set_xticks(x)
ax.set_xticklabels([f"{NAMES[c]}\n(n={tot[c]['n']})" for c in CATS])
ax.set_ylabel("% of records naming the work")
ax.grid(axis="y", alpha=.2)
ax.legend(fontsize=8, frameon=False, labelcolor=GREY, ncol=2)
ax.set_title("How each catalog describes a multi-volume set\n"
             "22 works; library records naming the work, publisher "
             "e-records excluded", color=GREY)
save(fig, "fig6-set-mechanisms.svg")

# --- Fig 7: declared per-volume records, work by work -----------------
works = list(S.keys())
mat = np.full((len(works), len(CATS)), np.nan)
for i, wk in enumerate(works):
    for j, c in enumerate(CATS):
        v = S[wk][c]
        if v["library"]:
            mat[i, j] = 100 * (v["l19_a"] + v["l19_b"] + v["l19_c"]) / v["library"]
fig, ax = plt.subplots(figsize=(6.0, 8.0))
cmap = plt.get_cmap("YlGnBu").copy()
cmap.set_bad("#e8e8e8")
ax.imshow(np.ma.masked_invalid(mat), cmap=cmap, vmin=0, vmax=100,
          aspect="auto")
ax.set_xticks(range(len(CATS)))
ax.set_xticklabels([NAMES[c] for c in CATS], rotation=30, ha="right")
ax.set_yticks(range(len(works)))
ax.set_yticklabels(works, fontsize=8)
for i in range(len(works)):
    for j in range(len(CATS)):
        if np.isnan(mat[i, j]):
            ax.text(j, i, "–", ha="center", va="center", fontsize=7,
                    color="#999999")
        else:
            ax.text(j, i, f"{mat[i, j]:.0f}", ha="center", va="center",
                    fontsize=7,
                    color="white" if mat[i, j] > 55 else "#333333")
ax.set_title("Records coding leader/19, any value\n"
             "% of library records naming the work; grey = none held",
             color=GREY, pad=10)
save(fig, "fig7-declared-by-work.svg")

# --- Fig 8: what each leader/19 value carries -------------------------
# Computed from the corpus rather than transcribed: the two catalogs
# that populate leader/19, language material only.
import collections as _c
import xml.etree.ElementTree as _ET
_M = "{http://www.loc.gov/MARC21/slim}"
_g = {v: _c.Counter() for v in ("c", "b", "a")}
_n = _c.Counter()
for _line in (HERE / "corpus.jsonl").open(encoding="utf-8"):
    _r = json.loads(_line)
    if _r["server"] not in ("k10plus", "dnb"):
        continue
    try:
        _rec = _ET.fromstring(_r["xml"])
    except _ET.ParseError:
        continue
    _l = _rec.findtext(f"{_M}leader") or ""
    if len(_l) < 20 or _l[6] != "a" or _l[19] not in "abc":
        continue
    _v = _l[19]
    _n[_v] += 1
    _t, _s245 = _c.Counter(), set()
    for _df in _rec.findall(f"{_M}datafield"):
        _t[_df.get("tag")] += 1
        if _df.get("tag") == "245":
            _s245 = {x.get("code") for x in _df.findall(f"{_M}subfield")}
    if _t["773"]:
        _g[_v]["773"] += 1
    if _s245 & {"n", "p"}:
        _g[_v]["245 $n/$p"] += 1
    if _t["490"]:
        _g[_v]["490"] += 1
    if _t["830"]:
        _g[_v]["830"] += 1
LABELS = {"c": "c dependent part", "b": "b independent part",
          "a": "a set record"}
L19 = {f"{LABELS[v]} (n={_n[v]})":
       {k: 100 * _g[v][k] / _n[v] for k in
        ("773", "245 $n/$p", "490", "830")}
       for v in ("c", "b", "a")}
print("  fig8 computed:", {k: {a: round(b) for a, b in v.items()}
                           for k, v in L19.items()})
fig, ax = plt.subplots(figsize=(7.4, 3.8))
keys = ["773", "245 $n/$p", "490", "830"]
x = np.arange(len(keys)); w = 0.26
for i, (lab, vals) in enumerate(L19.items()):
    ax.bar(x + (i - 1) * w, [vals[k] for k in keys], w, label=lab,
           color=["#1f4e79", "#55a868", "#c44e52"][i])
ax.set_xticks(x); ax.set_xticklabels(keys)
ax.set_ylabel("% of records with that leader/19 value")
ax.grid(axis="y", alpha=.2)
ax.legend(fontsize=8, frameon=False, labelcolor=GREY)
ax.set_title("The three multipart values use different mechanisms\n"
             "K10plus and DNB books, the two catalogs that populate "
             "leader/19", color=GREY)
save(fig, "fig8-leader19-mechanisms.svg")

# --- Fig 9: AMI with bootstrap intervals ------------------------------
C = json.loads((HERE / "confidence.json").read_text())
LBL = {"server": "catalog", "agency": "040 $a agency",
       "desc_form": "leader/18 descriptive cataloging form",
       "rec_type": "leader/06 record type",
       "bib_level": "leader/07 bib level", "decade": "decade"}
fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), sharex=True)
for ax, (tag, title) in zip(axes, [
        ("all_fields", "All fields"),
        ("standard_only", "Local and administrative fields dropped")]):
    e = C["ami"][tag]["8"]
    items = sorted(e.items(), key=lambda kv: kv[1]["ami"])
    for i, (k, v) in enumerate(items):
        ax.plot([v["lo"], v["hi"]], [i, i], color="#4878a8", lw=2.4)
        ax.plot([v["ami"]], [i], "o", color="#1f4e79", ms=5)
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([LBL.get(k, k) for k, _ in items], fontsize=8)
    ax.set_xlim(0, 1); ax.grid(axis="x", alpha=.2)
    ax.set_title(title, fontsize=9, color=GREY)
    ax.set_xlabel("adjusted mutual information")
fig.suptitle("What the clusters correspond to, at k=8\n"
             "points are AMI, bars are 95% bootstrap intervals",
             color=GREY, y=1.10)
save(fig, "fig9-ami.svg")
