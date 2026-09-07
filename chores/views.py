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

from .forms import ChoreEditForm, ChoreQuickAddForm, recurrence_initial
from .models import Chore, ChoreStatus, Recurrence
from .recurrence import compute_next_due_date


def _apply_recurrence(chore, recurrence_kwargs):
    """Set/change/clear `chore`'s `Recurrence` per issue #15's
    acceptance criteria: `recurrence_kwargs` is the dict returned by
    `BaseChoreForm.get_recurrence_kwargs()` (`None` for "no
    recurrence"). Never touches `chore.owner` or any other `Chore`
    field. Overwrites all five kind-specific fields on an existing row
    wholesale so a kind switch never leaves stale values behind, and
    runs `full_clean()` so `Recurrence.clean()`'s field-relevance
    validation applies here too, not just via a form.
    """
    existing = getattr(chore, "recurrence", None)

    if recurrence_kwargs is None:
        if existing is not None:
            existing.delete()
        return

    if existing is not None:
        for field, value in recurrence_kwargs.items():
            setattr(existing, field, value)
        existing.full_clean()
        existing.save()
    else:
        recurrence = Recurrence(chore=chore, **recurrence_kwargs)
        recurrence.full_clean()
        recurrence.save()


def _just_completed_session_key(slug, chore_id):
    """Session key naming "this chore was just completed by this visitor,
    in this browser, and hasn't been viewed on the confirmation page
    yet" -- see `chore_complete`/`chore_just_completed` below.
    """
    return f"just_completed:{slug}:{chore_id}"


def _generated_chore_session_key(slug, chore_id):
    """Session key naming "completing this chore generated this next
    occurrence" -- issue #17's chosen mechanism for `chore_undo` to find
    (and delete) the occurrence a completion generated.

    Deliberately a *separate* session key from
    `_just_completed_session_key` rather than folded into it: the
    just-completed flag is popped (consumed) the first time the
    confirmation page is viewed (issue #12's one-shot mechanism), but
    Undo -- POSTed *from* that same page -- still needs to know which
    chore it generated at that point. Keeping this key separate, and
    popping it only in `chore_undo` itself, means it survives exactly
    as long as it needs to: set on a successful `chore_complete` that
    generated an occurrence, read once (and removed) by `chore_undo`
    when it actually reverts the completion, without racing the
    just-completed flag's own one-shot lifecycle.
    """
    return f"generated_chore:{slug}:{chore_id}"


