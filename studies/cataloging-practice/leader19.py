import collections, json, pathlib
import xml.etree.ElementTree as ET
M = "{http://www.loc.gov/MARC21/slim}"
rows = [json.loads(l) for l in pathlib.Path("tmp/vagf/corpus.jsonl").open(encoding="utf-8")]
SV = sorted({r["server"] for r in rows})
recs = []
for r in rows:
    try: rec = ET.fromstring(r["xml"])
    except ET.ParseError: continue
    ldr = rec.findtext(f"{M}leader") or ""
    if len(ldr) < 20: continue
    t = collections.Counter(); sub = collections.defaultdict(set)
    for df in rec.findall(f"{M}datafield"):
        t[df.get("tag")] += 1
        for s in df.findall(f"{M}subfield"): sub[df.get("tag")].add(s.get("code"))
    recs.append({"sv": r["server"], "l06": ldr[6], "l07": ldr[7],
                 "l19": ldr[19] if ldr[19].strip() else "#", "t": t, "sub": sub})
books = [x for x in recs if x["l06"] == "a"]

print("leader/19 on language material, by catalog")
print(f"{'catalog':10}{'n':>6}{'a Set':>8}{'b indep':>9}{'c dep':>8}{'populated':>11}")
for sv in SV:
    b = [x for x in books if x["sv"] == sv]
    c = collections.Counter(x["l19"] for x in b)
    pop = len(b) - c["#"] - c["-"]
    print(f"{sv:10}{len(b):6}{c['a']:8}{c['b']:9}{c['c']:8}"
          f"{pop:7} ({100*pop//max(len(b),1)}%)")

print("\nWhat leader/19=c records carry (the two catalogs that populate it)")
print(f"{'':10}{'n':>5}{'773':>7}{'830':>7}{'490':>7}{'245$n/$p':>10}{'800/810/811':>13}")
for sv in ("k10plus", "dnb"):
    for v in ("c", "b", "a", "#"):
        g = [x for x in books if x["sv"] == sv and x["l19"] == v]
        if len(g) < 5: continue
        def pc(fn): return f"{100*sum(1 for x in g if fn(x))//len(g)}%"
        print(f"{sv+'/'+v:10}{len(g):5}"
              f"{pc(lambda x: x['t']['773']>0):>7}"
              f"{pc(lambda x: x['t']['830']>0):>7}"
              f"{pc(lambda x: x['t']['490']>0):>7}"
              f"{pc(lambda x: bool(x['sub']['245'] & {'n','p'})):>10}"
              f"{pc(lambda x: any(x['t'][y] for y in ('800','810','811'))):>13}")

print("\nConverse: of books carrying 773, how many declare leader/19=c?")
for sv in SV:
    g = [x for x in books if x["sv"] == sv and x["t"]["773"] > 0]
    if not g: print(f"  {sv:10} no 773 records"); continue
    c = sum(1 for x in g if x["l19"] == "c")
    a07 = sum(1 for x in g if x["l07"] == "a")
    print(f"  {sv:10} {len(g):4} with 773: {c:4} are leader/19=c, "
          f"{a07:4} are leader/07=a component parts")

print("\n773 $g / $q (part designation) presence, books with 773")
for sv in SV:
    g = [x for x in books if x["sv"] == sv and x["t"]["773"] > 0]
    if not g: continue
    gg = sum(1 for x in g if "g" in x["sub"]["773"])
    ww = sum(1 for x in g if "w" in x["sub"]["773"])
    print(f"  {sv:10} n={len(g):4}  $g={100*gg//len(g)}%  $w={100*ww//len(g)}%")
