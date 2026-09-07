"""Same item, every catalog that holds it, field by field."""
import pathlib, sys
import xml.etree.ElementTree as ET
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sru_fetch import fetch, inspect, M

CASES = [
    ("9789176370582", "Yoshe kalb (Yiddish novel, Swedish imprint)"),
    ("9789655404487", "100 sipurim Erets-Yisreelim (Hebrew anthology)"),
    ("9789657012017", "41 Muzik-Lider (notated music)"),
    ("9783643120649", "Hiob: eine biblische Tragoedie (German monograph)"),
    ("9789654938044", "Tse tame: gerush ruhot (Hebrew monograph)"),
    ("9783835352599", "Ausgestopfte Juden? (German monograph)"),
]
QF = {"nli": "alma.isbn={}", "oxford": "alma.isbn={}", "lc": "bath.isbn={}",
      "dnb": "NUM={}", "k10plus": "pica.isb={}"}
SHOW = ["001", "003", "020", "040", "041", "100", "110", "130", "240",
        "245", "246", "250", "260", "264", "300", "490", "505", "700",
        "730", "740", "773", "830", "880"]

out = []
for isbn, label in CASES:
    out.append("=" * 74)
    out.append(f"{label}\nISBN {isbn}")
    for server, form in QF.items():
        try:
            xml, _ = fetch(server, form.format(isbn), max_records=3)
        except Exception as exc:
            out.append(f"\n-- {server}: fetch error {type(exc).__name__}")
            continue
        n, total, diag = inspect(xml)
        if not n:
            out.append(f"\n-- {server}: not held (total={total})")
            continue
        rec = ET.fromstring(xml).find(f".//{M}record")
        leader = rec.findtext(f"{M}leader") or ""
        cf = {c.get("tag"): (c.text or "") for c in
              rec.findall(f"{M}controlfield")}
        out.append(f"\n-- {server}")
        out.append(f"   LEADER {leader}")
        out.append(f"     06={leader[6]} 07={leader[7]} 17={leader[17]} "
                   f"18={leader[18]}")
        out.append(f"   001 {cf.get('001','-')}   003 {cf.get('003','-')}")
        out.append(f"   008 {cf.get('008','-')[:40]}")
        alltags = []
        for df in rec.findall(f"{M}datafield"):
            t = df.get("tag")
            alltags.append(t)
            if t not in SHOW:
                continue
            subs = " ".join(f"${s.get('code')}{(s.text or '').strip()}"
                            for s in df.findall(f"{M}subfield"))
            out.append(f"   {t} {df.get('ind1') or '#'}{df.get('ind2') or '#'} "
                       f"{subs[:150]}")
        out.append(f"   [tags: {' '.join(sorted(set(alltags)))}]")
    out.append("")

p = pathlib.Path("tmp/vagf/cases.txt")
p.write_text("\n".join(out), encoding="utf-8")
print(f"wrote {p} ({len(out)} lines)")
