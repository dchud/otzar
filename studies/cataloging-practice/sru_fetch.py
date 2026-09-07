"""Paced SRU fetcher for the cataloging-practice clustering study.

Disk-cached under tmp/vagf/cache so a re-run costs no requests, and
paced per host so no server sees two requests inside MIN_GAP seconds.
"""

import hashlib
import pathlib
import time
import urllib.parse
import xml.etree.ElementTree as ET

import httpx

MIN_GAP = 4.0
CACHE = pathlib.Path(__file__).parent / "cache"
CACHE.mkdir(exist_ok=True)

SERVERS = {
    "nli": ("https://nli.alma.exlibrisgroup.com/view/sru/972NNL_INST",
            "1.2", "marcxml"),
    "lc": ("http://lx2.loc.gov:210/LCDB", "1.1", "marcxml"),
    "dnb": ("https://services.dnb.de/sru/dnb", "1.1", "MARC21-xml"),
    "k10plus": ("https://sru.k10plus.de/opac-de-627", "1.1", "marcxml"),
    "oxford": ("https://oxford.alma.exlibrisgroup.com/view/sru/44OXF_INST",
               "1.2", "marcxml"),
}

M = "{http://www.loc.gov/MARC21/slim}"
_last_hit: dict[str, float] = {}


def fetch(server, query, max_records=50, start_record=1):
    """Return (xml_text, from_cache). Raises on transport failure."""
    base, version, schema = SERVERS[server]
    params = {
        "operation": "searchRetrieve",
        "version": version,
        "query": query,
        "maximumRecords": str(max_records),
        "recordSchema": schema,
    }
    if start_record != 1:
        params["startRecord"] = str(start_record)
    key = hashlib.sha256(
        (base + urllib.parse.urlencode(sorted(params.items()))).encode()
    ).hexdigest()[:24]
    path = CACHE / f"{server}-{key}.xml"
    if path.exists():
        return path.read_text(encoding="utf-8"), True

    host = urllib.parse.urlsplit(base).hostname
    gap = time.monotonic() - _last_hit.get(host, -MIN_GAP)
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    _last_hit[host] = time.monotonic()

    resp = httpx.get(base, params=params, timeout=60)
    resp.raise_for_status()
    text = resp.text
    if not text.strip().startswith("<"):
        raise ValueError(f"{server}: response is not XML")
    path.write_text(text, encoding="utf-8")
    return text, False


def inspect(xml_text):
    """Return (n_records_in_response, numberOfRecords, diagnostic_or_None)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return 0, None, f"parse error: {exc}"
    recs = root.findall(f".//{M}record")
    total = None
    diag = None
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "numberOfRecords" and el.text and el.text.strip().isdigit():
            total = int(el.text.strip())
        if tag in ("message", "diagnostic") and el.text and el.text.strip():
            diag = (diag or "") + el.text.strip()[:120]
    return len(recs), total, diag
