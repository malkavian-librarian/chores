"""Tests for issue #17: generating a recurring chore's next occurrence
on completion.

Two layers, per `_docs/arch.md` §7's model/service-heavy, view-light
pyramid:

- `TestComputeNextDueDate` -- pure date-math unit tests for
  `chores.recurrence.compute_next_due_date`, one per recurrence kind
  plus every edge case called out in the issue (month-end clamping
  across 30/31-day months and both leap/non-leap February, weekly
  "today matches but must still jump forward", monthly-relative
  crossing a month boundary, and `month_ordinal=-1`).
- `TestNextOccurrenceIntegration` -- through `chore_complete`/
  `chore_undo`, covering: exactly one correctly-configured new `Chore`
  and cloned `Recurrence` on completing a recurring chore; no new row
  for a non-recurring chore; Undo removing both the reversion and the
  generated chore; the old completed chore still showing correctly in
  issue #14's Completed section afterward.
"""

from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from chores.models import Chore, ChoreStatus, Recurrence, RecurrenceKind
from chores.recurrence import compute_next_due_date
from households.models import Household, Partner
from households.views import _acting_as_session_key


def _aware(year, month, day, hour=12):
    """A timezone-aware `datetime` on the given local calendar date, at
    a mid-day hour so it's nowhere near a local-midnight DST boundary.
    """
    return timezone.make_aware(datetime(year, month, day, hour, 0, 0))


class _FakeRecurrence:
    """A plain stand-in for a `Recurrence` row -- `compute_next_due_date`
    only reads attributes off it, so a lightweight namespace avoids a
    database hit for the pure date-math tests.
    """

    def __init__(self, kind, **fields):
        self.kind = kind
        self.weekday = fields.get("weekday")
        self.month_day = fields.get("month_day")
        self.month_ordinal = fields.get("month_ordinal")
        self.month_weekday = fields.get("month_weekday")
        self.interval_days = fields.get("interval_days")


