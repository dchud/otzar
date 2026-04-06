from django.shortcuts import render

from catalog.models import Author, Record


def home(request):
    stats = {
        "total_records": Record.objects.count(),
        "total_authors": Author.objects.count(),
        "recent_records": Record.objects.order_by("-created_at")[:5],
    }
    return render(request, "home.html", stats)
