import pycountry
from django.http import JsonResponse


def language_search(request):
    """Return matching ISO 639 languages as JSON for autosuggest.

    Searches both the language code and name. Returns up to 10 results.
    """
    q = request.GET.get("q", "").strip().lower()
    if not q or len(q) < 2:
        return JsonResponse([], safe=False)

    results = []
    for lang in pycountry.languages:
        code = lang.alpha_3
        name = lang.name
        bib = getattr(lang, "bibliographic", code)

        if q in code.lower() or q in bib.lower() or q in name.lower():
            results.append({"code": bib, "name": name})
            if len(results) >= 10:
                break

    return JsonResponse(results, safe=False)
