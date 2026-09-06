"""VIAF SRU responses shaped like the live service's, for tests.

The clusters are cut down from what VIAF returns for the founder of
Chabad and for the people who share his name, keeping the parts the
parser reads and the shapes that matter: a heading per contributing
file, tracings with their own sources, the tags and subfield codes VIAF
emits, and the junk that arrives with them.
"""

from unittest.mock import MagicMock
from xml.sax.saxutils import escape

SRW = "http://www.loc.gov/zing/srw/"
VIAF = "http://viaf.org/viaf/terms#"


def _sources(codes):
    return "".join(f"<ns2:s>{escape(code)}</ns2:s>" for code in codes)


def x400(subfields, sources, tag="400"):
    """One tracing. ``subfields`` is a list of (code, text) pairs."""
    fields = "".join(
        f'<ns2:subfield code="{code}">{escape(text)}</ns2:subfield>'
        for code, text in subfields
    )
    normalized = escape(" ".join(text for _, text in subfields).lower())
    return (
        "<ns2:x400>"
        f'<ns2:datafield dtype="MARC21" ind1="1" ind2=" " tag="{tag}">'
        f"{fields}<ns2:normalized>{normalized}</ns2:normalized>"
        "</ns2:datafield>"
        f"<ns2:sources>{_sources(sources)}</ns2:sources>"
        "</ns2:x400>"
    )


def cluster(viaf_id, headings, source_ids, x400s=()):
    """A VIAFCluster element.

    ``headings`` is a list of (text, sources) pairs, ``source_ids`` a
    dict of file code to that file's identifier, ``x400s`` a list of
    strings from :func:`x400`.
    """
    heads = "".join(
        f"<ns2:data><ns2:text>{escape(text)}</ns2:text>"
        f"<ns2:sources>{_sources(sources)}</ns2:sources></ns2:data>"
        for text, sources in headings
    )
    ids = "".join(
        f"<ns2:source>{escape(code)}|{escape(value)}</ns2:source>"
        for code, value in source_ids.items()
    )
    return (
        f'<ns2:VIAFCluster xmlns:ns2="{VIAF}">'
        f"<ns2:viafID>{viaf_id}</ns2:viafID>"
        "<ns2:nameType>Personal</ns2:nameType>"
        f"<ns2:sources>{ids}</ns2:sources>"
        f"<ns2:mainHeadings>{heads}</ns2:mainHeadings>"
        f"<ns2:x400s>{''.join(x400s)}</ns2:x400s>"
        "</ns2:VIAFCluster>"
    )


def response(clusters, total=None):
    """An SRU response carrying *clusters*.

    ``total`` is the hit count VIAF reports, which can exceed what it
    returns; it defaults to the number of clusters.
    """
    if total is None:
        total = len(clusters)
    records = "".join(
        "<record><recordSchema>VIAF</recordSchema>"
        f"<recordData>{item}</recordData></record>"
        for item in clusters
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<searchRetrieveResponse xmlns="{SRW}"><version>1.1</version>'
        f"<numberOfRecords>{total}</numberOfRecords>"
        f"<records>{records}</records></searchRetrieveResponse>"
    )


EMPTY = response([])


# The founder of Chabad, as LC and NLI file him and as fifteen other
# files do. The tracings show every shape the parser has to cope with:
# LC's Hebrew see-froms, a Cyrillic one from NLI, a scientific
# transliteration, BNF's non-sorting control characters and $5 code,
# a broken tracing that is nothing but punctuation, a corporate 410,
# a BNF 700, and a name/title tracing with a $t.
SHNEUR_ZALMAN_ID = "71634419"
SHNEUR_ZALMAN = cluster(
    SHNEUR_ZALMAN_ID,
    headings=[
        ("Shneur Zalman, of Lyady, 1745-1812", ["J9U", "LC"]),
        ("שניאור זלמן בן ברוך, 1745-1812", ["J9U", "LIH"]),
        ("Шнеур Залман Бен Барух, 1745-1812", ["J9U"]),
        ("Shneur Zalman 1745-1813 of Lyady", ["ISNI"]),
        ("Shneur Zalman, of Lyady, 1745-1813", ["NLA", "NTA"]),
        ("שניאור זלמן", ["WKP"]),
        ("Schneur Salman von Ljadi 1745-1812", ["DNB"]),
    ],
    source_ids={
        "LC": "n  81144085",
        "J9U": "987007268012305171",
        "DNB": "118944134",
        "ISNI": "0000000092900110",
        "WKP": "Q547033",
    },
    x400s=[
        x400([("a", "שניאור זלמן מלאדי.")], ["LC"]),
        x400([("a", "אדמוה״ז,"), ("d", "1745-1812")], ["LC"]),
        x400([("a", 'אדמו"ר הזקן')], ["ISNI", "J9U"]),
        x400([("a", "Baʻal ha-Tanya,"), ("d", "1745-1812")], ["LC"]),
        x400([("a", "Шнеур Залман")], ["J9U"]),
        x400([("a", "Šneyʾwr Zalman, Milyaʾdiy")], ["ISNI"]),
        x400(
            [("5", "e"), ("a", "\x98ה\x9cעילוי"), ("f", "1745-1813")],
            ["BNF"],
        ),
        x400([("a", "+.")], ["LC"]),
        x400([("a", "Ḥabad")], ["LC"], tag="410"),
        x400(
            [("a", "Šneyʾwr Zalman"), ("f", "1745-1813")], ["BNF"], tag="700"
        ),
        x400(
            [
                ("a", "Shneur Zalman, of Lyady,"),
                ("d", "1745-1812."),
                ("t", "Tanya"),
            ],
            ["LC"],
        ),
    ],
)

