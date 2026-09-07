"""Chore model, fields only, per `_docs/arch.md` §4 and issue #7.

This is the model-only slice of the Chore feature. `completed_at`/
`completed_by` were added by issue #12. `note` was added by issue #13
as a temporary home on `Chore` itself (rather than a `ChoreHistory`
row, which doesn't exist yet) for an optional note on the chore's
current/most-recent completion -- see issue #13's "Out of scope" for
the planned follow-up migration onto `ChoreHistory`. `Recurrence` was
added by issue #15 (fixed-schedule kinds only; #16 wires up
`interval_after_completion`, #17/#18 generate/propagate occurrences).
"""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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


class RecurrenceKind(models.TextChoices):
    """All five kinds from `_docs/arch.md` §4. Issue #15's forms/UI only
    expose the three ``FIXED_*`` kinds; ``INTERVAL_AFTER_COMPLETION`` is
    wired up by issue #16 -- the model carries it now so the schema is
    built once for all recurrence work.
    """

    FIXED_DAILY = "fixed_daily", "Daily"
    FIXED_WEEKLY = "fixed_weekly", "Weekly"
    FIXED_MONTHLY_DATE = "fixed_monthly_date", "Monthly (specific date)"
    FIXED_MONTHLY_RELATIVE = "fixed_monthly_relative", "Monthly (relative day)"
    INTERVAL_AFTER_COMPLETION = "interval_after_completion", "Interval after completion"


RECURRENCE_KIND_MAX_LENGTH = 30

#: Weekday encoding shared by `weekday` and `month_weekday`: 0-6 for
#: Monday-Sunday, matching Python's `date.weekday()` convention (issue
#: #15's Constraints).
MONTH_ORDINAL_CHOICES = [
    (1, "First"),
    (2, "Second"),
    (3, "Third"),
    (4, "Fourth"),
    (-1, "Last"),
]


class Recurrence(models.Model):
    """A recurrence rule attached to at most one `Chore` (issue #15).

    `chore` is the FK side, not `Chore`, so deleting a `Chore` cascades
    to delete its `Recurrence` automatically (no orphan rows to clean
    up), and `unique=True` (implied by `OneToOneField`) enforces "zero
    or one `Recurrence` per chore" at the database level.

    Only the fields relevant to `kind` may be populated; the rest must
    be null -- enforced by `clean()`, not just by the form/template
    (`_docs/arch.md` §4: business rules belong at the model/service
    layer). `interval_days` is unused by any kind this issue's forms
    expose (`interval_after_completion` is issue #16), but already
    carries its own relevance rule for when that kind is wired up.
    """

    chore = models.OneToOneField(Chore, on_delete=models.CASCADE, related_name="recurrence")
    kind = models.CharField(max_length=RECURRENCE_KIND_MAX_LENGTH, choices=RecurrenceKind.choices)
    weekday = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(6)]
    )
    month_day = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    month_ordinal = models.SmallIntegerField(null=True, blank=True, choices=MONTH_ORDINAL_CHOICES)
    month_weekday = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(6)]
    )
    interval_days = models.PositiveSmallIntegerField(null=True, blank=True)

    #: Which of the kind-specific fields are relevant (must be non-null)
    #: for a given `kind` -- every field not listed here must be null.
    FIELDS_BY_KIND = {
        RecurrenceKind.FIXED_DAILY: (),
        RecurrenceKind.FIXED_WEEKLY: ("weekday",),
        RecurrenceKind.FIXED_MONTHLY_DATE: ("month_day",),
        RecurrenceKind.FIXED_MONTHLY_RELATIVE: ("month_ordinal", "month_weekday"),
        RecurrenceKind.INTERVAL_AFTER_COMPLETION: ("interval_days",),
    }

    ALL_KIND_FIELDS = ("weekday", "month_day", "month_ordinal", "month_weekday", "interval_days")

    def __str__(self):
        return f"{self.chore.title} ({self.get_kind_display()})"

    def clean(self):
        super().clean()

        relevant = self.FIELDS_BY_KIND.get(self.kind, ())
        errors = {}

        for field_name in self.ALL_KIND_FIELDS:
            value = getattr(self, field_name)
            if field_name in relevant:
                if value is None:
                    errors[field_name] = ValidationError(
                        "This field is required for the selected recurrence kind.",
                        code="required_for_kind",
                    )
            elif value is not None:
                errors[field_name] = ValidationError(
                    "This field is not valid for the selected recurrence kind.",
                    code="not_valid_for_kind",
                )

        if errors:
            raise ValidationError(errors)
