"""Plain Django form for the quick-add chore flow, per issue #8.

Full-page GET-form / POST-redirect, not an HTMX partial -- see issue
#8's Constraints for why no HTMX plumbing is added yet. Owner/category
choices are scoped to the household passed in at construction time
(`household.partners.all()` / `household.categories.all()`) so this
form can never leak another household's partners/categories as
choices.
"""

from django import forms

from chores.models import MONTH_ORDINAL_CHOICES, TITLE_MAX_LENGTH, RecurrenceKind

NO_CATEGORY_LABEL = "No category"
NO_ACTING_AS_OWNER_LABEL = "Select owner"

#: Weekday encoding shared with `Recurrence.weekday`/`month_weekday`:
#: 0-6 for Monday-Sunday.
WEEKDAY_CHOICES = [
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
]

NO_RECURRENCE = ""
MONTHLY = "monthly"

#: The five UI-level choices: "no recurrence", "Daily", "Weekly",
#: "Monthly" (issue #15), and "Every X after completion" (issue #16).
#: "Monthly" is a single form-level choice that fans out into
#: `fixed_monthly_date` or `fixed_monthly_relative` via `monthly_mode`
#: below. The interval choice uses `RecurrenceKind.INTERVAL_AFTER_COMPLETION`
#: directly (no further fan-out needed) paired with the preset dropdown
#: below.
RECURRENCE_KIND_CHOICES = [
    (NO_RECURRENCE, "No recurrence"),
    (RecurrenceKind.FIXED_DAILY, "Daily"),
    (RecurrenceKind.FIXED_WEEKLY, "Weekly"),
    (MONTHLY, "Monthly"),
    (RecurrenceKind.INTERVAL_AFTER_COMPLETION, "Every X after completion"),
]

MONTHLY_MODE_DATE = "date"
MONTHLY_MODE_RELATIVE = "relative"

MONTHLY_MODE_CHOICES = [
    (MONTHLY_MODE_DATE, "Specific date"),
    (MONTHLY_MODE_RELATIVE, "Relative day"),
]

#: The four completion-based interval presets from `plan.md` §6. "1
#: month" is stored as exactly 30 days -- a fixed simplification, not a
#: calendar-month calculation (varies 28-31 days) -- per issue #16's
#: acceptance criteria, so a later reader doesn't mistake 30 for a
#: coincidence.
INTERVAL_PRESET_3_DAYS = "3_days"
INTERVAL_PRESET_1_WEEK = "1_week"
INTERVAL_PRESET_2_WEEKS = "2_weeks"
INTERVAL_PRESET_1_MONTH = "1_month"

RECURRENCE_INTERVAL_PRESET_DAYS = {
    INTERVAL_PRESET_3_DAYS: 3,
    INTERVAL_PRESET_1_WEEK: 7,
    INTERVAL_PRESET_2_WEEKS: 14,
    INTERVAL_PRESET_1_MONTH: 30,
}

RECURRENCE_INTERVAL_PRESET_CHOICES = [
    (INTERVAL_PRESET_3_DAYS, "3 days"),
    (INTERVAL_PRESET_1_WEEK, "1 week"),
    (INTERVAL_PRESET_2_WEEKS, "2 weeks"),
    (INTERVAL_PRESET_1_MONTH, "1 month"),
]

#: Reverse lookup (interval_days -> preset key) used by `recurrence_initial()`
#: to pre-fill the preset dropdown for an existing interval recurrence.
_INTERVAL_DAYS_TO_PRESET = {
    days: preset for preset, days in RECURRENCE_INTERVAL_PRESET_DAYS.items()
}


