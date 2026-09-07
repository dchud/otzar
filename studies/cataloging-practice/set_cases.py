"""How each catalog describes a multi-volume Judaica set.

The matched items in the case chapter were found by ISBN, which finds
modern single-volume trade books. This asks the question the set work
actually cares about: take a work that is unambiguously a multi-volume
set, ask every catalog for it, and count what comes back.
"""
import collections
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sru_fetch import fetch, inspect, M

VOL = re.compile(r"\b(\d+)\s*(v\.|vols?\b|volumes?\b|B(?:ä|ae)nde\b|Bde\b|"
                 r"כרכים|כר׳)", re.I)

# One work per block, with the title as each catalog indexes it. NLI is
# asked in Hebrew because that is how it catalogues; the others are asked
# in romanized form.
WORKS = {
    "Entsiklopedyah talmudit": {
        "nli": 'alma.title="אנציקלופדיה תלמודית"',
        "oxford": 'alma.title="Entsiklopedyah talmudit"',
        "k10plus": 'pica.tit="Entsiklopedyah talmudit"',
        "lc": 'dc.title="Encyclopedia talmudica"',
        "dnb": "TIT=Entsiklopedyah",
    },
    "Die Mischna (Giessen)": {
        "nli": 'alma.title="Die Mischna"',
        "oxford": 'alma.title="Die Mischna"',
        "k10plus": 'pica.tit="Die Mischna"',
        "lc": 'dc.title="Die Mischna"',
        "dnb": "TIT=Mischna",
    },
    "Talmud Bavli": {
        "nli": 'alma.title="תלמוד בבלי"',
        "oxford": 'alma.title="Talmud Bavli"',
        "k10plus": 'pica.tit="Talmud Bavli"',
        "lc": 'dc.title="Talmud Bavli"',
        "dnb": "TIT=Talmud Bavli",
    },
    "Miqraot Gedolot": {
        "nli": 'alma.title="מקראות גדולות"',
        "oxford": 'alma.title="Miḳraʾot gedolot"',
        "k10plus": 'pica.tit="Mikraot gedolot"',
        "lc": 'dc.title="Mikraot gedolot"',
        "dnb": "TIT=Mikraot gedolot",
    },
    "Mishnah Berurah": {
        "nli": 'alma.title="משנה ברורה"',
        "oxford": 'alma.title="Mishnah berurah"',
        "k10plus": 'pica.tit="Mishnah berurah"',
        "lc": 'dc.title="Mishnah berurah"',
        "dnb": "TIT=Mishnah berurah",
    },
    "Shulhan Arukh": {
        "nli": 'alma.title="שלחן ערוך"',
        "oxford": 'alma.title="Shulhan arukh"',
        "k10plus": 'pica.tit="Shulhan arukh"',
        "lc": 'dc.title="Shulhan arukh"',
        "dnb": "TIT=Schulchan Aruch",
    },
    "Mishneh Torah": {
        "nli": 'alma.title="משנה תורה"',
        "oxford": 'alma.title="Mishneh Torah"',
        "k10plus": 'pica.tit="Mishneh Torah"',
        "lc": 'dc.title="Mishneh Torah"',
        "dnb": "TIT=Mishneh Torah",
    },
    "Talmud Yerushalmi": {
        "nli": 'alma.title="תלמוד ירושלמי"',
        "oxford": 'alma.title="Talmud Yerushalmi"',
        "k10plus": 'pica.tit="Talmud Yerushalmi"',
        "lc": 'dc.title="Talmud Yerushalmi"',
        "dnb": "TIT=Talmud Yerushalmi",
    },
    "Midrash Rabbah": {
        "nli": 'alma.title="מדרש רבה"',
        "oxford": 'alma.title="Midrash rabbah"',
        "k10plus": 'pica.tit="Midrasch Rabba"',
        "lc": 'dc.title="Midrash rabbah"',
        "dnb": "TIT=Midrasch Rabba",
    },
    "Zohar": {
        "nli": 'alma.title="ספר הזהר"',
        "oxford": 'alma.title="Sefer ha-Zohar"',
        "k10plus": 'pica.tit="Sefer ha-Zohar"',
        "lc": 'dc.title="Zohar"',
        "dnb": "TIT=Sohar",
    },
    "Arukh ha-Shulhan": {
        "nli": 'alma.title="ערוך השלחן"',
        "oxford": 'alma.title="Arukh ha-shulhan"',
        "k10plus": 'pica.tit="Arukh ha-shulhan"',
        "lc": 'dc.title="Arukh ha-shulhan"',
        "dnb": "TIT=Arukh ha-shulhan",
    },
    "Encyclopaedia Judaica": {
        "nli": 'alma.title="Encyclopaedia Judaica"',
        "oxford": 'alma.title="Encyclopaedia Judaica"',
        "k10plus": 'pica.tit="Encyclopaedia Judaica"',
        "lc": 'dc.title="Encyclopaedia Judaica"',
        "dnb": "TIT=Encyclopaedia Judaica",
    },
    "Torah Shelemah": {
        "nli": 'alma.title="תורה שלמה"',
        "oxford": 'alma.title="Torah shelemah"',
        "k10plus": 'pica.tit="Torah shelemah"',
        "lc": 'dc.title="Torah shelemah"',
        "dnb": "TIT=Torah shelemah",
    },
    "Schottenstein Talmud": {
        "nli": 'alma.title="Schottenstein"',
        "oxford": 'alma.title="Schottenstein"',
        "k10plus": 'pica.tit="Schottenstein"',
        "lc": 'dc.title="Schottenstein"',
        "dnb": "TIT=Schottenstein",
    },
    "Ein Yaakov": {
        "nli": 'alma.title="עין יעקב"',
        "oxford": 'alma.title="En Yaakov"',
        "k10plus": 'pica.tit="En Yaakov"',
        "lc": 'dc.title="En Yaakov"',
        "dnb": "TIT=En Yaakov",
    },
    "Yalkut Shimoni": {
        "nli": 'alma.title="ילקוט שמעוני"',
        "oxford": 'alma.title="Yalkut Shimoni"',
        "k10plus": 'pica.tit="Jalkut Schimoni"',
        "lc": 'dc.title="Yalkut Shimoni"',
        "dnb": "TIT=Jalkut Schimoni",
    },
    "Tosefta": {
        "nli": 'alma.title="תוספתא"',
        "oxford": 'alma.title="Tosefta"',
        "k10plus": 'pica.tit="Tosefta"',
        "lc": 'dc.title="Tosefta"',
        "dnb": "TIT=Tosefta",
    },
    "Arbaah Turim": {
        "nli": 'alma.title="ארבעה טורים"',
        "oxford": 'alma.title="Arbaah Turim"',
        "k10plus": 'pica.tit="Arbaah Turim"',
        "lc": 'dc.title="Arbaah Turim"',
        "dnb": "TIT=Arbaa Turim",
    },
    "Otsar ha-Geonim": {
        "nli": 'alma.title="אוצר הגאונים"',
        "oxford": 'alma.title="Otsar ha-geonim"',
        "k10plus": 'pica.tit="Otsar ha-geonim"',
        "lc": 'dc.title="Otsar ha-geonim"',
        "dnb": "TIT=Otsar ha-geonim",
    },
    "Sifre": {
        "nli": 'alma.title="ספרי"',
        "oxford": 'alma.title="Sifre"',
        "k10plus": 'pica.tit="Sifre"',
        "lc": 'dc.title="Sifre"',
        "dnb": "TIT=Sifre",
    },
    "Or ha-Hayim": {
        "nli": 'alma.title="אור החיים"',
        "oxford": 'alma.title="Or ha-hayim"',
        "k10plus": 'pica.tit="Or ha-hayim"',
        "lc": 'dc.title="Or ha-hayim"',
        "dnb": "TIT=Or ha-hayim",
    },
    "Pesiqta Rabbati": {
        "nli": 'alma.title="פסיקתא רבתי"',
        "oxford": 'alma.title="Pesiqta Rabbati"',
        "k10plus": 'pica.tit="Pesiqta Rabbati"',
        "lc": 'dc.title="Pesikta rabbati"',
        "dnb": "TIT=Pesiqta Rabbati",
    },
}


