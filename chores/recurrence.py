"""Pure date-math for computing a recurring chore's next occurrence,
per issue #17.

`compute_next_due_date` is intentionally kept free of any Django ORM
writes or session/view concerns -- it takes a `Recurrence` instance and
a completion timestamp, and returns a plain `datetime.date`. That keeps
it trivially unit-testable (see `chores/tests/test_next_occurrence.py`)
and reusable from `chore_complete` (issue #17) and, later, from #18's
edit-propagation code without dragging view/session logic along.

Only the standard library (`datetime`, `calendar`) is used for the date
math, per `_docs/arch.md` §1/§12's minimal-dependencies stance -- no
third-party date library.
"""

import calendar
from datetime import date, timedelta

from .models import RecurrenceKind


def _add_month(year, month):
    """Return `(year, month)` for the calendar month after `(year, month)`."""
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _clamped_month_day(year, month, day):
    """`day` in `(year, month)`, clamped to that month's last valid day
    (e.g. `31` in a 30-day month, or in February) per the
    `fixed_monthly_date` acceptance criterion.
    """
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _nth_weekday_of_month(year, month, weekday, ordinal):
    """The `ordinal`-th occurrence of `weekday` (0=Monday..6=Sunday, per
    issue #15's convention) in `(year, month)`, or the *last* occurrence
    if `ordinal == -1`.

    A positive `ordinal` (1-4) with no such occurrence in the month is
    out of scope per issue #17's "Out of scope" section -- forms are
    responsible for only ever storing combinations that exist in *some*
    month, not every month, so this may raise (a `ValueError` from
    constructing an invalid `date`) rather than validate defensively.
    """
    if ordinal == -1:
        last_day_num = calendar.monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)
        days_back = (last_day.weekday() - weekday) % 7
        return last_day - timedelta(days=days_back)

    first_day = date(year, month, 1)
    days_until_first = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day + timedelta(days=days_until_first)
    return first_occurrence + timedelta(days=7 * (ordinal - 1))


def compute_next_due_date(recurrence, completed_at):
    """Compute the next `due_date` (a `date`) for a new occurrence of a
    recurring chore, given its `Recurrence` rule and the `completed_at`
    timestamp of the just-finished occurrence.

    `completed_at` is converted to a local calendar date via
    `django.utils.timezone.localdate`, never a naive `.date()` call, per
    issue #17's acceptance criteria (consistent with issue #10's
    `timezone.localdate()` convention -- avoids UTC-vs-local off-by-one
    errors near local midnight).
    """
    from django.utils import timezone

    completed_date = timezone.localdate(completed_at)
    kind = recurrence.kind

    if kind == RecurrenceKind.FIXED_DAILY:
        return completed_date + timedelta(days=1)

    if kind == RecurrenceKind.FIXED_WEEKLY:
        # Strictly after completed_date, even if completed_date itself
        # is already on `weekday` -- (weekday - completed_date.weekday())
        # % 7 would give 0 in that case, so a plain %7 is wrong; forcing
        # a range of 1..7 guarantees "always in the future, never +0".
        days_ahead = (recurrence.weekday - completed_date.weekday() - 1) % 7 + 1
        return completed_date + timedelta(days=days_ahead)

    if kind == RecurrenceKind.FIXED_MONTHLY_DATE:
        next_year, next_month = _add_month(completed_date.year, completed_date.month)
        return _clamped_month_day(next_year, next_month, recurrence.month_day)

    if kind == RecurrenceKind.FIXED_MONTHLY_RELATIVE:
        next_year, next_month = _add_month(completed_date.year, completed_date.month)
        return _nth_weekday_of_month(
            next_year, next_month, recurrence.month_weekday, recurrence.month_ordinal
        )

    if kind == RecurrenceKind.INTERVAL_AFTER_COMPLETION:
        return completed_date + timedelta(days=recurrence.interval_days)

    raise ValueError(f"Unknown recurrence kind: {kind!r}")
