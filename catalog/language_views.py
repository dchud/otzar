import pycountry
from django.http import JsonResponse

from catalog.language_codes import language_name


def language_search(request):
    """Return matching ISO 639 languages as JSON for autosuggest.

    Searches both the language code and name, and returns the
    bibliographic form of the code, which is what MARC 008/35-37 carries
    and what records store. Returns up to 10 results.
    """
    q = request.GET.get("q", "").strip().lower()
    if not q or len(q) < 2:
        return JsonResponse([], safe=False)

    results = []
    for lang in pycountry.languages:
        code = lang.alpha_3
        bib = getattr(lang, "bibliographic", code)
        name = language_name(bib)

        if q in code.lower() or q in bib.lower() or q in name.lower():
            results.append({"code": bib, "name": name})
            if len(results) >= 10:
                break

    return JsonResponse(results, safe=False)