def describe(xml_text):
    """Structural summary of the records in one response."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    out = []
    for rec in root.findall(f".//{M}record"):
        ldr = rec.findtext(f"{M}leader") or ""
        tags = collections.Counter()
        s245, a300 = set(), ""
        title = ""
        for df in rec.findall(f"{M}datafield"):
            tag = df.get("tag")
            tags[tag] += 1
            subs = {s.get("code"): (s.text or "")
                    for s in df.findall(f"{M}subfield")}
            if tag == "245":
                s245 = set(subs)
                title = " ".join(subs.get(c, "") for c in ("a", "n", "p"))
            if tag == "300" and not a300:
                a300 = subs.get("a", "")
        out.append({
            "l07": ldr[7] if len(ldr) > 7 else "?",
            "l19": ldr[19] if len(ldr) > 19 and ldr[19].strip() else "-",
            "np": bool(s245 & {"n", "p"}),
            "t773": tags["773"] > 0,
            "t505": tags["505"] > 0,
            "volcount": bool(VOL.search(a300)),
            "a300": a300[:34],
            "title": title[:60],
        })
    return out


results = {}
for work, queries in WORKS.items():
    print(f"\n=== {work} ===")
    results[work] = {}
    for sv, q in queries.items():
        try:
            xml, cached = fetch(sv, q, max_records=50)
        except Exception as exc:
            print(f"  {sv:8} ERROR {type(exc).__name__}")
            continue
        got, total, diag = inspect(xml)
        recs = describe(xml) or []
        f = collections.Counter()
        for r in recs:
            if r["l19"] != "-":
                f[f"l19={r['l19']}"] += 1
            if r["np"]:
                f["245$n/$p"] += 1
            if r["t773"]:
                f["773"] += 1
            if r["volcount"]:
                f["300 vol-count"] += 1
            if r["t505"]:
                f["505"] += 1
        results[work][sv] = {"total": total, "returned": len(recs),
                             "flags": dict(f), "records": recs}
        print(f"  {sv:8} hits={str(total):>6}  returned={len(recs):>3}  "
              f"{dict(f) or '(no set markers)'}")

pathlib.Path("tmp/vagf/set_cases.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nwrote tmp/vagf/set_cases.json")
