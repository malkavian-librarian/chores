"""Views for household creation and slug-based access, per issue #2.

Function-based views only, per `_docs/arch.md` §3.
"""

from django.http import Http404
from django.shortcuts import redirect, render

from .models import Household

SESSION_KEY = "household_slug"


def index(request):
    """`GET /` — create-or-resume the visitor's household, then redirect.

    - No slug in the session yet: create a new Household, store its slug
      in the session, redirect to `/h/<slug>/`.
    - Slug already in the session from a previous visit: redirect there
      without creating a second household.
    """
    slug = request.session.get(SESSION_KEY)
    if not slug or not Household.objects.filter(slug=slug).exists():
        household = Household.create_with_unique_slug()
        slug = household.slug
        request.session[SESSION_KEY] = slug

    return redirect("households:detail", slug=slug)


def detail(request, slug):
    """`GET /h/<slug>/` — 200 with a minimal page if the slug exists, else 404.

    No Partner data exists yet (that's #3), so this must not query or
    assume any — it only needs the Household row itself.
    """
    household = Household.objects.filter(slug=slug).first()
    if household is None:
        raise Http404("No household matches this slug.")

    return render(request, "households/detail.html", {"household": household})
