"""English names for the ISO 639 language codes stored on records.

The code is the interchange value and is what gets stored: it round-trips
against ``source_marc`` and stays correct when the name for a language
changes. The name is derived for display only.

MARC 008/35-37 carries ISO 639-2/**B** bibliographic codes, so a German
record says ``ger``, not ``deu``. pycountry indexes ISO 639-3, where the
bibliographic forms exist only as an alias on the 639-3 entry --
``languages.get(alpha_3="ger")`` is ``None`` and only
``languages.get(bibliographic="ger")`` finds German. Twenty languages
diverge that way, so an alpha_3 lookup on its own renders every one of
them blank. The two indexes are disjoint -- no bibliographic code is
also somebody's alpha_3 -- so both have to be consulted, in either
order.
"""

import re

import pycountry

# Language codes withdrawn from MARC, mapped to their replacements.
# Records catalogued before a withdrawal still carry the old code, and
# ISO 639-3 has since handed most of these codes to unrelated languages
# -- `gae` meant Scottish Gaelic in MARC and means Guarequena in 639-3 --
# so the redirect has to run before pycountry sees the code.
WITHDRAWN_CODES = {
    "cam": "khm",  # Khmer
    "esp": "epo",  # Esperanto
    "eth": "gez",  # Ethiopic
    "far": "fao",  # Faroese
    "fri": "fry",  # Frisian
    "gae": "gla",  # Scottish Gaelic
    "gag": "glg",  # Galician
    "gal": "orm",  # Oromo
    "gua": "grn",  # Guarani
    "int": "ina",  # Interlingua
    "iri": "gle",  # Irish
    "kus": "kos",  # Kusaie
    "lan": "oci",  # Occitan
    "lap": "smi",  # Sami
    "max": "glv",  # Manx
    "mla": "mlg",  # Malagasy
    "mol": "ron",  # Moldavian
    "sao": "smo",  # Samoan
    "scc": "srp",  # Serbian
    "scr": "hrv",  # Croatian
    "sho": "sna",  # Shona
    "snh": "sin",  # Sinhalese
    "sso": "sot",  # Sotho
    "swz": "ssw",  # Swazi
    "tag": "tgl",  # Tagalog
    "taj": "tgk",  # Tajik
    "tar": "tat",  # Tatar
    "tsw": "tsn",  # Tswana
}

# ISO 639-3 names that read as scholarly apparatus on a catalog page.
# Keyed by the alpha_3 the code resolves to, so both halves of a
# bibliographic/terminology pair get the same answer.
NAME_OVERRIDES = {
    "arc": "Aramaic",  # Official Aramaic (700-300 BCE)
    "ell": "Greek",  # Modern Greek (1453-)
}

# ISO 639-3 marks macrolanguages in the name; ISO 639-2 and MARC do not.
_MACROLANGUAGE = re.compile(r"\s*\(macrolanguage\)$")


def language_name(code):
    """Return the English name of the language *code* identifies.

    Accepts ISO 639-2/B, ISO 639-2/T, ISO 639-3 and the ISO 639-5
    collective codes, in any case and with surrounding whitespace. A code
    with no match comes back trimmed but otherwise unchanged, so an
    unrecognized value still tells a cataloger what the record holds.
    """
    if not code:
        return ""
    text = str(code).strip()
    if not text:
        return ""

    key = text.lower()
    key = WITHDRAWN_CODES.get(key, key)

    language = pycountry.languages.get(
        bibliographic=key
    ) or pycountry.languages.get(alpha_3=key)
    if language is not None:
        return NAME_OVERRIDES.get(
            language.alpha_3, _MACROLANGUAGE.sub("", language.name)
        )

    family = pycountry.language_families.get(alpha_3=key)
    if family is not None:
        return family.name

    return text
