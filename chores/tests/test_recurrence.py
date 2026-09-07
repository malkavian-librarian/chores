"""Tests for the `Recurrence` model and its wiring into the chore
create/edit forms and views, per issue #15.

Covers: valid `Recurrence` rows for each of the three fixed-schedule
kinds, `clean()` rejecting irrelevant fields for a given kind and
requiring the relevant ones, a kind switch clearing stale fields, the
OneToOne enforcement (a chore can't have two `Recurrence` rows), and
that setting/changing/removing recurrence never touches `chore.owner`
(or any other chore field).
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse

from chores.models import Chore, Recurrence, RecurrenceKind
from households.models import Household, Partner


def _household_with_partners(slug):
    household = Household.objects.create(slug=slug)
    alice = Partner.objects.create(household=household, name="Alice")
    bob = Partner.objects.create(household=household, name="Bob")
    return household, alice, bob


def _chore(household, owner, created_by, **kwargs):
    defaults = {
        "household": household,
        "title": "Wash dishes",
        "owner": owner,
        "created_by": created_by,
    }
    defaults.update(kwargs)
    return Chore.objects.create(**defaults)


@pytest.mark.django_db
class TestRecurrenceModel:
    # -- valid recurrence for each of the three fixed kinds --

    def test_valid_fixed_daily(self):
        household, alice, bob = _household_with_partners("rec-daily")
        chore = _chore(household, alice, bob)

        recurrence = Recurrence(chore=chore, kind=RecurrenceKind.FIXED_DAILY)
        recurrence.full_clean()
        recurrence.save()

        assert recurrence.weekday is None
        assert recurrence.month_day is None
        assert recurrence.month_ordinal is None
        assert recurrence.month_weekday is None
        assert recurrence.interval_days is None

    def test_valid_fixed_weekly(self):
        household, alice, bob = _household_with_partners("rec-weekly")
        chore = _chore(household, alice, bob)

        recurrence = Recurrence(chore=chore, kind=RecurrenceKind.FIXED_WEEKLY, weekday=5)
        recurrence.full_clean()
        recurrence.save()

        assert recurrence.weekday == 5
        assert recurrence.month_day is None
        assert recurrence.month_ordinal is None
        assert recurrence.month_weekday is None

    def test_valid_fixed_monthly_date(self):
        household, alice, bob = _household_with_partners("rec-monthly-date")
        chore = _chore(household, alice, bob)

        recurrence = Recurrence(chore=chore, kind=RecurrenceKind.FIXED_MONTHLY_DATE, month_day=15)
        recurrence.full_clean()
        recurrence.save()

        assert recurrence.month_day == 15
        assert recurrence.weekday is None
        assert recurrence.month_ordinal is None
        assert recurrence.month_weekday is None

    def test_valid_fixed_monthly_relative(self):
        household, alice, bob = _household_with_partners("rec-monthly-relative")
        chore = _chore(household, alice, bob)

        # "last Saturday" -- month_ordinal=-1, month_weekday=5.
        recurrence = Recurrence(
            chore=chore,
            kind=RecurrenceKind.FIXED_MONTHLY_RELATIVE,
            month_ordinal=-1,
            month_weekday=5,
        )
        recurrence.full_clean()
        recurrence.save()

        assert recurrence.month_ordinal == -1
        assert recurrence.month_weekday == 5
        assert recurrence.weekday is None
        assert recurrence.month_day is None

    # -- clean() rejects irrelevant/missing fields --

    def test_clean_rejects_irrelevant_field_for_weekly(self):
        household, alice, bob = _household_with_partners("rec-reject-irrelevant")
        chore = _chore(household, alice, bob)

        recurrence = Recurrence(
            chore=chore, kind=RecurrenceKind.FIXED_WEEKLY, weekday=1, month_day=10
        )

        with pytest.raises(ValidationError) as exc_info:
            recurrence.full_clean()
        assert "month_day" in exc_info.value.message_dict

    def test_clean_requires_weekday_for_weekly(self):
        household, alice, bob = _household_with_partners("rec-require-weekday")
        chore = _chore(household, alice, bob)

        recurrence = Recurrence(chore=chore, kind=RecurrenceKind.FIXED_WEEKLY)

        with pytest.raises(ValidationError) as exc_info:
            recurrence.full_clean()
        assert "weekday" in exc_info.value.message_dict

    def test_clean_requires_month_day_for_monthly_date(self):
        household, alice, bob = _household_with_partners("rec-require-month-day")
        chore = _chore(household, alice, bob)

        recurrence = Recurrence(chore=chore, kind=RecurrenceKind.FIXED_MONTHLY_DATE)

        with pytest.raises(ValidationError) as exc_info:
            recurrence.full_clean()
        assert "month_day" in exc_info.value.message_dict

    def test_clean_requires_both_fields_for_monthly_relative(self):
        household, alice, bob = _household_with_partners("rec-require-monthly-relative")
        chore = _chore(household, alice, bob)

        recurrence = Recurrence(
            chore=chore, kind=RecurrenceKind.FIXED_MONTHLY_RELATIVE, month_ordinal=1
        )

        with pytest.raises(ValidationError) as exc_info:
            recurrence.full_clean()
        assert "month_weekday" in exc_info.value.message_dict

    def test_clean_rejects_any_field_for_daily(self):
        household, alice, bob = _household_with_partners("rec-reject-daily")
        chore = _chore(household, alice, bob)

        recurrence = Recurrence(chore=chore, kind=RecurrenceKind.FIXED_DAILY, weekday=2)

        with pytest.raises(ValidationError) as exc_info:
            recurrence.full_clean()
        assert "weekday" in exc_info.value.message_dict

    # -- OneToOne enforcement --

    def test_chore_cannot_have_two_recurrence_rows(self):
        household, alice, bob = _household_with_partners("rec-onetoone")
        chore = _chore(household, alice, bob)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)

        with pytest.raises(IntegrityError):
            Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)

    def test_chore_recurrence_defaults_to_none(self):
        household, alice, bob = _household_with_partners("rec-none-default")
        chore = _chore(household, alice, bob)

        assert getattr(chore, "recurrence", None) is None

    def test_deleting_chore_deletes_its_recurrence(self):
        household, alice, bob = _household_with_partners("rec-cascade-delete")
        chore = _chore(household, alice, bob)
        recurrence = Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)

        chore.delete()

        assert not Recurrence.objects.filter(pk=recurrence.pk).exists()


@pytest.mark.django_db
class TestRecurrenceViewIntegration:
    """Tests through the chore create/edit views and forms, per issue
    #15's acceptance criteria on the UI-facing behaviour.
    """

    def _detail_url(self, household, chore):
        return reverse("chores:chore_detail", kwargs={"slug": household.slug, "chore_id": chore.pk})

    def _quick_add_url(self, household):
        return reverse("chores:quick_add", kwargs={"slug": household.slug})

    def _base_post_data(self, owner, **overrides):
        data = {"title": "Wash dishes", "owner": owner.pk}
        data.update(overrides)
        return data

    # -- create with each fixed kind via quick add --

    def test_quick_add_creates_daily_recurrence(self, client):
        household, alice, bob = _household_with_partners("qa-daily")

        response = client.post(
            self._quick_add_url(household),
            self._base_post_data(alice, recurrence_kind="fixed_daily"),
        )

        assert response.status_code == 302
        chore = Chore.objects.get(household=household)
        assert chore.recurrence.kind == RecurrenceKind.FIXED_DAILY

    def test_quick_add_creates_weekly_recurrence(self, client):
        household, alice, bob = _household_with_partners("qa-weekly")

        response = client.post(
            self._quick_add_url(household),
            self._base_post_data(alice, recurrence_kind="fixed_weekly", recurrence_weekday=2),
        )

        assert response.status_code == 302
        chore = Chore.objects.get(household=household)
        assert chore.recurrence.kind == RecurrenceKind.FIXED_WEEKLY
        assert chore.recurrence.weekday == 2

    def test_quick_add_creates_monthly_date_recurrence(self, client):
        household, alice, bob = _household_with_partners("qa-monthly-date")

        response = client.post(
            self._quick_add_url(household),
            self._base_post_data(
                alice,
                recurrence_kind="monthly",
                recurrence_monthly_mode="date",
                recurrence_month_day=3,
            ),
        )

        assert response.status_code == 302
        chore = Chore.objects.get(household=household)
        assert chore.recurrence.kind == RecurrenceKind.FIXED_MONTHLY_DATE
        assert chore.recurrence.month_day == 3

    def test_quick_add_creates_monthly_relative_recurrence(self, client):
        household, alice, bob = _household_with_partners("qa-monthly-relative")

        response = client.post(
            self._quick_add_url(household),
            self._base_post_data(
                alice,
                recurrence_kind="monthly",
                recurrence_monthly_mode="relative",
                recurrence_month_ordinal=1,
                recurrence_month_weekday=5,
            ),
        )

        assert response.status_code == 302
        chore = Chore.objects.get(household=household)
        assert chore.recurrence.kind == RecurrenceKind.FIXED_MONTHLY_RELATIVE
        assert chore.recurrence.month_ordinal == 1
        assert chore.recurrence.month_weekday == 5

    def test_quick_add_with_no_recurrence_creates_none(self, client):
        household, alice, bob = _household_with_partners("qa-none")

        response = client.post(self._quick_add_url(household), self._base_post_data(alice))

        assert response.status_code == 302
        chore = Chore.objects.get(household=household)
        assert getattr(chore, "recurrence", None) is None

    # -- form validation errors, does not save --

    def test_weekly_without_weekday_is_rejected(self, client):
        household, alice, bob = _household_with_partners("qa-weekly-missing")

        response = client.post(
            self._quick_add_url(household),
            self._base_post_data(alice, recurrence_kind="fixed_weekly"),
        )

        assert response.status_code == 200
        assert not Chore.objects.filter(household=household).exists()

    def test_monthly_without_submode_is_rejected(self, client):
        household, alice, bob = _household_with_partners("qa-monthly-missing")

        response = client.post(
            self._quick_add_url(household),
            self._base_post_data(alice, recurrence_kind="monthly"),
        )

        assert response.status_code == 200
        assert not Chore.objects.filter(household=household).exists()

    # -- edit: kind switch clears stale fields --

    def test_editing_weekly_to_daily_clears_weekday(self, client):
        household, alice, bob = _household_with_partners("edit-weekly-to-daily")
        chore = _chore(household, alice, bob)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_WEEKLY, weekday=3)

        response = client.post(
            self._detail_url(household, chore),
            self._base_post_data(alice, recurrence_kind="fixed_daily"),
        )

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.recurrence.kind == RecurrenceKind.FIXED_DAILY
        assert chore.recurrence.weekday is None

    def test_editing_monthly_date_to_monthly_relative_clears_month_day(self, client):
        household, alice, bob = _household_with_partners("edit-monthly-switch")
        chore = _chore(household, alice, bob)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_MONTHLY_DATE, month_day=10)

        response = client.post(
            self._detail_url(household, chore),
            self._base_post_data(
                alice,
                recurrence_kind="monthly",
                recurrence_monthly_mode="relative",
                recurrence_month_ordinal=4,
                recurrence_month_weekday=0,
            ),
        )

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.recurrence.kind == RecurrenceKind.FIXED_MONTHLY_RELATIVE
        assert chore.recurrence.month_day is None
        assert chore.recurrence.month_ordinal == 4
        assert chore.recurrence.month_weekday == 0

    # -- removing recurrence --

    def test_removing_recurrence_deletes_row_without_affecting_other_fields(self, client):
        household, alice, bob = _household_with_partners("edit-remove-recurrence")
        chore = _chore(household, alice, bob, description="Keep me")
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)

        response = client.post(
            self._detail_url(household, chore),
            self._base_post_data(alice, description="Keep me"),
        )

        assert response.status_code == 302
        chore.refresh_from_db()
        assert getattr(chore, "recurrence", None) is None
        assert chore.description == "Keep me"

    # -- owner untouched by setting/changing/removing recurrence --

    def test_setting_recurrence_does_not_change_owner(self, client):
        household, alice, bob = _household_with_partners("owner-unchanged-set")
        chore = _chore(household, alice, bob)

        client.post(
            self._detail_url(household, chore),
            self._base_post_data(alice, recurrence_kind="fixed_daily"),
        )

        chore.refresh_from_db()
        assert chore.owner == alice

    def test_changing_recurrence_does_not_change_owner(self, client):
        household, alice, bob = _household_with_partners("owner-unchanged-change")
        chore = _chore(household, alice, bob)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)

        client.post(
            self._detail_url(household, chore),
            self._base_post_data(alice, recurrence_kind="fixed_weekly", recurrence_weekday=0),
        )

        chore.refresh_from_db()
        assert chore.owner == alice

    def test_removing_recurrence_does_not_change_owner(self, client):
        household, alice, bob = _household_with_partners("owner-unchanged-remove")
        chore = _chore(household, alice, bob)
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)

        client.post(self._detail_url(household, chore), self._base_post_data(alice))

        chore.refresh_from_db()
        assert chore.owner == alice
