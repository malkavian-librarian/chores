"""Views for household creation and slug-based access, per issue #2.

Function-based views only, per `_docs/arch.md` §3.
"""

from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render

from .forms import PartnerNamingForm
from .models import Household, Partner

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
    """`GET/POST /h/<slug>/` — household page, with first-launch naming.

    - No `Partner` rows yet: a GET renders the naming form; a valid POST
      creates exactly 2 `Partner` rows and redirects back here.
    - Partners already exist: renders the household page instead of the
      form, on GET or POST alike (a POST here is a double-submit — e.g.
      double-click or back-button resubmit — and is redirected without
      creating any more rows).
    """
    household = Household.objects.filter(slug=slug).first()
    if household is None:
        raise Http404("No household matches this slug.")

    partners = list(household.partners.all())

    if partners:
        if request.method == "POST":
            return redirect("households:detail", slug=slug)
        return render(
            request, "households/detail.html", {"household": household, "partners": partners}
        )

    form = PartnerNamingForm(request.POST if request.method == "POST" else None)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Re-check under the household lock to close the double-submit
            # race: two near-simultaneous POSTs must not both pass the
            # `partners` emptiness check above and each create a pair.
            if not household.partners.exists():
                Partner.objects.bulk_create(
                    [
                        Partner(household=household, name=form.cleaned_data["partner_1_name"]),
                        Partner(household=household, name=form.cleaned_data["partner_2_name"]),
                    ]
                )
        return redirect("households:detail", slug=slug)

    return render(request, "households/detail.html", {"household": household, "form": form})
