"""Chore model, fields only, per `_docs/arch.md` §4 and issue #7.

This is the model-only slice of the Chore feature: `recurrence`,
`completed_at`, and `completed_by` belong to the recurrence/completion
issues (#15, #16, #12) and are deliberately absent here.
"""

from django.db import models

from categories.models import Category
from households.models import Household, Partner

TITLE_MAX_LENGTH = 200
STATUS_MAX_LENGTH = 20


class ChoreStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"


class Chore(models.Model):
    """A household chore, owned by one partner and optionally categorized.

    Fields are the contract from `_docs/arch.md` §4, minus the
    recurrence/completion fields carved out to later issues. `owner`
    and `created_by` are independent FKs to `Partner` — no constraint
    forces them to be the same partner, per `plan.md` §5.

    `owner`/`created_by` use `on_delete=CASCADE` because no feature
    exists to delete a `Partner` (there are always exactly two per
    household, per `_docs/arch.md` §4) — this path is currently
    unreachable. `category` uses `on_delete=SET_NULL` per issue #6's
    decision, exercised for the first time here since this is the
    first model that can reference a `Category`.
    """

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="chores")
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name="owned_chores")
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chores",
    )
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name="created_chores")
    status = models.CharField(
        max_length=STATUS_MAX_LENGTH,
        choices=ChoreStatus.choices,
        default=ChoreStatus.ACTIVE,
    )

    def __str__(self):
        return self.title