# The same person as the Portuguese national library alone files him:
# a cluster VIAF has not folded into the one above, whose tracing is
# LC's heading word for word.
PTBNP_SPLIT_ID = "47159939586225252469"
PTBNP_SPLIT = cluster(
    PTBNP_SPLIT_ID,
    headings=[("Chnéour Zalman, 1745-1813 de Lyadi", ["PTBNP"])],
    source_ids={"PTBNP": "1788306"},
    x400s=[
        x400([("a", "Shneur Zalman of Lyady‏")], ["PTBNP"]),
        x400([("a", "Shneur Zalman de Lyadi‏")], ["PTBNP"]),
    ],
)

# A different Shneur Zalman of Lyady, born eighty-five years later.
FRADKIN_ID = "160366599"
FRADKIN = cluster(
    FRADKIN_ID,
    headings=[
        ("Shneʾur Zalman ben Shelomoh, mi-Ladi, 1830-1902", ["LC", "J9U"]),
        ("פרדקין, שניאור זלמן בן שלמה, 1830-1902", ["J9U"]),
    ],
    source_ids={"LC": "n  85158455", "J9U": "987007266853505171"},
    x400s=[
        x400([("a", "לדיר, שניאור זלמן,"), ("d", "1830-1902")], ["J9U"]),
        x400([("a", "Gaon mi-Lublin,"), ("d", "1830-1902")], ["LC"]),
    ],
)

# The founder's daughter. Her heading holds every word of his.
FREIDA_ID = "4169628484782861008"
FREIDA = cluster(
    FREIDA_ID,
    headings=[("פריידא בת שניאור זלמן בן ברוך", ["J9U"])],
    source_ids={"J9U": "987007404587605171"},
    x400s=[
        x400(
            [("a", "פרידא בת שניאור זלמן בן ברוך,"), ("c", "מלאדי")],
            ["J9U"],
        ),
    ],
)

# The founder's son and successor.
DOV_BER_ID = "45222208"
DOV_BER = cluster(
    DOV_BER_ID,
    headings=[
        ("Schneersohn, Dov Baer, 1773-1827", ["LC", "J9U"]),
        ("שניאורסון, דב בר בן שניאור זלמן, 1773-1827", ["J9U"]),
    ],
    source_ids={"LC": "n  80123359", "J9U": "987007267782505171"},
    x400s=[
        x400([("a", "Admor ha-emtsaʻi,"), ("d", "1773-1827")], ["LC"]),
    ],
)

# Three of the several hundred clusters a common name returns.
COHEN_1949_ID = "9620160668312903560002"
COHEN_1949 = cluster(
    COHEN_1949_ID,
    headings=[
        ("Cohen, David, 1949-", ["LC", "J9U"]),
        ("כהן, דיויד, 1949-", ["J9U"]),
    ],
    source_ids={"LC": "n  79093223", "J9U": "987007260009505171"},
    x400s=[x400([("a", "כהן, דוד,"), ("d", "1946-")], ["J9U"])],
)
COHEN_PLAIN_ID = "8239178467199235190006"
COHEN_PLAIN = cluster(
    COHEN_PLAIN_ID,
    headings=[("Cohen, David", ["NUKAT"])],
    source_ids={"NUKAT": "n 2004077340"},
)
COHEN_1955_ID = "7465169262307609510008"
COHEN_1955 = cluster(
    COHEN_1955_ID,
    headings=[("Cohen, David, 1955 December 15-", ["LC"])],
    source_ids={"LC": "no2011053641"},
)

# A heading only the German national library established.
HESCHEL_DNB_ID = "27071894"
HESCHEL_DNB = cluster(
    HESCHEL_DNB_ID,
    headings=[("Heschel, Abraham Joshua, 1907-1972", ["DNB"])],
    source_ids={"DNB": "118550098"},
)


class FakeVIAF:
    """Stands in for ``httpx.get`` and ``time.sleep`` in the VIAF client.

    Responses are served in the order queued; an exception in the queue
    is raised in place of a response. A request with nothing queued
    fails the test: nothing here may reach the network, and a query the
    test did not expect is a bug in the test or in the cascade. Sleeps
    are recorded instead of taken.
    """

    def __init__(self):
        self.queue = []
        self.urls = []
        self.sleeps = []

    def answer(self, *responses):
        self.queue.extend(responses)

    def get(self, url, **kwargs):
        self.urls.append(url)
        if not self.queue:
            raise AssertionError(f"unexpected VIAF request: {url}")
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        resp = MagicMock()
        resp.text = item
        resp.raise_for_status = MagicMock()
        return resp

    def install(self, monkeypatch):
        monkeypatch.setattr("sources.viaf.httpx.get", self.get)
        monkeypatch.setattr("sources.viaf.time.sleep", self.sleeps.append)
        return self
