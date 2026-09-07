"""Views for the categories app.

Placeholder only for issue #4 — no `Category` model or CRUD yet (that's
#5/#6). This just gives the "Categories" nav link a real page.
"""

from django.shortcuts import render


def index(request):
    """`GET /categories/` — placeholder page."""
    return render(request, "categories/index.html")
