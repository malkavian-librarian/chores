"""Plain Django form for the quick-add chore flow, per issue #8.

Full-page GET-form / POST-redirect, not an HTMX partial -- see issue
#8's Constraints for why no HTMX plumbing is added yet. Owner/category
choices are scoped to the household passed in at construction time
(`household.partners.all()` / `household.categories.all()`) so this
form can never leak another household's partners/categories as
choices.
"""

from django import forms

from chores.models import TITLE_MAX_LENGTH

NO_CATEGORY_LABEL = "No category"
NO_ACTING_AS_OWNER_LABEL = "Select owner"


class BaseChoreForm(forms.Form):
    """Shared field set for the quick-add and edit/detail chore forms
    (title, description, owner, due_date, category), per issue #11's
    Constraints: extend/reuse `ChoreQuickAddForm` rather than
    duplicating its fields and household-scoped querysets.

    `owner`/`category` choices are always scoped to the household
    passed in at construction time (`household.partners.all()` /
    `household.categories.all()`) so this form can never leak another
    household's partners/categories as choices.
    """

    title = forms.CharField(max_length=TITLE_MAX_LENGTH, strip=True)
    description = forms.CharField(required=False, strip=True, widget=forms.Textarea)
    owner = forms.ModelChoiceField(queryset=None)
    due_date = forms.DateField(required=False)
    category = forms.ModelChoiceField(queryset=None, required=False, empty_label=NO_CATEGORY_LABEL)

    def __init__(self, *args, household, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = household.partners.all()
        self.fields["category"].queryset = household.categories.all()


class ChoreQuickAddForm(BaseChoreForm):
    """Title is the only field visible by default; description, owner,
    due_date, and category are the fields the template puts behind a
    collapsible `<details>` expander.

    `owner` always renders as a real dropdown of the household's two
    partners: with an "acting as" partner selected in session it
    defaults to that partner (but is still changeable to the other
    one); with no "acting as" partner selected it has no default and
    must be chosen explicitly (issue #8 acceptance criteria).
    """

    def __init__(self, *args, household, acting_as, **kwargs):
        super().__init__(*args, household=household, **kwargs)

        if acting_as is not None:
            # A real default exists: no blank option, and it's
            # pre-selected on GET, but the field stays a normal
            # required dropdown the visitor can still change.
            self.fields["owner"].empty_label = None
            self.initial["owner"] = acting_as.pk
        else:
            # No identity to default to: force an explicit choice by
            # keeping the blank option, so an unchanged blank submit
            # fails validation instead of silently defaulting.
            self.fields["owner"].empty_label = NO_ACTING_AS_OWNER_LABEL


class ChoreEditForm(BaseChoreForm):
    """Edit form for an existing chore, per issue #11.

    Unlike the quick-add form, an existing chore always has a real
    `owner` value already, and editing is not gated on "acting as"
    identity at all (either partner may edit regardless of acting-as
    state, per `plan.md` §3) -- so `owner` is just a normal required
    dropdown with no blank option, pre-filled by the view via
    `initial=`.
    """

    def __init__(self, *args, household, **kwargs):
        super().__init__(*args, household=household, **kwargs)
        self.fields["owner"].empty_label = None
