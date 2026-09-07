"""Views for household creation and slug-based access, per issue #2.

Function-based views only, per `_docs/arch.md` §3.
"""

from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.db.models.functions import Lower
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from chores.models import Chore, ChoreStatus

from .forms import PartnerNamingForm, PartnerRenameForm, ResetDataForm
from .models import Household, Partner

#: The exact three "Reset data" option names (issue #20 Constraints --
#: no "select all"/"everything" shortcut). Both the checkbox step and the
#: confirmation step validate against this same list, via `ResetDataForm`.
RESET_DATA_FIELDS = ("active_chores", "completed_history", "custom_categories")

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
        today = timezone.localdate()
        active_chores = list(
            Chore.objects.filter(household=household, status=ChoreStatus.ACTIVE)
            .select_related("owner")
            .order_by(Lower("owner__name"), F("due_date").asc(nulls_last=True))
        )
        for chore in active_chores:
            # Computed here (issue #10), not in the template, per
            # `_docs/arch.md` §5 ("no business logic in templates").
            # `today` is fixed once per request via `timezone.localdate()`
            # (project has `USE_TZ = True`), never `date.today()`.
            chore.is_overdue = chore.due_date is not None and chore.due_date < today
        # Issue #14: the "Completed" section's history. No `ChoreHistory`
        # model — a `Chore`'s own row, once `status=completed`, is its own
        # history for now (see issue #14 Constraints). A chore that was
        # completed and then undone (#12) reverts to `status=active` and
        # so is naturally excluded here without any special-case code.
        completed_chores = list(
            household.chores.filter(status=ChoreStatus.COMPLETED)
            .select_related("completed_by")
            .order_by("-completed_at")
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
                "completed_chores": completed_chores,
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


def settings(request, slug):
    """`GET/POST /h/<slug>/settings/` — rename either partner (issue #19).

    Not named as a Django app to avoid colliding with `config/settings/`
    (see issue #4 Constraints); it lives as a plain household-scoped
    route on `households` instead.

    - Fewer than 2 `Partner` rows (reachable only by visiting the URL
      directly before first-launch naming from #3 is complete): redirect
      to the household detail page, which itself shows the naming form.
    - GET: renders both partners' current names, pre-filled.
    - POST valid: updates each `Partner.name` in place (same pk) and
      redirects back here so a refresh doesn't resubmit the form.
    """
    household = get_object_or_404(Household, slug=slug)
    partners = list(household.partners.order_by("pk"))

    if len(partners) < 2:
        return redirect("households:detail", slug=slug)

    partner_1, partner_2 = partners[0], partners[1]

    if request.method == "POST":
        form = PartnerRenameForm(request.POST)
        if form.is_valid():
            partner_1.name = form.cleaned_data["partner_1_name"]
            partner_2.name = form.cleaned_data["partner_2_name"]
            partner_1.save(update_fields=["name"])
            partner_2.save(update_fields=["name"])
            return redirect("households:settings", slug=slug)
    else:
        form = PartnerRenameForm(
            initial={
                "partner_1_name": partner_1.name,
                "partner_2_name": partner_2.name,
            }
        )

    return render(
        request,
        "households/settings.html",
        {
            "household": household,
            "form": form,
            "partners": partners,
            "reset_form": ResetDataForm(),
        },
    )


def _get_household_with_partners_or_redirect(slug):
    """Shared guard for the reset-data views: fetch the household and its
    partners, returning `(household, partners, None)` when there are at
    least 2 partners, or `(None, None, redirect_response)` when the
    household has fewer than 2 (pre-onboarding), matching `settings`'s
    existing guard.
    """
    household = get_object_or_404(Household, slug=slug)
    partners = list(household.partners.order_by("pk"))
    if len(partners) < 2:
        return None, None, redirect("households:detail", slug=household.slug)
    return household, partners, None


def _reset_data_selection_counts(household, selections):
    """Row counts for each *selected* reset option, computed just before
    rendering the confirmation page -- never persisted, always freshly
    queried so the confirmed step can't act on stale numbers.
    """
    counts = {}
    if selections["active_chores"]:
        counts["active_chores"] = household.chores.filter(status=ChoreStatus.ACTIVE).count()
    if selections["completed_history"]:
        counts["completed_history"] = household.chores.filter(status=ChoreStatus.COMPLETED).count()
    if selections["custom_categories"]:
        counts["custom_categories"] = household.categories.filter(is_predefined=False).count()
    return counts


def reset_data(request, slug):
    """`POST /h/<slug>/settings/reset/` — step 1 of the reset-data flow
    (issue #20): take the "Reset data" checkbox selection from the
    Settings page and show a confirmation page listing exactly what will
    be deleted, with counts. Deletes nothing.

    - Fewer than 2 `Partner` rows: redirect to household detail, same
      guard as `settings`.
    - Non-POST (e.g. a direct GET on this URL): redirect back to
      Settings, where the checkboxes actually live -- nothing to show
      here without a submitted selection.
    - Zero boxes checked: accepted as a no-op, no confirmation page,
      straight back to Settings with an informational message.
    """
    household, partners, guard_response = _get_household_with_partners_or_redirect(slug)
    if guard_response is not None:
        return guard_response

    if request.method != "POST":
        return redirect("households:settings", slug=slug)

    form = ResetDataForm(request.POST)
    if not form.is_valid():
        return redirect("households:settings", slug=slug)

    selections = {name: form.cleaned_data[name] for name in RESET_DATA_FIELDS}

    if not any(selections.values()):
        messages.info(request, "Nothing selected — no household data was deleted.")
        return redirect("households:settings", slug=slug)

    counts = _reset_data_selection_counts(household, selections)

    return render(
        request,
        "households/reset_data_confirm.html",
        {"household": household, "selections": selections, "counts": counts},
    )


def reset_data_confirm(request, slug):
    """`POST /h/<slug>/settings/reset/confirm/` — step 2 of the reset-data
    flow (issue #20): actually perform the deletion(s) the user just saw
    counts for, atomically, then redirect back to Settings.

    Re-validates the selection carried forward as hidden fields rather
    than trusting a session flag, and re-derives every query from
    `RESET_DATA_FIELDS`/`household` scoping rather than accepting any
    row ids from the client -- so a manipulated POST can, at most, select
    a subset of these three fixed, household-scoped deletions. In
    particular, predefined categories are never reachable here: the
    "Custom categories" branch always filters `is_predefined=False`
    regardless of what else is in the request body.

    - Fewer than 2 `Partner` rows: redirect to household detail.
    - Non-POST, or zero boxes selected: no-op back to Settings, same as
      `reset_data`'s guards -- reachable if this URL is hit directly
      without going through the confirmation page.
    """
    household, partners, guard_response = _get_household_with_partners_or_redirect(slug)
    if guard_response is not None:
        return guard_response

    if request.method != "POST":
        return redirect("households:settings", slug=slug)

    form = ResetDataForm(request.POST)
    if not form.is_valid():
        return redirect("households:settings", slug=slug)

    selections = {name: form.cleaned_data[name] for name in RESET_DATA_FIELDS}

    if not any(selections.values()):
        messages.info(request, "Nothing selected — no household data was deleted.")
        return redirect("households:settings", slug=slug)

    with transaction.atomic():
        if selections["active_chores"]:
            household.chores.filter(status=ChoreStatus.ACTIVE).delete()
        if selections["completed_history"]:
            household.chores.filter(status=ChoreStatus.COMPLETED).delete()
        if selections["custom_categories"]:
            household.categories.filter(is_predefined=False).delete()

    messages.success(request, "Selected household data has been reset.")
    return redirect("households:settings", slug=slug)


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
