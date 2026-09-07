"""Plain Django forms for the `categories` app, per `_docs/arch.md` §5/§12.

No REST API, no client-side JS framework — a full-page GET/POST must work
without HTMX.
"""

from django import forms

from .models import CATEGORY_NAME_MAX_LENGTH


class CategoryForm(forms.Form):
    """Create/rename form for a *custom* `Category`.

    Serves both create and rename: pass `household` so the
    case-insensitive duplicate-name check (against every category in
    that household, predefined or custom, per issue #6's acceptance
    criteria) is scoped correctly, and pass `exclude_pk` on rename so a
    category doesn't collide with its own current name.

    `strip=True` plus `required` (the `CharField` default) means an
    empty or whitespace-only name is rejected by the field itself
    before `clean_name` ever runs.
    """

    name = forms.CharField(max_length=CATEGORY_NAME_MAX_LENGTH, strip=True)

    def __init__(self, *args, household=None, exclude_pk=None, **kwargs):
        self.household = household
        self.exclude_pk = exclude_pk
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"]
        if self.household is not None:
            conflicts = self.household.categories.filter(name__iexact=name)
            if self.exclude_pk is not None:
                conflicts = conflicts.exclude(pk=self.exclude_pk)
            if conflicts.exists():
                raise forms.ValidationError(
                    f'A category named "{name}" already exists in this household.'
                )
        return name
