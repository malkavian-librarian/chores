"""Views for the categories app.

Bare listing only, per issue #5 — no CRUD yet (that's #6).
"""

from django.http import Http404
from django.shortcuts import render

from households.models import Household


def index(request, slug):
    """`GET /h/<slug>/categories/` — bare list of a household's categories.

    Visiting a slug that doesn't exist returns 404, matching
    `households:detail`.
    """
    household = Household.objects.filter(slug=slug).first()
    if household is None:
        raise Http404("No household matches this slug.")

    categories = list(household.categories.all())

    return render(
        request,
        "categories/index.html",
        {"household": household, "categories": categories},
    )
