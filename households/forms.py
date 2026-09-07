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
