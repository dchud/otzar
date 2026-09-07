import json, pathlib
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = pathlib.Path(__file__).parent
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
