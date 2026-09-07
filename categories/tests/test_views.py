import pytest
from django.urls import NoReverseMatch, reverse
from django.utils.html import escape

from categories.models import PREDEFINED_CATEGORY_NAMES, Category
from households.models import Household


@pytest.mark.django_db
class TestCategoriesIndexView:
    def test_renders_household_categories(self, client):
        household = Household.create_with_unique_slug()

        response = client.get(reverse("categories:index", kwargs={"slug": household.slug}))

        assert response.status_code == 200
        content = response.content.decode()
        for name in PREDEFINED_CATEGORY_NAMES:
            assert escape(name) in content

    def test_unknown_slug_returns_404(self, client):
        response = client.get(reverse("categories:index", kwargs={"slug": "no-such-household"}))

        assert response.status_code == 404

    def test_uses_categories_index_template(self, client):
        household = Household.create_with_unique_slug()

        response = client.get(reverse("categories:index", kwargs={"slug": household.slug}))

        template_names = [t.name for t in response.templates]
        assert "categories/index.html" in template_names
        assert "base.html" in template_names


@pytest.mark.django_db
class TestCategoryCreateView:
    def test_valid_name_creates_custom_category(self, client):
        household = Household.create_with_unique_slug()

        response = client.post(
            reverse("categories:create", kwargs={"slug": household.slug}),
            {"name": "Garage"},
        )

        assert response.status_code == 302
        assert response.url == reverse("categories:index", kwargs={"slug": household.slug})
        category = household.categories.get(name="Garage")
        assert category.is_predefined is False

    def test_created_category_appears_on_index_after_redirect(self, client):
        household = Household.create_with_unique_slug()
        create_url = reverse("categories:create", kwargs={"slug": household.slug})

        response = client.post(create_url, {"name": "Garage"}, follow=True)

        assert escape("Garage") in response.content.decode()

    def test_empty_name_rejected(self, client):
        household = Household.create_with_unique_slug()

        response = client.post(
            reverse("categories:create", kwargs={"slug": household.slug}),
            {"name": ""},
            follow=True,
        )

        assert not household.categories.filter(name="").exists()
        assert response.status_code == 200

    def test_whitespace_only_name_rejected(self, client):
        household = Household.create_with_unique_slug()

        response = client.post(
            reverse("categories:create", kwargs={"slug": household.slug}),
            {"name": "   "},
            follow=True,
        )

        assert household.categories.count() == len(PREDEFINED_CATEGORY_NAMES)
        assert response.status_code == 200

    def test_duplicate_of_predefined_name_rejected_case_insensitive(self, client):
        household = Household.create_with_unique_slug()

        response = client.post(
            reverse("categories:create", kwargs={"slug": household.slug}),
            {"name": "kitchen"},
            follow=True,
        )

        assert household.categories.filter(name__iexact="kitchen").count() == 1
        content = response.content.decode()
        assert "already exists" in content.lower()

    def test_duplicate_of_custom_name_rejected_case_insensitive(self, client):
        household = Household.create_with_unique_slug()
        Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:create", kwargs={"slug": household.slug}),
            {"name": "GARAGE"},
            follow=True,
        )

        assert household.categories.filter(name__iexact="garage").count() == 1
        content = response.content.decode()
        assert "already exists" in content.lower()

    def test_same_name_allowed_across_different_households(self, client):
        household_a = Household.create_with_unique_slug()
        household_b = Household.create_with_unique_slug()
        Category.objects.create(household=household_a, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:create", kwargs={"slug": household_b.slug}),
            {"name": "Garage"},
        )

        assert response.status_code == 302
        assert household_b.categories.filter(name="Garage").exists()

    def test_get_request_redirects_without_creating(self, client):
        household = Household.create_with_unique_slug()

        response = client.get(reverse("categories:create", kwargs={"slug": household.slug}))

        assert response.status_code == 302
        assert household.categories.count() == len(PREDEFINED_CATEGORY_NAMES)

    def test_unknown_slug_returns_404(self, client):
        response = client.post(
            reverse("categories:create", kwargs={"slug": "no-such-household"}),
            {"name": "Garage"},
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestCategoryRenameView:
    def test_renames_custom_category(self, client):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:rename", kwargs={"slug": household.slug, "pk": category.pk}),
            {"name": "Workshop"},
        )

        assert response.status_code == 302
        category.refresh_from_db()
        assert category.name == "Workshop"

    def test_renamed_category_appears_on_index_after_redirect(self, client):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:rename", kwargs={"slug": household.slug, "pk": category.pk}),
            {"name": "Workshop"},
            follow=True,
        )

        assert escape("Workshop") in response.content.decode()

    def test_predefined_category_rename_rejected_without_500(self, client):
        household = Household.create_with_unique_slug()
        predefined = household.categories.filter(is_predefined=True).first()
        original_name = predefined.name

        response = client.post(
            reverse("categories:rename", kwargs={"slug": household.slug, "pk": predefined.pk}),
            {"name": "Hacked"},
        )

        assert response.status_code in (302, 403)
        predefined.refresh_from_db()
        assert predefined.name == original_name
        assert predefined.is_predefined is True

    def test_predefined_category_rename_shows_error_after_redirect(self, client):
        household = Household.create_with_unique_slug()
        predefined = household.categories.filter(is_predefined=True).first()

        response = client.post(
            reverse("categories:rename", kwargs={"slug": household.slug, "pk": predefined.pk}),
            {"name": "Hacked"},
            follow=True,
        )

        assert response.status_code == 200
        assert "predefined" in response.content.decode().lower()

    def test_empty_name_rejected_and_unchanged(self, client):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:rename", kwargs={"slug": household.slug, "pk": category.pk}),
            {"name": "   "},
            follow=True,
        )

        category.refresh_from_db()
        assert category.name == "Garage"
        assert response.status_code == 200

    def test_duplicate_name_rejected_and_unchanged(self, client):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:rename", kwargs={"slug": household.slug, "pk": category.pk}),
            {"name": "kitchen"},
            follow=True,
        )

        category.refresh_from_db()
        assert category.name == "Garage"
        content = response.content.decode()
        assert "already exists" in content.lower()

    def test_rename_to_own_current_name_is_allowed(self, client):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:rename", kwargs={"slug": household.slug, "pk": category.pk}),
            {"name": "Garage"},
        )

        assert response.status_code == 302
        category.refresh_from_db()
        assert category.name == "Garage"

    def test_cross_household_category_id_returns_404(self, client):
        household_a = Household.create_with_unique_slug()
        household_b = Household.create_with_unique_slug()
        category = Category.objects.create(
            household=household_a, name="Garage", is_predefined=False
        )

        response = client.post(
            reverse("categories:rename", kwargs={"slug": household_b.slug, "pk": category.pk}),
            {"name": "Hacked"},
        )

        assert response.status_code == 404
        category.refresh_from_db()
        assert category.name == "Garage"

    def test_unknown_slug_returns_404(self, client):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:rename", kwargs={"slug": "no-such-household", "pk": category.pk}),
            {"name": "Workshop"},
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestCategoryDeleteView:
    def test_deletes_custom_category(self, client):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:delete", kwargs={"slug": household.slug, "pk": category.pk})
        )

        assert response.status_code == 302
        assert not household.categories.filter(pk=category.pk).exists()

    def test_deleted_category_absent_from_index_after_redirect(self, client):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:delete", kwargs={"slug": household.slug, "pk": category.pk}),
            follow=True,
        )

        assert escape("Garage") not in response.content.decode()

    def test_deleting_last_custom_category_succeeds(self, client):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:delete", kwargs={"slug": household.slug, "pk": category.pk})
        )

        assert response.status_code == 302
        assert household.categories.filter(is_predefined=False).count() == 0
        assert household.categories.filter(is_predefined=True).count() == len(
            PREDEFINED_CATEGORY_NAMES
        )

    def test_predefined_category_delete_rejected_without_500(self, client):
        household = Household.create_with_unique_slug()
        predefined = household.categories.filter(is_predefined=True).first()

        response = client.post(
            reverse("categories:delete", kwargs={"slug": household.slug, "pk": predefined.pk})
        )

        assert response.status_code in (302, 403)
        assert household.categories.filter(pk=predefined.pk).exists()

    def test_predefined_category_delete_shows_error_after_redirect(self, client):
        household = Household.create_with_unique_slug()
        predefined = household.categories.filter(is_predefined=True).first()

        response = client.post(
            reverse("categories:delete", kwargs={"slug": household.slug, "pk": predefined.pk}),
            follow=True,
        )

        assert response.status_code == 200
        assert "predefined" in response.content.decode().lower()

    def test_cross_household_category_id_returns_404(self, client):
        household_a = Household.create_with_unique_slug()
        household_b = Household.create_with_unique_slug()
        category = Category.objects.create(
            household=household_a, name="Garage", is_predefined=False
        )

        response = client.post(
            reverse("categories:delete", kwargs={"slug": household_b.slug, "pk": category.pk})
        )

        assert response.status_code == 404
        assert household_a.categories.filter(pk=category.pk).exists()

    def test_unknown_slug_returns_404(self, client):
        household = Household.create_with_unique_slug()
        category = Category.objects.create(household=household, name="Garage", is_predefined=False)

        response = client.post(
            reverse("categories:delete", kwargs={"slug": "no-such-household", "pk": category.pk})
        )

        assert response.status_code == 404


class TestOldGlobalCategoriesRouteRemoved:
    def test_global_categories_route_no_longer_resolves(self):
        with pytest.raises(NoReverseMatch):
            reverse("categories:index")

    @pytest.mark.django_db
    def test_old_global_categories_path_returns_404(self, client):
        response = client.get("/categories/")

        assert response.status_code == 404
