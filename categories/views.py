"""Views for the categories app.

Bare listing from issue #5, plus create/rename/delete for *custom*
categories from issue #6. Predefined categories can never be renamed
or deleted — enforced here at the view level, not only hidden in the
template (issue #6 Constraints).

Every lookup goes through `household.categories.filter(...)`, never a
bare `Category.objects.get(pk=...)`, so a category id belonging to a
different household 404s instead of resolving (issue #6 Constraints).
"""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render

from households.models import Household

from .forms import CategoryForm
from .models import Category


def _get_household_or_404(slug):
    household = Household.objects.filter(slug=slug).first()
    if household is None:
        raise Http404("No household matches this slug.")
    return household


def _get_household_category_or_404(household, pk):
    category = household.categories.filter(pk=pk).first()
    if category is None:
        raise Http404("No category matches this id in this household.")
    return category


def index(request, slug):
    """`GET /h/<slug>/categories/` — list a household's categories, with
    create/rename/delete forms for its custom ones."""
    household = _get_household_or_404(slug)

    categories = list(household.categories.all())

    return render(
        request,
        "categories/index.html",
        {"household": household, "categories": categories},
    )


def create(request, slug):
    """`POST /h/<slug>/categories/create/` — create a custom category.

    Always redirects back to the Categories page: on success the new
    category is in the list; on failure a validation error message is
    attached via the messages framework (empty/whitespace name, or a
    case-insensitive duplicate of an existing category in this
    household).
    """
    household = _get_household_or_404(slug)

    if request.method != "POST":
        return redirect("categories:index", slug=slug)

    form = CategoryForm(request.POST, household=household)
    if form.is_valid():
        Category.objects.create(
            household=household, name=form.cleaned_data["name"], is_predefined=False
        )
        return redirect("categories:index", slug=slug)

    for error in form.errors.get("name", []):
        messages.error(request, error)
    return redirect("categories:index", slug=slug)


def rename(request, slug, pk):
    """`POST /h/<slug>/categories/<pk>/rename/` — rename a custom category.

    Rejects (redirect + error message, never 500) a predefined
    category's id, an empty/whitespace name, or a case-insensitive
    duplicate of another category in this household.
    """
    household = _get_household_or_404(slug)
    category = _get_household_category_or_404(household, pk)

    if request.method != "POST":
        return redirect("categories:index", slug=slug)

    if category.is_predefined:
        messages.error(request, "Predefined categories cannot be renamed.")
        return redirect("categories:index", slug=slug)

    form = CategoryForm(request.POST, household=household, exclude_pk=category.pk)
    if form.is_valid():
        category.name = form.cleaned_data["name"]
        category.save(update_fields=["name"])
        return redirect("categories:index", slug=slug)

    for error in form.errors.get("name", []):
        messages.error(request, error)
    return redirect("categories:index", slug=slug)


def delete(request, slug, pk):
    """`POST /h/<slug>/categories/<pk>/delete/` — delete a custom category.

    Rejects (redirect + error message, never 500) a predefined
    category's id. Deleting the last custom category in a household is
    fine — no special-cased minimum-count rule.
    """
    household = _get_household_or_404(slug)
    category = _get_household_category_or_404(household, pk)

    if request.method != "POST":
        return redirect("categories:index", slug=slug)

    if category.is_predefined:
        messages.error(request, "Predefined categories cannot be deleted.")
        return redirect("categories:index", slug=slug)

    category.delete()
    return redirect("categories:index", slug=slug)
