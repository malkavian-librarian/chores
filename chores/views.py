"""Views for the `chores` app, per issue #8.

Function-based views only, per `_docs/arch.md` §3. Plain full-page
GET-form / POST-redirect flow -- not an HTMX partial (see issue #8's
Constraints).
"""

from django.shortcuts import get_object_or_404, redirect, render

from households.models import Household
from households.views import _get_acting_as_partner

from .forms import ChoreQuickAddForm
from .models import Chore


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
