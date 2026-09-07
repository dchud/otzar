"""Filter the set survey to records that actually name the work, and
report how each catalog describes it.

A title query returns more than the work asked for. Counting raw hits
would overstate every figure, so each record's 245 is matched against
the work before it is counted.
"""
import collections
import json
import pathlib
import re
import unicodedata

HERE = pathlib.Path("tmp/vagf")
CATALOGS = ("lc", "oxford", "nli", "dnb", "k10plus")

PATTERNS = {
    "Entsiklopedyah talmudit": r"(entsi.?lopedyah talmudit|encyclopedia talmudica|אנציקלופדיה תלמודית)",
    "Die Mischna (Giessen)": r"die mischna",
    "Talmud Bavli": r"(talmud bavli|talmud babli|תלמוד בבלי)",
    "Miqraot Gedolot": r"(mi.?ra.?ot gedolot|mikraot gedolot|מקראות גדולות)",
    "Mishnah Berurah": r"(mishnah berurah|mishnah berurah|משנה ברורה)",
    "Shulhan Arukh": r"(shul.?an .?arukh|schulchan aruch|שלחן ערוך|שולחן ערוך)",
    "Mishneh Torah": r"(mishneh torah|משנה תורה)",
    "Talmud Yerushalmi": r"(talmud yerushalmi|תלמוד ירושלמי)",
    "Midrash Rabbah": r"(midrash rabbah|midrasch rabba|מדרש רבה)",
    "Zohar": r"(zohar|sohar|זהר|הזהר)",
    "Arukh ha-Shulhan": r"(.?arukh ha.?shul.?an|ערוך השלחן)",
    "Encyclopaedia Judaica": r"encyclopaedia judaica",
    "Torah Shelemah": r"(torah shelemah|תורה שלמה)",
    "Schottenstein Talmud": r"schottenstein",
    "Ein Yaakov": r"(.?en ya.?a.?ov|en jaakob|עין יעקב)",
    "Yalkut Shimoni": r"(yal.?ut shim.?oni|jalkut schimoni|ילקוט שמעוני)",
    "Tosefta": r"(tosefta|tosephta|תוספתא)",
    "Arbaah Turim": r"(arba.?ah turim|arba.?a turim|ארבעה טורים)",
    "Otsar ha-Geonim": r"(otsar ha.?ge.?onim|אוצר הגאונים)",
    "Sifre": r"(sifre|siphre|ספרי)",
    "Or ha-Hayim": r"(or ha.?.?ayim|אור החיים)",
    "Pesiqta Rabbati": r"(pesi.?ta rabbati|pesikta rabbati|פסיקתא רבתי)",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w\s֐-׿]", " ", s)


data = json.loads((HERE / "set_cases.json").read_text())
summary = {}

print(f"{'work':26}" + "".join(f"{c.upper()[:7]:>16}" for c in CATALOGS))
print(f"{'':26}" + "".join(f"{'n  l19c  np/505':>16}" for c in CATALOGS))
for work, cats in data.items():
    rx = re.compile(PATTERNS.get(work, re.escape(work.lower())))
    row, held = "", 0
    summary[work] = {}
    for c in CATALOGS:
        recs = cats.get(c, {}).get("records", [])
        hit = [r for r in recs if rx.search(norm(r["title"]))]
        if hit:
            held += 1
        l19c = sum(1 for r in hit if r["l19"] == "c")
        l19b = sum(1 for r in hit if r["l19"] == "b")
        np = sum(1 for r in hit if r["np"])
        vol = sum(1 for r in hit if r["volcount"])
        t505 = sum(1 for r in hit if r["t505"])
        t773 = sum(1 for r in hit if r["t773"])
        summary[work][c] = {"n": len(hit), "l19c": l19c, "l19b": l19b,
                            "np": np, "vol": vol, "t505": t505,
                            "t773": t773,
                            "truncated": len(recs) >= 50}
        row += f"{len(hit):5}{l19c:6}{np:4}/{t505:<3}"
    print(f"{work:26}{row}   [{held} catalogs]")

print("\nWorks held by at least three catalogs, "
      "with a per-volume/set-level contrast:")
for work, cats in summary.items():
    held = [c for c in CATALOGS if cats[c]["n"]]
    if len(held) < 3:
        continue
    declared = [c for c in held if cats[c]["l19c"] > 0]
    setlevel = [c for c in held if cats[c]["vol"] > 0 and cats[c]["l19c"] == 0]
    enumerated = [c for c in held
                  if cats[c]["np"] > 0 and cats[c]["l19c"] == 0]
    if declared and (setlevel or enumerated):
        print(f"  {work}")
        print(f"    declared per-volume (leader/19=c): "
              f"{', '.join(f'{c}={cats[c]['l19c']}' for c in declared)}")
        if setlevel:
            print(f"    set-level (300 volume count):     "
                  f"{', '.join(f'{c}={cats[c]['vol']}' for c in setlevel)}")
        if enumerated:
            print(f"    enumerated in 245 only:           "
                  f"{', '.join(f'{c}={cats[c]['np']}' for c in enumerated)}")

(HERE / "set_summary.json").write_text(json.dumps(summary, indent=1))

# The published table: one row per work and catalog.
import csv
out = pathlib.Path("docs/practice-study/data/set-survey.csv")
with out.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["work", "catalog", "records_naming_work", "leader19_b",
                "leader19_c", "has_773", "has_245_n_or_p",
                "has_300_volume_count", "has_505", "response_truncated"])
    for work, cats in summary.items():
        for c in CATALOGS:
            v = cats[c]
            w.writerow([work, c, v["n"], v["l19b"], v["l19c"], v["t773"],
                        v["np"], v["vol"], v["t505"],
                        int(bool(v["truncated"]))])
print(f"\nwrote tmp/vagf/set_summary.json and {out}")
