import pytest

from categories.models import PREDEFINED_CATEGORY_NAMES, Category
from categories.services import seed_predefined_categories
from households.models import Household


@pytest.mark.django_db
class TestSeedPredefinedCategories:
    def test_creates_nine_predefined_categories(self):
        household = Household.objects.create(slug="seed-service")

        seed_predefined_categories(household)

        categories = list(household.categories.order_by("pk"))
        assert len(categories) == 9
        assert [c.name for c in categories] == PREDEFINED_CATEGORY_NAMES
        assert all(c.is_predefined for c in categories)


@pytest.mark.django_db
class TestHouseholdCreationSeedsCategories:
    def test_create_with_unique_slug_seeds_nine_categories(self):
        household = Household.create_with_unique_slug()

        categories = list(household.categories.order_by("pk"))
        assert len(categories) == 9
        assert [c.name for c in categories] == PREDEFINED_CATEGORY_NAMES
        assert all(c.is_predefined for c in categories)

    def test_two_households_have_independent_category_rows(self):
        household_1 = Household.create_with_unique_slug()
        household_2 = Household.create_with_unique_slug()

        categories_1 = list(household_1.categories.all())
        categories_2 = list(household_2.categories.all())

        pks_1 = {c.pk for c in categories_1}
        pks_2 = {c.pk for c in categories_2}
        assert pks_1.isdisjoint(pks_2)
        assert {c.name for c in categories_1} == {c.name for c in categories_2}
        assert Category.objects.filter(household__isnull=True).count() == 0

    def test_no_global_categories_exist(self):
        Household.create_with_unique_slug()

        assert Category.objects.filter(household__isnull=True).count() == 0

    def test_failure_seeding_categories_rolls_back_household(self, monkeypatch):
        """Seeding runs inside the same atomic block as Household
        creation, so a failure there must roll back the Household row
        too — no household is ever left with zero categories."""

        def boom(household):
            raise RuntimeError("seeding exploded")

        monkeypatch.setattr("categories.services.seed_predefined_categories", boom)

        with pytest.raises(RuntimeError):
            Household.create_with_unique_slug()

        assert Household.objects.filter(slug__isnull=False).count() == 0
        assert Category.objects.count() == 0