class TestComputeNextDueDate:
    # -- fixed_daily --

    def test_fixed_daily_adds_one_day(self):
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_DAILY)
        completed_at = _aware(2026, 3, 10)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 3, 11)

    def test_fixed_daily_crosses_month_boundary(self):
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_DAILY)
        completed_at = _aware(2026, 1, 31)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 2, 1)

    # -- fixed_weekly --

    def test_fixed_weekly_next_matching_weekday(self):
        # 2026-03-10 is a Tuesday (weekday=1); next Friday (weekday=4).
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_WEEKLY, weekday=4)
        completed_at = _aware(2026, 3, 10)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 3, 13)

    def test_fixed_weekly_today_matches_jumps_full_week(self):
        # 2026-03-11 is a Wednesday; weekday=Wednesday must yield +7,
        # never +0 -- the issue's explicitly called-out edge case.
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_WEEKLY, weekday=2)
        completed_at = _aware(2026, 3, 11)

        result = compute_next_due_date(recurrence, completed_at)

        assert result == date(2026, 3, 18)
        assert result != date(2026, 3, 11)

    # -- fixed_monthly_date --

    def test_fixed_monthly_date_plain(self):
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_MONTHLY_DATE, month_day=15)
        completed_at = _aware(2026, 3, 1)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 4, 15)

    def test_fixed_monthly_date_clamped_into_30_day_month(self):
        # Completed in March (31 days); next month is April (30 days).
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_MONTHLY_DATE, month_day=31)
        completed_at = _aware(2026, 3, 5)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 4, 30)

    def test_fixed_monthly_date_clamped_into_february_non_leap_year(self):
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_MONTHLY_DATE, month_day=31)
        completed_at = _aware(2026, 1, 5)  # 2026 is not a leap year.

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 2, 28)

    def test_fixed_monthly_date_clamped_into_february_leap_year(self):
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_MONTHLY_DATE, month_day=31)
        completed_at = _aware(2028, 1, 5)  # 2028 is a leap year.

        assert compute_next_due_date(recurrence, completed_at) == date(2028, 2, 29)

    def test_fixed_monthly_date_no_clamping_needed(self):
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_MONTHLY_DATE, month_day=10)
        completed_at = _aware(2026, 1, 5)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 2, 10)

    def test_fixed_monthly_date_wraps_year_boundary(self):
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_MONTHLY_DATE, month_day=5)
        completed_at = _aware(2026, 12, 20)

        assert compute_next_due_date(recurrence, completed_at) == date(2027, 1, 5)

    # -- fixed_monthly_relative --

    def test_fixed_monthly_relative_first_saturday(self):
        # Completed in March 2026 -> generate for April 2026.
        # April 2026's first Saturday (weekday=5) is 2026-04-04.
        recurrence = _FakeRecurrence(
            RecurrenceKind.FIXED_MONTHLY_RELATIVE, month_ordinal=1, month_weekday=5
        )
        completed_at = _aware(2026, 3, 15)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 4, 4)

    def test_fixed_monthly_relative_crosses_month_boundary_into_first_week(self):
        # Completed in April 2026 -> generate for May 2026. May 2026
        # starts on a Friday, so the first Saturday (weekday=5) falls
        # on 2026-05-02, in the first days of the month.
        recurrence = _FakeRecurrence(
            RecurrenceKind.FIXED_MONTHLY_RELATIVE, month_ordinal=1, month_weekday=5
        )
        completed_at = _aware(2026, 4, 20)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 5, 2)

    def test_fixed_monthly_relative_second_tuesday(self):
        # Generate for April 2026. April 2026's Tuesdays: 7, 14, 21, 28.
        recurrence = _FakeRecurrence(
            RecurrenceKind.FIXED_MONTHLY_RELATIVE, month_ordinal=2, month_weekday=1
        )
        completed_at = _aware(2026, 3, 1)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 4, 14)

    def test_fixed_monthly_relative_last_occurrence(self):
        # Generate for April 2026. April 2026's last Thursday
        # (weekday=3): April has 30 days; April 30 2026 is a Thursday.
        recurrence = _FakeRecurrence(
            RecurrenceKind.FIXED_MONTHLY_RELATIVE, month_ordinal=-1, month_weekday=3
        )
        completed_at = _aware(2026, 3, 1)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 4, 30)

    def test_fixed_monthly_relative_last_occurrence_not_on_last_day(self):
        # Generate for May 2026 (31 days, ends on a Sunday). Last
        # Monday (weekday=0) of May 2026 is May 25, not May 31.
        recurrence = _FakeRecurrence(
            RecurrenceKind.FIXED_MONTHLY_RELATIVE, month_ordinal=-1, month_weekday=0
        )
        completed_at = _aware(2026, 4, 1)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 5, 25)

    # -- interval_after_completion --

    def test_interval_after_completion_adds_interval_days(self):
        recurrence = _FakeRecurrence(RecurrenceKind.INTERVAL_AFTER_COMPLETION, interval_days=14)
        completed_at = _aware(2026, 3, 10)

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 3, 24)

    def test_interval_after_completion_crosses_month_and_year_boundary(self):
        recurrence = _FakeRecurrence(RecurrenceKind.INTERVAL_AFTER_COMPLETION, interval_days=30)
        completed_at = _aware(2026, 12, 15)

        assert compute_next_due_date(recurrence, completed_at) == date(2027, 1, 14)

    # -- uses timezone.localdate, not a naive .date() --

    def test_uses_localdate_not_naive_utc_date(self, settings):
        # A UTC time just after local midnight in a UTC-behind timezone
        # falls on the *previous* local calendar date -- a naive
        # `.date()` call would get this wrong.
        settings.TIME_ZONE = "America/New_York"
        recurrence = _FakeRecurrence(RecurrenceKind.FIXED_DAILY)
        # 2026-03-10 00:30 UTC == 2026-03-09 19:30 in America/New_York.
        completed_at = datetime(2026, 3, 10, 0, 30, tzinfo=timezone.get_fixed_timezone(0))

        assert compute_next_due_date(recurrence, completed_at) == date(2026, 3, 10)


