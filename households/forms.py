"""Plain Django forms for the `households` app, per `_docs/arch.md` §1/§12.

No REST API, no client-side JS framework — a full-page GET/POST must work
without HTMX.
"""

from django import forms

from .models import PARTNER_NAME_MAX_LENGTH


class PartnerNamingForm(forms.Form):
    """First-launch form collecting both partners' names at once.

    Both fields are required, trimmed of surrounding whitespace, capped at
    `PARTNER_NAME_MAX_LENGTH`, and whitespace-only input is rejected the
    same as blank input. Duplicate names across the two fields are allowed
    (see issue #3 acceptance criteria).
    """

    partner_1_name = forms.CharField(
        label="Partner 1 name",
        max_length=PARTNER_NAME_MAX_LENGTH,
        strip=True,
    )
    partner_2_name = forms.CharField(
        label="Partner 2 name",
        max_length=PARTNER_NAME_MAX_LENGTH,
        strip=True,
    )


class PartnerRenameForm(forms.Form):
    """Settings-page form for renaming both partners at once (issue #19).

    Both fields are required, trimmed of surrounding whitespace, capped at
    `PARTNER_NAME_MAX_LENGTH`, and whitespace-only input is rejected the
    same as blank input -- same validation pattern as `PartnerNamingForm`.
    Duplicate names across the two fields (or a no-op rename back to the
    same current name) are allowed (see issue #3 acceptance criteria).
    """

    partner_1_name = forms.CharField(
        label="Partner 1 name",
        max_length=PARTNER_NAME_MAX_LENGTH,
        strip=True,
    )
    partner_2_name = forms.CharField(
        label="Partner 2 name",
        max_length=PARTNER_NAME_MAX_LENGTH,
        strip=True,
    )


class ResetDataForm(forms.Form):
    """Settings-page "Reset data" checkboxes (issue #20).

    Exactly three independent, unchecked-by-default options -- no
    "select all" shortcut, per issue #20's Constraints. All fields are
    optional booleans: submitting with zero boxes checked is a valid,
    accepted no-op rather than a validation error.

    The same form class renders the initial checkboxes (on the Settings
    page) and re-validates the selection carried forward as hidden
    fields on the confirmation page's POST, so both steps agree on the
    exact set of valid option names.
    """

    active_chores = forms.BooleanField(label="Active chores", required=False)
    completed_history = forms.BooleanField(label="Completed history", required=False)
    custom_categories = forms.BooleanField(label="Custom categories", required=False)
