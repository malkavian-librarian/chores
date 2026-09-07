"""Views for the `chores` app, per issue #8.

Function-based views only, per `_docs/arch.md` §3. Plain full-page
GET-form / POST-redirect flow -- not an HTMX partial (see issue #8's
Constraints).
"""

from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from households.models import Household
from households.views import _get_acting_as_partner

from .forms import ChoreEditForm, ChoreQuickAddForm
from .models import Chore, ChoreStatus


def _just_completed_session_key(slug, chore_id):
    """Session key naming "this chore was just completed by this visitor,
    in this browser, and hasn't been viewed on the confirmation page
    yet" -- see `chore_complete`/`chore_just_completed` below.
    """
    return f"just_completed:{slug}:{chore_id}"


def quick_add(request, slug):
    """`GET/POST /h/<slug>/chores/add/` -- quick-add a chore.

    - Fewer than 2 partners: redirect to the household page rather than
      raising a 500 (the household page itself renders the partner
      naming form in that state, per issue #2/#3).
    - GET: render the form, defaulting `owner` to the visitor's
      "acting as" partner when one is selected in session.
    - POST valid: create the `Chore` and redirect to the household
      page. `created_by` is the "acting as" partner when one is
      selected; otherwise it's whichever partner was chosen as
      `owner` on this submission, since there's no other identity to
      attribute authorship to.
    - POST invalid (e.g. blank title): re-render the form with errors,
      creating zero rows and preserving what was typed.
    """
    household = get_object_or_404(Household, slug=slug)
    partners = list(household.partners.all())

    if len(partners) != 2:
        return redirect("households:detail", slug=slug)

    acting_as = _get_acting_as_partner(request, household, partners)

    if request.method == "POST":
        form = ChoreQuickAddForm(request.POST, household=household, acting_as=acting_as)
        if form.is_valid():
            owner = form.cleaned_data["owner"]
            created_by = acting_as if acting_as is not None else owner
            Chore.objects.create(
                household=household,
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                owner=owner,
                category=form.cleaned_data["category"],
                due_date=form.cleaned_data["due_date"],
                created_by=created_by,
            )
            return redirect("households:detail", slug=slug)
    else:
        form = ChoreQuickAddForm(household=household, acting_as=acting_as)

    return render(request, "chores/quick_add.html", {"household": household, "form": form})


def chore_detail(request, slug, chore_id):
    """`GET/POST /h/<slug>/chores/<chore_id>/` -- chore details/edit view.

    Per issue #11:

    - A plain full-page view (not HTMX -- see the issue's Constraints).
    - Looked up via `household.chores.filter(pk=...)`
      (`get_object_or_404(household.chores, pk=...)`), not
      `Chore.objects.get(pk=...)`, so a chore id belonging to another
      household -- or that doesn't exist at all -- 404s instead of
      leaking.
    - GET renders the edit form pre-filled with the chore's current
      values.
    - POST valid: persists the edit and redirects to the household
      list. This is *not* gated on "acting as" state at all -- either
      partner may edit a chore regardless of who (if anyone) is
      currently selected as acting-as (`plan.md` §3).
    - POST invalid: re-renders the form with errors, changing nothing.
    - The delete button is only ever shown (`can_delete`) when the
      visitor's acting-as partner equals the chore's `created_by`; the
      actual delete permission check lives in `chore_delete` below, not
      just in the template.
    """
    household = get_object_or_404(Household, slug=slug)
    chore = get_object_or_404(household.chores, pk=chore_id)
    partners = list(household.partners.all())
    acting_as = _get_acting_as_partner(request, household, partners)

    if request.method == "POST":
        form = ChoreEditForm(request.POST, household=household)
        if form.is_valid():
            chore.title = form.cleaned_data["title"]
            chore.description = form.cleaned_data["description"]
            chore.owner = form.cleaned_data["owner"]
            chore.category = form.cleaned_data["category"]
            chore.due_date = form.cleaned_data["due_date"]
            chore.save()
            return redirect("households:detail", slug=slug)
    else:
        form = ChoreEditForm(
            household=household,
            initial={
                "title": chore.title,
                "description": chore.description,
                "owner": chore.owner_id,
                "due_date": chore.due_date,
                "category": chore.category_id,
            },
        )

    can_delete = acting_as is not None and acting_as == chore.created_by
    is_active = chore.status == ChoreStatus.ACTIVE
    can_complete = acting_as is not None and is_active

    return render(
        request,
        "chores/detail.html",
        {
            "household": household,
            "chore": chore,
            "form": form,
            "can_delete": can_delete,
            "is_active": is_active,
            "can_complete": can_complete,
        },
    )


