import pytest
from django.urls import NoReverseMatch, reverse
from django.utils.html import escape

from categories.models import PREDEFINED_CATEGORY_NAMES
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


class TestOldGlobalCategoriesRouteRemoved:
    def test_global_categories_route_no_longer_resolves(self):
        with pytest.raises(NoReverseMatch):
            reverse("categories:index")

    @pytest.mark.django_db
    def test_old_global_categories_path_returns_404(self, client):
        response = client.get("/categories/")

        assert response.status_code == 404
