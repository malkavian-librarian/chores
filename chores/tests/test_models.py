import datetime

import pytest
from django.core.exceptions import ValidationError

from categories.models import Category
from chores.models import Chore, ChoreStatus
from households.models import Household, Partner


@pytest.mark.django_db
class TestChoreModel:
    def _household_with_partners(self, slug):
        household = Household.objects.create(slug=slug)
        alice = Partner.objects.create(household=household, name="Alice")
        bob = Partner.objects.create(household=household, name="Bob")
        return household, alice, bob

    def test_create_valid_chore_is_retrievable(self):
        household, alice, bob = self._household_with_partners("chore-valid")

        chore = Chore.objects.create(
            household=household,
            title="Wash dishes",
            owner=alice,
            created_by=bob,
        )

        fetched = Chore.objects.get(pk=chore.pk)
        assert fetched.title == "Wash dishes"
        assert fetched.household == household
        assert fetched.owner == alice
        assert fetched.created_by == bob

    def test_title_is_required(self):
        household, alice, bob = self._household_with_partners("chore-title-required")

        chore = Chore(household=household, title="", owner=alice, created_by=bob)

        with pytest.raises(ValidationError):
            chore.full_clean()

    def test_category_is_nullable(self):
        household, alice, bob = self._household_with_partners("chore-category-nullable")

        chore = Chore.objects.create(
            household=household,
            title="Take out trash",
            owner=alice,
            created_by=bob,
            category=None,
        )

        assert chore.category is None

    def test_deleting_category_sets_null_on_chore(self):
        household, alice, bob = self._household_with_partners("chore-category-set-null")
        category = Category.objects.create(household=household, name="Kitchen")

        chore = Chore.objects.create(
            household=household,
            title="Clean counters",
            owner=alice,
            created_by=bob,
            category=category,
        )

        category.delete()
        chore.refresh_from_db()

        assert chore.category is None
        assert Chore.objects.filter(pk=chore.pk).exists()

    def test_owner_and_created_by_can_differ(self):
        household, alice, bob = self._household_with_partners("chore-owner-created-by-differ")

        chore = Chore.objects.create(
            household=household,
            title="Mow the lawn",
            owner=bob,
            created_by=alice,
        )

        assert chore.owner == bob
        assert chore.created_by == alice
        assert chore.owner != chore.created_by

    def test_status_defaults_to_active(self):
        household, alice, bob = self._household_with_partners("chore-status-default")

        chore = Chore.objects.create(
            household=household,
            title="Water plants",
            owner=alice,
            created_by=bob,
        )

        assert chore.status == ChoreStatus.ACTIVE

    def test_str_returns_title(self):
        household, alice, bob = self._household_with_partners("chore-str")

        chore = Chore.objects.create(
            household=household,
            title="Vacuum living room",
            owner=alice,
            created_by=bob,
        )

        assert str(chore) == "Vacuum living room"

    def test_due_date_and_description_optional(self):
        household, alice, bob = self._household_with_partners("chore-optional-fields")

        chore = Chore.objects.create(
            household=household,
            title="Organize garage",
            owner=alice,
            created_by=bob,
        )

        assert chore.description == ""
        assert chore.due_date is None

    def test_due_date_can_be_set(self):
        household, alice, bob = self._household_with_partners("chore-due-date")

        chore = Chore.objects.create(
            household=household,
            title="Pay bills",
            owner=alice,
            created_by=bob,
            due_date=datetime.date(2026, 1, 1),
        )

        assert chore.due_date == datetime.date(2026, 1, 1)
