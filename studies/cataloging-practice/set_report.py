"""Filter the set survey and report how each catalog describes a work.

Three filters, each of which changed the numbers when it was added:

* A title query returns more than the work asked for, so a record's 245
  is matched against the work. The patterns are anchored at the start of
  the title, because a work name appearing mid-title usually belongs to
  a book *about* the work.
* Only leader/07 `m` records are counted. The unfiltered responses carry
  archival subunits, journal articles and analytic entries, none of
  which is an edition of the work.
* Publisher-supplied electronic records are counted separately. A run of
  per-tractate records that looked like library cataloguing turned out
  to be one vendor's e-book series.

Extent is classified rather than pattern-matched for a leading digit:
`v.` and `v. <1-27, 29-53>` are set-level extents and an earlier version
of this script missed both.
"""
import collections
import csv
import json
import pathlib
import re
import unicodedata

HERE = pathlib.Path("tmp/vagf")
CATALOGS = ("lc", "oxford", "nli", "dnb", "k10plus")

PATTERNS = {
    "Entsiklopedyah talmudit": r"^(entsi.?lopedyah talmudit|encyclopedia talmudica|אנציקלופדיה תלמודית)",
    "Die Mischna (Giessen)": r"^die mischna",
    "Talmud Bavli": r"^(talmud bavli|talmud babli|תלמוד בבלי)",
    "Miqraot Gedolot": r"^(mi.?ra.?ot gedolot|mikraot gedolot|מקראות גדולות)",
    "Mishnah Berurah": r"^(mishnah berurah|משנה ברורה)",
    "Shulhan Arukh": r"^(shul.?an .?arukh|schulchan aruch|שלחן ערוך|שולחן ערוך)",
    "Mishneh Torah": r"^(mishneh torah|משנה תורה)",
    "Talmud Yerushalmi": r"^(talmud yerushalmi|תלמוד ירושלמי)",
    "Midrash Rabbah": r"^(midrash rabbah|midrasch rabba|מדרש רבה)",
    "Zohar": r"^(sefer ha.?zohar|zohar|sohar|ספר הזהר|הזהר)",
    "Arukh ha-Shulhan": r"^(.?arukh ha.?shul.?an|ערוך השלחן)",
    "Encyclopaedia Judaica": r"^encyclopaedia judaica",
    "Torah Shelemah": r"^(torah shelemah|תורה שלמה)",
    "Schottenstein Talmud": r"schottenstein",
    "Ein Yaakov": r"^(.?en ya.?a.?ov|en jaakob|עין יעקב)",
    "Yalkut Shimoni": r"^(yal.?ut shim.?oni|jalkut schimoni|ילקוט שמעוני)",
    "Tosefta": r"^(tosefta|tosephta|תוספתא)",
    "Arbaah Turim": r"^(arba.?ah turim|arba.?a turim|ארבעה טורים)",
    "Otsar ha-Geonim": r"^(otsar ha.?ge.?onim|אוצר הגאונים)",
    # 'Sifre' alone matches ספרי ילדים (children's books) and ספרי
    # זכרונות (memory books), so the Hebrew form requires one of the
    # midrash's actual continuations.
    "Sifre": r"^(sifre|siphre)\b|^ספרי\s*(דבי|במדבר|דברים|זוטא|$)",
    "Or ha-Hayim": r"^(or ha.?.?ayim|אור החיים)",
    "Pesiqta Rabbati": r"^(pesi.?ta rabbati|pesikta rabbati|פסיקתא רבתי)",
}

COUNTED = re.compile(r"\b\d+\s*(v\.|vols?\b|volumes?\b|B(?:ä|ae)nde\b|Bde\b|"
                     r"כרכים)", re.I)
OPEN = re.compile(r"^\s*(v\.|vols?\b|volumes?\b|B(?:ä|ae)nde\b)|<\s*\d", re.I)


# Editions are commonly titled "Sefer X" / "ספר X" / "Ḥamishah ḥumshe
# X". Anchoring the work name at the very start of the title drops them:
# an earlier version of this script reported zero K10plus records for
# Ein Yaakov while the response held 23 coded ones titled "Sefer ʿEn
# Yaʿaḳov 5", and zero NLI records for Miqraot Gedolot. The anchor is
# kept, because a work name appearing mid-title usually belongs to a
# book about the work, but an edition prefix may precede it.
PREFIX = r"(?:(?:sefer|siddur|mahzor|hamishah|humshe|ha)\s+){0,3}"


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w\s֐-׿]", " ", s).strip()


