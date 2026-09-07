"""Views for household creation and slug-based access, per issue #2.

Function-based views only, per `_docs/arch.md` §3.
"""

from django.db import transaction
from django.db.models import F
from django.db.models.functions import Lower
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from chores.models import Chore, ChoreStatus

from .forms import PartnerNamingForm
from .models import Household, Partner

SESSION_KEY = "household_slug"


def _acting_as_session_key(slug):
    """Session key for the "acting as" partner selection, scoped to a
    household by its slug so switching households in the same browser
    session can never leak one household's selection into another's
    (`_docs/arch.md` §2)."""
    return f"acting_as:{slug}"


def _get_acting_as_partner(request, household, partners):
    """Resolve the currently-selected "acting as" partner for this
    household from the session, or `None` if nothing valid is stored.

    Falls back to `None` (rather than raising) when the session holds a
    partner id that doesn't belong to this household — e.g. a stale
    value left over from a future household-reset feature.
    """
    partner_id = request.session.get(_acting_as_session_key(household.slug))
    if partner_id is None:
        return None
    for partner in partners:
        if partner.pk == partner_id:
            return partner
    return None


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
        acting_as = _get_acting_as_partner(request, household, partners)
        active_chores = list(
            Chore.objects.filter(household=household, status=ChoreStatus.ACTIVE)
            .select_related("owner")
            .order_by(Lower("owner__name"), F("due_date").asc(nulls_last=True))
        )
        return render(
            request,
            "households/detail.html",
            {
                "household": household,
                "partners": partners,
                "acting_as": acting_as,
                "active_chores": active_chores,
                "has_active_chores": bool(active_chores),
            },
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


def settings_placeholder(request):
    """`GET /settings/` — placeholder page for the "Settings" nav link.

    Not named `settings` as a Django app to avoid colliding with
    `config/settings/` (see issue #4 Constraints); it lives as a plain
    route on `households` instead, since it isn't household-scoped yet.
    Real settings pages are #19/#20.
    """
    return render(request, "households/settings.html")


def set_acting_as(request, slug):
    """`POST /h/<slug>/acting-as/` — store which partner the visitor is
    currently acting as, scoped to this household.

    Only accepts POST (a selection is a state change, not a page fetch).
    A `partner_id` that isn't a valid, existing partner of this household
    is ignored rather than erroring, so a malformed or stale submission
    just leaves the session unchanged and redirects back to the page.
    """
    if request.method != "POST":
        return redirect("households:detail", slug=slug)

    household = get_object_or_404(Household, slug=slug)

    partner_id = request.POST.get("partner_id")
    if partner_id is not None:
        partner = household.partners.filter(pk=partner_id).first()
        if partner is not None:
            request.session[_acting_as_session_key(slug)] = partner.pk

    return redirect("households:detail", slug=slug)
