"""Category model and predefined seeding, per `_docs/arch.md` §4 and
issue #5.

Predefined categories are seeded per household on creation (see
`seed_predefined_categories` in `categories/services.py`, called from
`Household.create_with_unique_slug`); either partner can add/rename/
delete custom ones later (#6).
"""

from django.db import models

from households.models import Household

CATEGORY_NAME_MAX_LENGTH = 100

# Fixed data for issue #5 — hardcoded here rather than a fixture or
# admin-editable table. Order matters: this is the order rows are
# seeded in and the order the bare listing page renders them in.
PREDEFINED_CATEGORY_NAMES = [
    "Kitchen",
    "Bathroom",
    "Bedroom",
    "Living Room",
    "Laundry",
    "Outdoor",
    "Pet Care",
    "Shopping & Errands",
    "General",
]


class Category(models.Model):
    """A chore category, owned by exactly one household.

    Fields are the contract from `_docs/arch.md` §4 — `household`,
    `name`, and `is_predefined` only.
    """

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=CATEGORY_NAME_MAX_LENGTH)
    is_predefined = models.BooleanField(default=False)

    def __str__(self):
        return self.name