def chore_delete(request, slug, chore_id):
    """`POST /h/<slug>/chores/<chore_id>/delete/` -- delete a chore.

    Per issue #11: only the chore's `created_by` partner may delete it,
    checked here against the current "acting as" partner (the only
    stand-in for identity this app has -- there is no login). A direct
    POST while acting as the non-creator partner, or with no acting-as
    partner selected at all (there's no creator identity to match, so
    it can never be authorized), is rejected with 403 -- not a 500 and
    not a silent success -- and the chore is left untouched.

    GET (or any other method) redirects back to the detail page rather
    than deleting anything, since a delete must be a deliberate POST.
    """
    household = get_object_or_404(Household, slug=slug)
    chore = get_object_or_404(household.chores, pk=chore_id)

    if request.method != "POST":
        return redirect("chores:chore_detail", slug=slug, chore_id=chore.pk)

    partners = list(household.partners.all())
    acting_as = _get_acting_as_partner(request, household, partners)

    if acting_as is None or acting_as.pk != chore.created_by_id:
        return HttpResponseForbidden("Only the chore's creator may delete it.")

    chore.delete()
    return redirect("households:detail", slug=slug)


def chore_complete(request, slug, chore_id):
    """`POST /h/<slug>/chores/<chore_id>/complete/` -- mark a chore done.

    Per issue #12: follows `chore_delete`'s permission-check shape --
    no acting-as partner selected means there is no identity to
    attribute completion to, so the request is rejected with
    `HttpResponseForbidden` (not a 500, not a silent redirect) and the
    chore is left untouched. GET (or any other method) redirects to
    the chore detail page rather than mutating anything.

    Setting `status`/`completed_at`/`completed_by` is a no-op if the
    chore is already `status=completed` -- a stale page, a
    double-click, or a resubmitted form never overwrites the original
    completion's timestamp/attribution.

    Undo window (issue #12's Constraints): there is no server-enforced
    expiry and no client-side JS timer. Instead, a one-shot session
    flag is set here naming this household+chore, and redirects to the
    `chore_just_completed` confirmation page below, which *consumes*
    (pops) that flag on the very next GET. That makes the page's Undo
    control genuinely one-time: reloading it, bookmarking it, or
    reaching it any other way after the first render finds the flag
    already gone and bounces to the plain chore detail page (which has
    no Undo control) instead. This holds whether or not this POST
    actually changed anything, so a double-Done still lands on the
    confirmation page rather than a 500.
    """
    household = get_object_or_404(Household, slug=slug)
    chore = get_object_or_404(household.chores, pk=chore_id)

    if request.method != "POST":
        return redirect("chores:chore_detail", slug=slug, chore_id=chore.pk)

    partners = list(household.partners.all())
    acting_as = _get_acting_as_partner(request, household, partners)

    if acting_as is None:
        return HttpResponseForbidden("Select an acting-as partner to complete a chore.")

    if chore.status != ChoreStatus.COMPLETED:
        chore.status = ChoreStatus.COMPLETED
        chore.completed_at = timezone.now()
        chore.completed_by = acting_as
        chore.save()

    request.session[_just_completed_session_key(slug, chore.pk)] = True
    return redirect("chores:chore_just_completed", slug=slug, chore_id=chore.pk)


def chore_just_completed(request, slug, chore_id):
    """`GET /h/<slug>/chores/<chore_id>/completed/` -- one-time "Done!
    Undo?" confirmation page.

    Only ever renders the Undo control immediately after a successful
    `chore_complete` POST from *this* browser session: it checks for
    (and pops) the one-shot session flag `chore_complete` set. A first
    visit right after Done finds the flag, consumes it, and renders
    the confirmation template with the Undo form. Any later visit --
    a reload, the back button, a bookmark, or navigating here
    directly -- finds the flag already gone (it was popped the first
    time) and redirects to the plain chore detail page instead, which
    has no Undo control anywhere. This is the entire mechanism behind
    issue #12's "no server-side time limit, offered exactly once"
    Undo window.
    """
    household = get_object_or_404(Household, slug=slug)
    chore = get_object_or_404(household.chores, pk=chore_id)

    session_key = _just_completed_session_key(slug, chore.pk)
    if not request.session.pop(session_key, False):
        return redirect("chores:chore_detail", slug=slug, chore_id=chore.pk)

    return render(request, "chores/just_completed.html", {"household": household, "chore": chore})


def chore_undo(request, slug, chore_id):
    """`POST /h/<slug>/chores/<chore_id>/undo/` -- revert a completion.

    Per issue #12: only reachable in practice from the one-time
    `chore_just_completed` page, but defensively a no-op regardless of
    how it's reached -- if the chore isn't currently
    `status=completed` (already undone, replayed/bookmarked POST, or a
    later Done already happened), nothing is changed; `status`,
    `completed_at`, and `completed_by` are left exactly as they are.
    GET (or any other method) redirects to the chore detail page
    rather than mutating anything, mirroring `chore_delete`/
    `chore_complete`.
    """
    household = get_object_or_404(Household, slug=slug)
    chore = get_object_or_404(household.chores, pk=chore_id)

    if request.method != "POST":
        return redirect("chores:chore_detail", slug=slug, chore_id=chore.pk)

    if chore.status == ChoreStatus.COMPLETED:
        chore.status = ChoreStatus.ACTIVE
        chore.completed_at = None
        chore.completed_by = None
        chore.save()

    return redirect("households:detail", slug=slug)
