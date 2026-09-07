"""Chore model, fields only, per `_docs/arch.md` §4 and issue #7.

This is the model-only slice of the Chore feature: `recurrence`
belongs to the recurrence issues (#15/#16) and is deliberately absent
here. `completed_at`/`completed_by` were added by issue #12. `note`
was added by issue #13 as a temporary home on `Chore` itself (rather
than a `ChoreHistory` row, which doesn't exist yet) for an optional
note on the chore's current/most-recent completion -- see issue #13's
"Out of scope" for the planned follow-up migration onto
`ChoreHistory`.
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
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        Partner,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_chores",
    )
    note = models.TextField(blank=True, default="")

    def __str__(self):
        return self.title
