"""Build the published data files for the study."""
import collections, csv, json, pathlib
import xml.etree.ElementTree as ET

HERE = pathlib.Path("tmp/vagf")
OUT = pathlib.Path("docs/practice-study/data")
M = "{http://www.loc.gov/MARC21/slim}"
ET.register_namespace("", "http://www.loc.gov/MARC21/slim")

rows = [json.loads(l) for l in (HERE/"corpus.jsonl").open(encoding="utf-8")]

MARKER_COLS = [
    ("has_773", lambda t, s, i: t["773"] > 0),
    ("has_490", lambda t, s, i: t["490"] > 0),
    ("has_490_traced", lambda t, s, i: i == "1"),
    ("has_830", lambda t, s, i: t["830"] > 0),
    ("has_800_810_811", lambda t, s, i: any(t[x] for x in ("800","810","811"))),
    ("has_440", lambda t, s, i: t["440"] > 0),
    ("has_245_n_or_p", lambda t, s, i: bool(s["245"] & {"n","p"})),
    ("has_246", lambda t, s, i: t["246"] > 0),
    ("has_505", lambda t, s, i: t["505"] > 0),
    ("has_505_t", lambda t, s, i: "t" in s["505"]),
    ("has_740", lambda t, s, i: t["740"] > 0),
    ("has_730", lambda t, s, i: t["730"] > 0),
    ("has_130_or_240", lambda t, s, i: t["130"] + t["240"] > 0),
    ("has_880", lambda t, s, i: t["880"] > 0),
    ("has_020", lambda t, s, i: t["020"] > 0),
    ("has_300_c", lambda t, s, i: "c" in s["300"]),
]
HEAD = (["record_id","catalog","control_number","control_number_identifier",
         "ldr06_record_type","ldr07_bib_level","ldr17_encoding_level",
         "ldr18_description_form","ldr19_multipart_level",
         "agency_040a","cataloging_lang_040b",
         "convention_040e","date_type_008","year1_008","year2_008",
         "place_008","lang_008","draw_axis","draw_domain","draw_year",
         "query"] + [c for c, _ in MARKER_COLS] + ["datafield_tags"])

def cell(x): return "" if x is None else x

n_written = 0
with (OUT/"corpus-features.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(HEAD)
    for r in rows:
        try: rec = ET.fromstring(r["xml"])
        except ET.ParseError: continue
        leader = rec.findtext(f"{M}leader") or ""
        cf = {c.get("tag"): (c.text or "") for c in rec.findall(f"{M}controlfield")}
        t, s = collections.Counter(), collections.defaultdict(set)
        ind490, f040 = None, {}
        tags = []
        for df in rec.findall(f"{M}datafield"):
            tag = df.get("tag"); t[tag] += 1; tags.append(tag)
            for sf in df.findall(f"{M}subfield"): s[tag].add(sf.get("code"))
            if tag == "490" and ind490 is None: ind490 = df.get("ind1")
            if tag == "040" and not f040:
                f040 = {sf.get("code"): (sf.text or "").strip()
                        for sf in df.findall(f"{M}subfield")}
        f8 = cf.get("008", "")
        def L(i): return leader[i] if len(leader) > i else ""
        def F(a, b): return f8[a:b] if len(f8) >= b else ""
        w.writerow([r["id"], r["server"], cf.get("001",""), cf.get("003",""),
                    L(6), L(7), L(17), L(18),
                    (L(19) if L(19).strip() else ''),
                    f040.get("a",""), f040.get("b",""), f040.get("e","").lower(),
                    F(6,7), F(7,11), F(11,15), F(15,18).strip(), F(35,38),
                    r.get("axis",""), r.get("domain",""), cell(r.get("year")),
                    r["query"]]
                   + [int(fn(t, s, ind490)) for _, fn in MARKER_COLS]
                   + [" ".join(sorted(set(tags)))])
        n_written += 1
print(f"corpus-features.csv: {n_written} rows, "
      f"{(OUT/'corpus-features.csv').stat().st_size/1024:.0f} KB")

# ---- query manifest ----
byq = collections.defaultdict(int)
meta = {}
for r in rows:
    k = (r["server"], r["query"])
    byq[k] += 1
    meta.setdefault(k, r)
with (OUT/"queries.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["catalog","query","draw_axis","draw_domain","draw_year",
                "records_first_seen_here"])
    for (sv, q), n in sorted(byq.items()):
        m = meta[(sv, q)]
        w.writerow([sv, q, m.get("axis",""), m.get("domain",""),
                    cell(m.get("year")), n])
print(f"queries.csv: {len(byq)} queries, "
      f"{(OUT/'queries.csv').stat().st_size/1024:.0f} KB")