def _create_next_occurrence(chore):
    """Create the next occurrence of a just-completed recurring `chore`,
    per issue #17: a new active `Chore` with the same `household`,
    `owner`, `title`, `description`, `category` as `chore`, `due_date`
    computed by `compute_next_due_date`, and its own cloned `Recurrence`
    row (same `kind` and kind-specific fields -- `Recurrence` is
    `OneToOne` with `Chore`, so the existing row can't be reused/moved).

    `created_by` is copied from the completed chore too -- there's no
    other partner to attribute authorship of a system-generated
    occurrence to, and the plan doesn't distinguish "who created" from
    "who owns" for recurrence purposes.

    Returns the new `Chore`. Only called when `chore.recurrence` exists;
    callers are responsible for that check.
    """
    recurrence = chore.recurrence
    next_due_date = compute_next_due_date(recurrence, chore.completed_at)

    next_chore = Chore.objects.create(
        household=chore.household,
        title=chore.title,
        description=chore.description,
        owner=chore.owner,
        category=chore.category,
        due_date=next_due_date,
        created_by=chore.created_by,
        status=ChoreStatus.ACTIVE,
    )
    Recurrence.objects.create(
        chore=next_chore,
        kind=recurrence.kind,
        weekday=recurrence.weekday,
        month_day=recurrence.month_day,
        month_ordinal=recurrence.month_ordinal,
        month_weekday=recurrence.month_weekday,
        interval_days=recurrence.interval_days,
    )
    return next_chore


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
            chore = Chore.objects.create(
                household=household,
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                owner=owner,
                category=form.cleaned_data["category"],
                due_date=form.cleaned_data["due_date"],
                created_by=created_by,
            )
            _apply_recurrence(chore, form.get_recurrence_kwargs())
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
            _apply_recurrence(chore, form.get_recurrence_kwargs())
            return redirect("households:detail", slug=slug)
    else:
        initial = {
            "title": chore.title,
            "description": chore.description,
            "owner": chore.owner_id,
            "due_date": chore.due_date,
            "category": chore.category_id,
        }
        initial.update(recurrence_initial(getattr(chore, "recurrence", None)))
        form = ChoreEditForm(household=household, initial=initial)

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

    Per issue #17: if `chore` has a `Recurrence`, completing it also
    synchronously creates the next occurrence (see
    `_create_next_occurrence`) -- no cron/background job, per
    `_docs/arch.md` §12. This only happens on the completion that
    actually flips `status` (guarded by the same `!= COMPLETED` check
    as the fields above), so a double-Done never generates a second
    occurrence. The generated chore's id is stashed in the session
    (`_generated_chore_session_key`) so `chore_undo` can find and
    delete it if this completion is undone.
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

        if getattr(chore, "recurrence", None) is not None:
            next_chore = _create_next_occurrence(chore)
            request.session[_generated_chore_session_key(slug, chore.pk)] = next_chore.pk

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

    Per issue #13: also resets `note` back to `""` when reverting, so a
    note attached to the undone completion doesn't linger and get
    misattributed to the chore's next completion.

    Per issue #17: if that completion generated a next occurrence (see
    `chore_complete`/`_create_next_occurrence`), Undo also deletes that
    generated `Chore` (its `Recurrence` cascades automatically) so the
    household ends up with exactly the original chore, active, and no
    trace of the occurrence that was generated -- not just the reverted
    original alongside an orphaned generated row. The generated chore's
    id is looked up (and popped) from the session key `chore_complete`
    set; it's popped unconditionally here rather than left to leak
    across future completions of the same chore.
    """
    household = get_object_or_404(Household, slug=slug)
    chore = get_object_or_404(household.chores, pk=chore_id)

    if request.method != "POST":
        return redirect("chores:chore_detail", slug=slug, chore_id=chore.pk)

    generated_chore_id = request.session.pop(_generated_chore_session_key(slug, chore.pk), None)

    if chore.status == ChoreStatus.COMPLETED:
        chore.status = ChoreStatus.ACTIVE
        chore.completed_at = None
        chore.completed_by = None
        chore.note = ""
        chore.save()

        if generated_chore_id is not None:
            household.chores.filter(pk=generated_chore_id).delete()

    return redirect("households:detail", slug=slug)


def chore_add_note(request, slug, chore_id):
    """`POST /h/<slug>/chores/<chore_id>/add-note/` -- attach an optional
    note to a chore's current completion.

    Per issue #13: reachable in practice from the "Add note" form on
    the one-time `chore_just_completed` confirmation page, alongside
    Undo, but does not itself reuse that page's one-shot session flag
    -- it only needs the chore to currently be `status=completed`
    (there's only ever one completion in flight at a time, since
    recurrence/history don't exist yet), which lets a note be added,
    then resubmitted (overwriting, not appending) without a second
    one-time flag to fight. GET (or any other method) redirects to the
    chore detail page rather than mutating anything, mirroring
    `chore_complete`/`chore_undo`.

    Permission mirrors `chore_complete`: no acting-as partner selected
    means there is no identity to attribute the note to, so the
    request is rejected with `HttpResponseForbidden`. If the chore
    isn't currently completed (already undone, or no completion yet),
    this is a no-op redirect to the detail page -- there's no active
    completion for the note to attach to.

    The submitted text is stripped before saving; blank/whitespace-only
    text is treated as no note and stored as `""` (matching the
    `blank=True` `TextField` convention already used for
    `description`), not as whitespace. Skipping this endpoint entirely
    (navigating away from the confirmation page without submitting)
    leaves `chore.note` exactly as it was -- `""` for a fresh
    completion -- which is the default, non-blocking path.
    """
    household = get_object_or_404(Household, slug=slug)
    chore = get_object_or_404(household.chores, pk=chore_id)

    if request.method != "POST":
        return redirect("chores:chore_detail", slug=slug, chore_id=chore.pk)

    partners = list(household.partners.all())
    acting_as = _get_acting_as_partner(request, household, partners)

    if acting_as is None:
        return HttpResponseForbidden("Select an acting-as partner to add a note.")

    if chore.status != ChoreStatus.COMPLETED:
        return redirect("chores:chore_detail", slug=slug, chore_id=chore.pk)

    chore.note = request.POST.get("note", "").strip()
    chore.save()

    return render(request, "chores/just_completed.html", {"household": household, "chore": chore})