class BaseChoreForm(forms.Form):
    """Shared field set for the quick-add and edit/detail chore forms
    (title, description, owner, due_date, category, recurrence), per
    issue #11's Constraints: extend/reuse `ChoreQuickAddForm` rather
    than duplicating its fields and household-scoped querysets.

    `owner`/`category` choices are always scoped to the household
    passed in at construction time (`household.partners.all()` /
    `household.categories.all()`) so this form can never leak another
    household's partners/categories as choices.

    Recurrence (issue #15) is modeled as a handful of flat fields
    rather than a nested form, per the issue's Constraints ("extend
    `BaseChoreForm`... or add recurrence-specific form fields"):
    `recurrence_kind` picks "no recurrence" / Daily / Weekly / Monthly;
    `recurrence_monthly_mode` is the Monthly sub-choice between a
    specific date and a relative day; the remaining fields hold the
    kind-specific values. `get_recurrence_kwargs()` (called only after
    `is_valid()`) turns these into a single dict of *all five*
    `Recurrence` fields -- the ones outside the chosen kind explicitly
    `None` -- so a caller can blindly overwrite an existing
    `Recurrence`'s fields on a kind switch without leaving stale
    values behind.
    """

    title = forms.CharField(max_length=TITLE_MAX_LENGTH, strip=True)
    description = forms.CharField(required=False, strip=True, widget=forms.Textarea)
    owner = forms.ModelChoiceField(queryset=None)
    due_date = forms.DateField(required=False)
    category = forms.ModelChoiceField(queryset=None, required=False, empty_label=NO_CATEGORY_LABEL)

    recurrence_kind = forms.ChoiceField(choices=RECURRENCE_KIND_CHOICES, required=False)
    recurrence_weekday = forms.TypedChoiceField(choices=WEEKDAY_CHOICES, coerce=int, required=False)
    recurrence_monthly_mode = forms.ChoiceField(choices=MONTHLY_MODE_CHOICES, required=False)
    recurrence_month_day = forms.IntegerField(required=False, min_value=1, max_value=31)
    recurrence_month_ordinal = forms.TypedChoiceField(
        choices=MONTH_ORDINAL_CHOICES, coerce=int, required=False
    )
    recurrence_month_weekday = forms.TypedChoiceField(
        choices=WEEKDAY_CHOICES, coerce=int, required=False
    )
    recurrence_interval_preset = forms.ChoiceField(
        choices=RECURRENCE_INTERVAL_PRESET_CHOICES, required=False
    )

    def __init__(self, *args, household, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = household.partners.all()
        self.fields["category"].queryset = household.categories.all()

    def clean(self):
        cleaned_data = super().clean()
        kind = cleaned_data.get("recurrence_kind")

        # `TypedChoiceField(required=False)` coerces to the field's
        # `empty_value` (`""` by default) rather than `None` when
        # nothing is selected -- and `0` (Monday) is a legitimate
        # weekday value, so this can't just be a falsy check.
        def _is_blank(field_name):
            return cleaned_data.get(field_name) in (None, "")

        if kind == RecurrenceKind.FIXED_WEEKLY and _is_blank("recurrence_weekday"):
            self.add_error("recurrence_weekday", "Choose a weekday for a weekly recurrence.")

        if kind == MONTHLY:
            mode = cleaned_data.get("recurrence_monthly_mode")
            if not mode:
                self.add_error(
                    "recurrence_monthly_mode",
                    "Choose a specific date or a relative day for a monthly recurrence.",
                )
            elif mode == MONTHLY_MODE_DATE:
                if _is_blank("recurrence_month_day"):
                    self.add_error("recurrence_month_day", "Choose a day of the month.")
            elif mode == MONTHLY_MODE_RELATIVE:
                if _is_blank("recurrence_month_ordinal"):
                    self.add_error("recurrence_month_ordinal", "Choose which occurrence.")
                if _is_blank("recurrence_month_weekday"):
                    self.add_error("recurrence_month_weekday", "Choose a weekday.")

        if kind == RecurrenceKind.INTERVAL_AFTER_COMPLETION and _is_blank(
            "recurrence_interval_preset"
        ):
            self.add_error(
                "recurrence_interval_preset",
                "Choose a preset for a completion-based interval recurrence.",
            )

        return cleaned_data

    def get_recurrence_kwargs(self):
        """Return kwargs for the five `Recurrence` kind-specific fields
        (`kind` plus `weekday`/`month_day`/`month_ordinal`/
        `month_weekday`/`interval_days`), or `None` if "no recurrence"
        was chosen. Only callable after a successful `is_valid()`.

        Always returns a value for every field (explicitly `None` for
        the ones that don't belong to the chosen kind), so a caller can
        overwrite an existing `Recurrence`'s fields wholesale on a kind
        switch without leaving stale values from the previous kind.
        """
        kind = self.cleaned_data.get("recurrence_kind")

        if not kind:
            return None

        if kind == MONTHLY:
            mode = self.cleaned_data.get("recurrence_monthly_mode")
            if mode == MONTHLY_MODE_RELATIVE:
                actual_kind = RecurrenceKind.FIXED_MONTHLY_RELATIVE
            else:
                actual_kind = RecurrenceKind.FIXED_MONTHLY_DATE
        else:
            actual_kind = kind

        return {
            "kind": actual_kind,
            "weekday": self.cleaned_data.get("recurrence_weekday")
            if actual_kind == RecurrenceKind.FIXED_WEEKLY
            else None,
            "month_day": self.cleaned_data.get("recurrence_month_day")
            if actual_kind == RecurrenceKind.FIXED_MONTHLY_DATE
            else None,
            "month_ordinal": self.cleaned_data.get("recurrence_month_ordinal")
            if actual_kind == RecurrenceKind.FIXED_MONTHLY_RELATIVE
            else None,
            "month_weekday": self.cleaned_data.get("recurrence_month_weekday")
            if actual_kind == RecurrenceKind.FIXED_MONTHLY_RELATIVE
            else None,
            "interval_days": RECURRENCE_INTERVAL_PRESET_DAYS.get(
                self.cleaned_data.get("recurrence_interval_preset")
            )
            if actual_kind == RecurrenceKind.INTERVAL_AFTER_COMPLETION
            else None,
        }


def recurrence_initial(recurrence):
    """Build the `initial=` dict of `recurrence_*` form fields for an
    existing `Recurrence` (or `{}` when the chore has none), so the
    edit form's GET pre-fills the kind/sub-choice/value currently
    stored, per issue #15.
    """
    if recurrence is None:
        return {}

    if recurrence.kind == RecurrenceKind.FIXED_MONTHLY_DATE:
        return {
            "recurrence_kind": MONTHLY,
            "recurrence_monthly_mode": MONTHLY_MODE_DATE,
            "recurrence_month_day": recurrence.month_day,
        }

    if recurrence.kind == RecurrenceKind.FIXED_MONTHLY_RELATIVE:
        return {
            "recurrence_kind": MONTHLY,
            "recurrence_monthly_mode": MONTHLY_MODE_RELATIVE,
            "recurrence_month_ordinal": recurrence.month_ordinal,
            "recurrence_month_weekday": recurrence.month_weekday,
        }

    if recurrence.kind == RecurrenceKind.FIXED_WEEKLY:
        return {
            "recurrence_kind": RecurrenceKind.FIXED_WEEKLY,
            "recurrence_weekday": recurrence.weekday,
        }

    if recurrence.kind == RecurrenceKind.FIXED_DAILY:
        return {"recurrence_kind": RecurrenceKind.FIXED_DAILY}

    if recurrence.kind == RecurrenceKind.INTERVAL_AFTER_COMPLETION:
        return {
            "recurrence_kind": RecurrenceKind.INTERVAL_AFTER_COMPLETION,
            "recurrence_interval_preset": _INTERVAL_DAYS_TO_PRESET.get(recurrence.interval_days),
        }

    return {}


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
