"""Every number the writeup and the figures use, computed once."""
import collections, json, math, pathlib
import xml.etree.ElementTree as ET
import numpy as np
from scipy.stats import chi2_contingency
HERE = pathlib.Path(__file__).parent
M = "{http://www.loc.gov/MARC21/slim}"

def wilson(k, n, z=1.959964):
    if n == 0: return (0.0, 0.0)
    p = k/n; d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    s = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return (max(0., c-s), min(1., c+s))

def marks_of(t, s, leader, ind490=None):
    b = leader[7] if len(leader) > 7 else "?"
    return {
        "leader/07=d subunit": b == "d", "leader/07=a analytic": b == "a",
        "773 host item": t["773"] > 0, "490 series stmt": t["490"] > 0,
        "830 series entry": t["830"] > 0,
        "800/810/811": any(t[x] for x in ("800", "810", "811")),
        "440 obsolete": t["440"] > 0,
        "245$n/$p": bool(s["245"] & {"n", "p"}),
        "246 variant": t["246"] > 0, "505 contents": t["505"] > 0,
        "740 added title": t["740"] > 0, "730 uniform added": t["730"] > 0,
        "130/240 uniform": t["130"] + t["240"] > 0,
        "880 linked script": t["880"] > 0, "020 ISBN": t["020"] > 0,
        "300$c dimensions": "c" in s["300"],
        "490 ind1=1 traced": ind490 == "1"}

REC_TYPES = {"a": "language material", "c": "notated music",
             "g": "projected image", "i": "nonmusical sound",
             "j": "musical sound", "k": "two-dimensional image",
             "p": "mixed material", "t": "manuscript"}
allrows = []
for line in (HERE/"corpus.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    try: rec = ET.fromstring(r["xml"])
    except ET.ParseError: continue
    leader = rec.findtext(f"{M}leader") or ""
    t, s = collections.Counter(), collections.defaultdict(set)
    ind490 = None
    for df in rec.findall(f"{M}datafield"):
        t[df.get("tag")] += 1
        for sf in df.findall(f"{M}subfield"): s[df.get("tag")].add(sf.get("code"))
        if df.get("tag") == "490" and ind490 is None: ind490 = df.get("ind1")
    f008 = next((c.text or "" for c in rec.findall(f"{M}controlfield")
                 if c.get("tag") == "008"), "")
    d1 = f008[7:11] if len(f008) >= 11 else ""
    allrows.append({"server": r["server"],
                    "rec_type": leader[6] if len(leader) > 6 else "?",
                    "y": int(d1) if d1.isdigit() and 1400 <= int(d1) <= 2026 else None,
                    "m": marks_of(t, s, leader, ind490)})

MARKS = list(allrows[0]["m"])
SERVERS = sorted({r["server"] for r in allrows})
books = [r for r in allrows if r["rec_type"] == "a"]
BINS = [(1500,1940,"pre-1940"), (1940,1970,"1940-69"), (1970,1990,"1970-89"),
        (1990,2005,"1990-2004"), (2005,2026,"2005-25")]
BL = [b[2] for b in BINS]

def tab(subset, groups, keyfn):
    out = {}
    for m in MARKS:
        cells = {}
        for g in groups:
            sub = [r for r in subset if keyfn(r) == g]
            k = sum(1 for r in sub if r["m"][m])
            lo, hi = wilson(k, len(sub))
            cells[g] = {"k": k, "n": len(sub),
                        "p": k/len(sub) if sub else None, "lo": lo, "hi": hi}
        arr = np.array([[cells[g]["k"] for g in groups],
                        [cells[g]["n"]-cells[g]["k"] for g in groups]])
        if arr[0].sum() and arr[1].sum():
            chi2, pv, _, _ = chi2_contingency(arr)
            v = math.sqrt(chi2/arr.sum())
        else: v, pv = None, None
        out[m] = {"cells": cells, "cramer_v": v, "p": pv}
    return out

mats = [k for k, c in collections.Counter(
    r["rec_type"] for r in allrows).most_common() if c >= 25]
data = {
    "marks": MARKS, "servers": SERVERS, "bin_labels": BL,
    "n_all": len(allrows), "n_books": len(books),
    "per_server_all": {s: sum(1 for r in allrows if r["server"] == s)
                       for s in SERVERS},
    "per_server_books": {s: sum(1 for r in books if r["server"] == s)
                         for s in SERVERS},
    "rec_types": {k: REC_TYPES.get(k, k) for k in mats},
    "books_by_cat": tab(books, SERVERS, lambda r: r["server"]),
    "all_by_mat": tab(allrows, mats, lambda r: r["rec_type"]),
    "books_by_epoch": tab(
        [r for r in books if r["y"]], BL,
        lambda r: next(lb for a, b, lb in BINS if a <= r["y"] < b)),
}
data["books_by_epoch_cat"] = {
    m: {sv: {lb: None for lb in BL} for sv in SERVERS} for m in MARKS}
for m in MARKS:
    for sv in SERVERS:
        for a, b, lb in BINS:
            sub = [r for r in books if r["server"] == sv and r["y"]
                   and a <= r["y"] < b]
            data["books_by_epoch_cat"][m][sv][lb] = {
                "n": len(sub),
                "p": (sum(1 for r in sub if r["m"][m])/len(sub)) if sub else None}
json.dump(data, (HERE/"final_stats.json").open("w"), indent=1)
print(f"all={len(allrows)} books={len(books)}")
print("books per catalog:", data["per_server_books"])
print("books per epoch:", {lb: data["books_by_epoch"][MARKS[0]]["cells"][lb]["n"]
                           for lb in BL})
