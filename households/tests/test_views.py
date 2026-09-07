from urllib.parse import quote

import pytest
from django.urls import reverse

from households.models import Household
from households.views import SESSION_KEY


@pytest.mark.django_db
class TestIndexView:
    def test_creates_household_and_redirects(self, client):
        assert Household.objects.count() == 0

        response = client.get(reverse("households:index"))

        assert Household.objects.count() == 1
        household = Household.objects.get()
        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})
        assert client.session[SESSION_KEY] == household.slug

    def test_return_visit_reuses_session_household(self, client):
        household = Household.objects.create(slug="existing-slug")
        session = client.session
        session[SESSION_KEY] = household.slug
        session.save()

        response = client.get(reverse("households:index"))

        assert Household.objects.count() == 1
        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})

    def test_stale_session_slug_creates_new_household(self, client):
        """If the session references a household that no longer exists,
        a new one is created rather than redirecting to a 404."""
        session = client.session
        session[SESSION_KEY] = "does-not-exist"
        session.save()

        response = client.get(reverse("households:index"))

        assert Household.objects.count() == 1
        household = Household.objects.get()
        assert household.slug != "does-not-exist"
        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})


@pytest.mark.django_db
class TestDetailView:
    def test_valid_slug_returns_200(self, client):
        household = Household.objects.create(slug="valid-slug")

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        assert response.status_code == 200
        assert household.slug.encode() in response.content

    def test_renders_without_partner_data(self, client):
        """The detail view must not query or assume Partner rows (#3
        doesn't exist yet)."""
        household = Household.objects.create(slug="no-partners-yet")

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        assert response.status_code == 200

    def test_nonexistent_but_wellformed_slug_returns_404(self, client):
        response = client.get(reverse("households:detail", kwargs={"slug": "no-such-slug"}))

        assert response.status_code == 404

    def test_malformed_slug_returns_404_not_500(self, client):
        response = client.get("/h/" + quote("bad slug!") + "/")

        assert response.status_code == 404

    def test_missing_trailing_slash_redirects(self, client):
        household = Household.objects.create(slug="needs-slash")

        response = client.get(f"/h/{household.slug}", follow=False)

        assert response.status_code == 301
        assert response.url == f"/h/{household.slug}/"
