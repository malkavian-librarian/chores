import pytest

from categories.forms import CategoryForm
from categories.models import Category
from households.models import Household


@pytest.mark.django_db
class TestCategoryForm:
    def test_valid_name_is_accepted(self):
        household = Household.create_with_unique_slug()

        form = CategoryForm({"name": "Garage"}, household=household)

        assert form.is_valid()
        assert form.cleaned_data["name"] == "Garage"

    def test_empty_name_rejected(self):
        form = CategoryForm({"name": ""})

        assert not form.is_valid()
        assert "name" in form.errors

    def test_whitespace_only_name_rejected(self):
        form = CategoryForm({"name": "   "})

        assert not form.is_valid()
        assert "name" in form.errors

    def test_name_is_stripped(self):
        household = Household.create_with_unique_slug()

        form = CategoryForm({"name": "  Garage  "}, household=household)

        assert form.is_valid()
        assert form.cleaned_data["name"] == "Garage"

    def test_duplicate_name_rejected_case_insensitive(self):
        household = Household.create_with_unique_slug()
        Category.objects.create(household=household, name="Garage", is_predefined=False)

        form = CategoryForm({"name": "GARAGE"}, household=household)

        assert not form.is_valid()
        assert "name" in form.errors

    def test_duplicate_of_predefined_rejected(self):
        household = Household.create_with_unique_slug()

        form = CategoryForm({"name": "kitchen"}, household=household)

        assert not form.is_valid()
        assert "name" in form.errors

    def test_exclude_pk_allows_renaming_to_same_name(self):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        form = CategoryForm({"name": "Garage"}, household=household, exclude_pk=category.pk)

        assert form.is_valid()

    def test_no_household_skips_duplicate_check(self):
        form = CategoryForm({"name": "Anything"})

        assert form.is_valid()
