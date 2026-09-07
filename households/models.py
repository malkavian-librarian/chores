"""Household model and slug-based identity, per `_docs/arch.md` §2/§4.

No accounts, no password: the unguessable slug in the URL/session is the
only identity a visitor has for their household.
"""

import secrets

from django.db import IntegrityError, models, transaction

# `token_urlsafe(9)` yields 12 base64url characters; give the column a
# little headroom rather than sizing it to the exact current output.
SLUG_MAX_LENGTH = 32
SLUG_BYTES = 9
MAX_SLUG_ATTEMPTS = 5

PARTNER_NAME_MAX_LENGTH = 100


class Household(models.Model):
    """A household, identified only by an unguessable slug.

    Fields are the contract from `_docs/arch.md` §4 — `slug` and
    `created_at` only, nothing else.
    """

    slug = models.CharField(max_length=SLUG_MAX_LENGTH, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.slug

    @classmethod
    def create_with_unique_slug(cls):
        """Create a Household with a fresh `secrets.token_urlsafe(9)` slug.

        Slug collisions are astronomically unlikely but not impossible, so
        this retries generation up to `MAX_SLUG_ATTEMPTS` times on a unique
        constraint violation before giving up (per the collision policy
        decided in issue #2) rather than letting a bare `IntegrityError`
        bubble up and break the homepage for a real visitor.
        """
        # Imported locally (not at module level) to avoid a circular
        # import: `categories.models` imports `Household` from this
        # module.
        from categories.services import seed_predefined_categories

        last_error = None
        for _ in range(MAX_SLUG_ATTEMPTS):
            slug = secrets.token_urlsafe(SLUG_BYTES)
            try:
                with transaction.atomic():
                    household = cls.objects.create(slug=slug)
                    seed_predefined_categories(household)
                    return household
            except IntegrityError as exc:
                last_error = exc
                continue
        raise RuntimeError(
            f"Could not generate a unique household slug after {MAX_SLUG_ATTEMPTS} attempts"
        ) from last_error


class Partner(models.Model):
    """One of the two people in a household, per `_docs/arch.md` §4.

    Exactly two are created together during first-launch onboarding
    (see `households/forms.py` and the `detail` view). Duplicate names
    within a household are deliberately allowed — see issue #3.
    """

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="partners")
    name = models.CharField(max_length=PARTNER_NAME_MAX_LENGTH)

    def __str__(self):
        return self.name
