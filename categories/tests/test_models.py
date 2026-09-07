import pytest

from categories.models import PREDEFINED_CATEGORY_NAMES, Category
from households.models import Household


@pytest.mark.django_db
class TestCategoryModel:
    def test_fields(self):
        household = Household.objects.create(slug="category-fields")

        category = Category.objects.create(household=household, name="Kitchen", is_predefined=True)

        assert category.household == household
        assert category.name == "Kitchen"
        assert category.is_predefined is True

    def test_is_predefined_defaults_false(self):
        household = Household.objects.create(slug="category-default-predefined")

        category = Category.objects.create(household=household, name="Custom")

        assert category.is_predefined is False

    def test_related_name_is_categories(self):
        household = Household.objects.create(slug="category-related-name")
        Category.objects.create(household=household, name="Kitchen", is_predefined=True)
        Category.objects.create(household=household, name="Bathroom", is_predefined=True)

        assert household.categories.count() == 2


class TestPredefinedCategoryNames:
    def test_exact_list_and_order(self):
        assert PREDEFINED_CATEGORY_NAMES == [
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

    def test_has_nine_names(self):
        assert len(PREDEFINED_CATEGORY_NAMES) == 9
