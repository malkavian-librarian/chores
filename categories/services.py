"""Category services — explicit calls rather than signal coupling.

Per `_docs/arch.md` §3, cross-app behaviour flows through plain Python
functions in a `services.py`, not signals: a `post_save` signal on
`Household` would fire on every `Household.objects.create()` call
(tests, fixtures, admin) with no way to opt out.
"""

from .models import PREDEFINED_CATEGORY_NAMES, Category


def seed_predefined_categories(household):
    """Create the 9 predefined `Category` rows for a newly created
    household, in the fixed `PREDEFINED_CATEGORY_NAMES` order.

    Must be called from within the same `transaction.atomic()` block as
    the `Household` row's creation (see
    `Household.create_with_unique_slug`) so a failure here rolls back
    the household too.
    """
    Category.objects.bulk_create(
        [
            Category(household=household, name=name, is_predefined=True)
            for name in PREDEFINED_CATEGORY_NAMES
        ]
    )