def extent(a300):
    if "online resource" in a300.lower():
        return "online"
    if COUNTED.search(a300):
        return "counted"
    if OPEN.search(a300):
        return "open"
    return "single"


data = json.loads((HERE / "set_cases.json").read_text())
summary, dropped = {}, collections.Counter()

for work, cats in data.items():
    rx = re.compile("^" + PREFIX + PATTERNS[work].lstrip("^"))
    # The work name in $b identifies an edition whose title proper is
    # something else ("The Five Megilloth : miqraot gedolot"). Searched
    # unanchored, since $b is already the remainder of the title.
    rx_b = re.compile(PATTERNS[work].lstrip("^"))
    summary[work] = {}
    for c in CATALOGS:
        recs = cats.get(c, {}).get("records", [])
        named = [r for r in recs
                 if rx.search(norm(r["title"]))
                 or (r.get("title_b") and rx_b.search(norm(r["title_b"])))]
        dropped[f"{c}:title"] += len(recs) - len(named)
        mono = [r for r in named if r["l07"] == "m"]
        dropped[f"{c}:not-monograph"] += len(named) - len(mono)
        vendor = [r for r in mono if r.get("online")]
        lib = [r for r in mono if not r.get("online")]
        ext = collections.Counter(extent(r["a300"]) for r in lib)
        l19 = collections.Counter(r.get("l19_any", "") for r in lib)
        summary[work][c] = {
            "returned": len(recs), "named": len(named), "monograph": len(mono),
            "vendor_online": len(vendor), "library": len(lib),
            "l19_a": l19["a"], "l19_b": l19["b"], "l19_c": l19["c"],
            "l19_any": l19["a"] + l19["b"] + l19["c"],
            "t773": sum(1 for r in lib if r["t773"]),
            "np": sum(1 for r in lib if r["np"]),
            "t505": sum(1 for r in lib if r["t505"]),
            "extent_counted": ext["counted"], "extent_open": ext["open"],
            "set_level_extent": ext["counted"] + ext["open"],
            "truncated": int(len(recs) >= 50),
        }

CAP = sum(v[c]["truncated"] for v in summary.values() for c in CATALOGS)
print(f"records dropped by each filter: {dict(dropped)}")
print(f"cells that hit the fifty-record cap: {CAP} of "
      f"{len(summary) * len(CATALOGS)}\n")

print(f"{'catalog':9}{'lib recs':>9}{'l19 a':>7}{'l19 b':>7}{'l19 c':>7}"
      f"{'773':>6}{'n/p':>6}{'set ext':>9}{'505':>6}{'vendor':>8}")
tot = collections.Counter()
for c in CATALOGS:
    r = {k: sum(summary[w][c][k] for w in summary) for k in
         ("library", "l19_a", "l19_b", "l19_c", "t773", "np",
          "set_level_extent", "t505", "vendor_online")}
    print(f"{c:9}{r['library']:9}{r['l19_a']:7}{r['l19_b']:7}{r['l19_c']:7}"
          f"{r['t773']:6}{r['np']:6}{r['set_level_extent']:9}{r['t505']:6}"
          f"{r['vendor_online']:8}")
    tot[c] = r["library"]

anglo = sum(summary[w][c]["l19_any"] for w in summary
            for c in ("lc", "oxford", "nli"))
anglo_n = sum(tot[c] for c in ("lc", "oxford", "nli"))
print(f"\nleader/19 coded at LC + Oxford + NLI: {anglo} of {anglo_n} records")

(HERE / "set_summary.json").write_text(json.dumps(summary, indent=1))
out = pathlib.Path("docs/practice-study/data/set-survey.csv")
with out.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    cols = ["returned", "named", "monograph", "vendor_online", "library",
            "l19_a", "l19_b", "l19_c", "t773", "np", "t505",
            "extent_counted", "extent_open", "set_level_extent", "truncated"]
    w.writerow(["work", "catalog"] + cols)
    for work, cats in summary.items():
        for c in CATALOGS:
            w.writerow([work, c] + [cats[c][k] for k in cols])
print(f"wrote {out}")