@pytest.mark.django_db
class TestNextOccurrenceIntegration:
    def _household_with_partners(self, slug):
        household = Household.objects.create(slug=slug)
        alice = Partner.objects.create(household=household, name="Alice")
        bob = Partner.objects.create(household=household, name="Bob")
        return household, alice, bob

    def _chore(self, household, owner, created_by, **kwargs):
        defaults = {
            "household": household,
            "title": "Wash dishes",
            "description": "Use the good sponge",
            "owner": owner,
            "created_by": created_by,
        }
        defaults.update(kwargs)
        return Chore.objects.create(**defaults)

    def _complete_url(self, household, chore):
        return reverse(
            "chores:chore_complete", kwargs={"slug": household.slug, "chore_id": chore.pk}
        )

    def _undo_url(self, household, chore):
        return reverse("chores:chore_undo", kwargs={"slug": household.slug, "chore_id": chore.pk})

    def _act_as(self, client, household, partner):
        session = client.session
        session[_acting_as_session_key(household.slug)] = partner.pk
        session.save()

    def test_completing_recurring_chore_creates_next_occurrence(self, client):
        household, alice, bob = self._household_with_partners("gen-creates-occurrence")
        chore = self._chore(household, owner=alice, created_by=bob)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))

        chore.refresh_from_db()
        next_chores = Chore.objects.exclude(pk=chore.pk)
        assert next_chores.count() == 1
        next_chore = next_chores.get()

        assert next_chore.household == household
        assert next_chore.owner == alice
        assert next_chore.created_by == bob
        assert next_chore.title == chore.title
        assert next_chore.description == chore.description
        assert next_chore.category == chore.category
        assert next_chore.status == ChoreStatus.ACTIVE
        assert next_chore.completed_at is None
        assert next_chore.completed_by is None
        assert next_chore.note == ""
        assert next_chore.due_date == timezone.localdate(chore.completed_at) + timedelta(days=1)

    def test_generated_occurrence_has_its_own_cloned_recurrence_row(self, client):
        household, alice, bob = self._household_with_partners("gen-clones-recurrence")
        chore = self._chore(household, owner=alice, created_by=alice)
        Recurrence.objects.create(
            chore=chore,
            kind=RecurrenceKind.FIXED_MONTHLY_RELATIVE,
            month_ordinal=-1,
            month_weekday=5,
        )
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))

        next_chore = Chore.objects.exclude(pk=chore.pk).get()
        assert next_chore.recurrence.pk != chore.recurrence.pk
        assert next_chore.recurrence.kind == RecurrenceKind.FIXED_MONTHLY_RELATIVE
        assert next_chore.recurrence.month_ordinal == -1
        assert next_chore.recurrence.month_weekday == 5
        assert next_chore.recurrence.weekday is None
        assert next_chore.recurrence.month_day is None
        assert next_chore.recurrence.interval_days is None

    def test_completing_non_recurring_chore_creates_no_new_row(self, client):
        household, alice, bob = self._household_with_partners("gen-no-recurrence-no-row")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))

        assert Chore.objects.count() == 1

    def test_undo_removes_both_reversion_and_generated_chore(self, client):
        household, alice, bob = self._household_with_partners("gen-undo-removes-both")
        chore = self._chore(household, owner=alice, created_by=alice)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        generated_chore = Chore.objects.exclude(pk=chore.pk).get()

        response = client.post(self._undo_url(household, chore))

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.status == ChoreStatus.ACTIVE
        assert chore.completed_at is None
        assert chore.completed_by is None
        assert not Chore.objects.filter(pk=generated_chore.pk).exists()
        assert Chore.objects.count() == 1

    def test_undo_removes_generated_chores_recurrence_via_cascade(self, client):
        household, alice, bob = self._household_with_partners("gen-undo-cascades-recurrence")
        chore = self._chore(household, owner=alice, created_by=alice)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        generated_chore = Chore.objects.exclude(pk=chore.pk).get()
        generated_recurrence_id = generated_chore.recurrence.pk

        client.post(self._undo_url(household, chore))

        assert not Recurrence.objects.filter(pk=generated_recurrence_id).exists()

    def test_undo_on_non_recurring_completion_does_not_error(self, client):
        household, alice, bob = self._household_with_partners("gen-undo-no-recurrence")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        response = client.post(self._undo_url(household, chore))

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.status == ChoreStatus.ACTIVE
        assert Chore.objects.count() == 1

    # -- editing recurrence before completion is picked up by the next
    # occurrence, and never touches already-completed history (issue #18) --

    def test_editing_recurrence_before_completion_uses_new_rule_for_next_occurrence(self, client):
        """#18's second acceptance criterion: edit a recurring chore's
        rule via `chore_detail` (weekly Monday -> weekly Friday), then
        complete it, and assert the generated next occurrence's
        `due_date` matches what the *new* rule produces -- not what the
        old rule would have produced. Monday and Friday can never
        compute to the same next date within a 7-day window, so this
        would fail outright if a stale/cached recurrence were read
        instead of the current row.
        """
        household, alice, bob = self._household_with_partners("edit-then-complete-new-rule")
        chore = self._chore(household, owner=alice, created_by=alice)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_WEEKLY, weekday=0)  # Mon
        self._act_as(client, household, alice)

        edit_url = reverse(
            "chores:chore_detail", kwargs={"slug": household.slug, "chore_id": chore.pk}
        )
        edit_response = client.post(
            edit_url,
            {
                "title": chore.title,
                "description": chore.description,
                "owner": alice.pk,
                "recurrence_kind": "fixed_weekly",
                "recurrence_weekday": 4,  # Friday
            },
        )
        assert edit_response.status_code == 302
        chore.refresh_from_db()
        assert chore.recurrence.weekday == 4  # edit landed before completion

        client.post(self._complete_url(household, chore))

        chore.refresh_from_db()
        next_chore = Chore.objects.exclude(pk=chore.pk).get()

        old_rule = _FakeRecurrence(RecurrenceKind.FIXED_WEEKLY, weekday=0)
        new_rule = _FakeRecurrence(RecurrenceKind.FIXED_WEEKLY, weekday=4)
        due_date_under_old_rule = compute_next_due_date(old_rule, chore.completed_at)
        due_date_under_new_rule = compute_next_due_date(new_rule, chore.completed_at)

        # Sanity check that this scenario is actually discriminating.
        assert due_date_under_old_rule != due_date_under_new_rule

        assert next_chore.due_date == due_date_under_new_rule
        assert next_chore.recurrence.kind == RecurrenceKind.FIXED_WEEKLY
        assert next_chore.recurrence.weekday == 4

    def test_editing_generated_occurrences_recurrence_does_not_touch_completed_history(
        self, client
    ):
        """#18's third acceptance criterion: after completing a
        recurring chore (producing a completed chore plus a freshly
        generated active occurrence), editing the *new* occurrence's
        recurrence must not retroactively change the already-completed
        chore's `due_date`, `completed_at`, `completed_by`, or `status`.
        """
        household, alice, bob = self._household_with_partners("edit-new-occurrence-no-history")
        chore = self._chore(household, owner=alice, created_by=alice)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        chore.refresh_from_db()
        original_due_date = chore.due_date
        original_completed_at = chore.completed_at
        original_completed_by_id = chore.completed_by_id
        original_status = chore.status

        next_chore = Chore.objects.exclude(pk=chore.pk).get()
        edit_url = reverse(
            "chores:chore_detail", kwargs={"slug": household.slug, "chore_id": next_chore.pk}
        )
        edit_response = client.post(
            edit_url,
            {
                "title": next_chore.title,
                "description": next_chore.description,
                "owner": alice.pk,
                "recurrence_kind": "fixed_weekly",
                "recurrence_weekday": 2,
            },
        )
        assert edit_response.status_code == 302
        next_chore.refresh_from_db()
        assert next_chore.recurrence.kind == RecurrenceKind.FIXED_WEEKLY  # edit landed

        chore.refresh_from_db()
        assert chore.due_date == original_due_date
        assert chore.completed_at == original_completed_at
        assert chore.completed_by_id == original_completed_by_id
        assert chore.status == original_status

    def test_old_completed_chore_still_shows_in_completed_section(self, client):
        household, alice, bob = self._household_with_partners("gen-old-chore-in-completed")
        chore = self._chore(household, owner=alice, created_by=alice)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        chore.refresh_from_db()

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))
        content = response.content.decode()

        # The completed-chore title still appears on the page (in the
        # Completed section) even though the generated occurrence
        # shares the same title and sits in the active list -- checked
        # by id, not title, since both chores are named "Wash dishes".
        assert chore.title in content
        active_ids = [c.pk for c in response.context["active_chores"]]
        assert chore.pk not in active_ids
