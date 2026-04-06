from django.core.paginator import Paginator
from django.shortcuts import render

from catalog.search import search_records


def catalog_search(request):
    """Search the catalog using FTS5 full-text search."""
    query = request.GET.get("q", "").strip()
    page_number = request.GET.get("page", 1)

    if not query:
        return render(request, "catalog/search.html", {"query": ""})

    results = search_records(query, limit=500)
    paginator = Paginator(results, 25)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "catalog/search.html",
        {
            "query": query,
            "page_obj": page_obj,
            "result_count": len(results),
        },
    )
