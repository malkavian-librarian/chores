"""Tests for the shared base template and top-level nav, issue #4.

Covers: nav links resolve to real pages (200), full pages extend
`base.html`, the nav is present on every page, the Household link
points at the current household when one is in context, and a
proxy-check that the content wrapper is a single centered column
(no side-by-side desktop layout).
"""

from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from households.models import Household, Partner


@pytest.mark.django_db
class TestNavLinksReturn200:
    def test_categories_page_returns_200(self, client):
        response = client.get(reverse("categories:index"))

        assert response.status_code == 200

    def test_settings_page_returns_200(self, client):
        response = client.get(reverse("households:settings"))

        assert response.status_code == 200

    def test_household_detail_returns_200(self, client):
        household = Household.objects.create(slug="nav-test-household")

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        assert response.status_code == 200


@pytest.mark.django_db
class TestBaseTemplateIsUsed:
    def test_household_detail_extends_base(self, client):
        household = Household.objects.create(slug="extends-base-household")

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        template_names = [t.name for t in response.templates]
        assert "base.html" in template_names
        assert "households/detail.html" in template_names

    def test_categories_index_extends_base(self, client):
        response = client.get(reverse("categories:index"))

        template_names = [t.name for t in response.templates]
        assert "base.html" in template_names
        assert "categories/index.html" in template_names

    def test_settings_extends_base(self, client):
        response = client.get(reverse("households:settings"))

        template_names = [t.name for t in response.templates]
        assert "base.html" in template_names
        assert "households/settings.html" in template_names


@pytest.mark.django_db
class TestNavBar:
    def test_nav_shows_three_labelled_links_on_every_page(self, client):
        for url in (
            reverse("categories:index"),
            reverse("households:settings"),
        ):
            content = client.get(url).content.decode()
            assert ">Household<" in content
            assert ">Categories<" in content
            assert ">Settings<" in content

    def test_categories_and_settings_links_use_url_tag_targets(self, client):
        response = client.get(reverse("categories:index"))
        content = response.content.decode()

        assert reverse("categories:index") in content
        assert reverse("households:settings") in content

    def test_household_link_points_at_index_without_household_context(self, client):
        response = client.get(reverse("categories:index"))
        content = response.content.decode()

        assert reverse("households:index") in content

    def test_household_link_points_at_current_household_when_in_context(self, client):
        household = Household.objects.create(slug="current-household-nav")
        Partner.objects.create(household=household, name="Alex")
        Partner.objects.create(household=household, name="Sam")

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))
        content = response.content.decode()

        assert reverse("households:detail", kwargs={"slug": household.slug}) in content


class TestSingleColumnLayout:
    """Proxy-check per issue #4: no visual regression testing for this
    MVP, so confirm by reading the template that the content wrapper is
    a single centered column with no side-by-side desktop variant."""

    def _base_html_source(self):
        base_html = Path(settings.BASE_DIR) / "templates" / "base.html"
        return base_html.read_text()

    def test_content_wrapper_uses_single_column_utilities(self):
        source = self._base_html_source()

        assert "max-w-" in source
        assert "mx-auto" in source

    def test_no_multi_column_desktop_utilities(self):
        source = self._base_html_source()

        assert "grid-cols-" not in source
        assert "flex-row" not in source
        assert "md:grid" not in source
        assert "lg:grid" not in source
