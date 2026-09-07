from urllib.parse import quote

import pytest
from django.urls import reverse

from households.models import Household, Partner
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


@pytest.mark.django_db
class TestDetailViewPartnerNaming:
    def test_naming_form_shown_with_zero_partners(self, client):
        household = Household.objects.create(slug="zero-partners")

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Partner 1 name" in content
        assert "Partner 2 name" in content

    def test_naming_form_hidden_when_two_partners_exist(self, client):
        household = Household.objects.create(slug="two-partners")
        Partner.objects.create(household=household, name="Alex")
        Partner.objects.create(household=household, name="Sam")

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Partner 1 name" not in content
        assert "Alex and Sam" in content

    def test_valid_submission_creates_exactly_two_partners(self, client):
        household = Household.objects.create(slug="submit-valid")
        url = reverse("households:detail", kwargs={"slug": household.slug})

        response = client.post(
            url, {"partner_1_name": "Alex", "partner_2_name": "Sam"}, follow=False
        )

        assert response.status_code == 302
        assert response.url == url
        assert household.partners.count() == 2
        names = set(household.partners.values_list("name", flat=True))
        assert names == {"Alex", "Sam"}

    def test_after_submission_form_no_longer_shown(self, client):
        household = Household.objects.create(slug="submit-then-get")
        url = reverse("households:detail", kwargs={"slug": household.slug})
        client.post(url, {"partner_1_name": "Alex", "partner_2_name": "Sam"})

        response = client.get(url)

        content = response.content.decode()
        assert "Partner 1 name" not in content
        assert "Alex and Sam" in content

    def test_visiting_later_after_partners_exist_skips_form(self, client):
        household = Household.objects.create(slug="later-visit")
        Partner.objects.create(household=household, name="Alex")
        Partner.objects.create(household=household, name="Sam")
        url = reverse("households:detail", kwargs={"slug": household.slug})

        # Simulate a fresh, unrelated session.
        second_client = client.__class__()
        response = second_client.get(url)

        assert response.status_code == 200
        assert "Partner 1 name" not in response.content.decode()

    def test_blank_name_rejected_creates_zero_rows(self, client):
        household = Household.objects.create(slug="blank-name")
        url = reverse("households:detail", kwargs={"slug": household.slug})

        response = client.post(url, {"partner_1_name": "", "partner_2_name": "Sam"})

        assert response.status_code == 200
        assert household.partners.count() == 0
        assert "Partner 1 name" in response.content.decode()

    def test_missing_field_rejected_creates_zero_rows(self, client):
        household = Household.objects.create(slug="missing-field")
        url = reverse("households:detail", kwargs={"slug": household.slug})

        response = client.post(url, {"partner_1_name": "Alex"})

        assert response.status_code == 200
        assert household.partners.count() == 0

    def test_whitespace_only_name_rejected_creates_zero_rows(self, client):
        household = Household.objects.create(slug="whitespace-name")
        url = reverse("households:detail", kwargs={"slug": household.slug})

        response = client.post(url, {"partner_1_name": "   ", "partner_2_name": "Sam"})

        assert response.status_code == 200
        assert household.partners.count() == 0

    def test_names_are_trimmed_before_saving(self, client):
        household = Household.objects.create(slug="trim-names")
        url = reverse("households:detail", kwargs={"slug": household.slug})

        client.post(url, {"partner_1_name": "  Alex ", "partner_2_name": " Sam  "})

        names = set(household.partners.values_list("name", flat=True))
        assert names == {"Alex", "Sam"}

    def test_name_over_max_length_rejected_creates_zero_rows(self, client):
        household = Household.objects.create(slug="too-long-name")
        url = reverse("households:detail", kwargs={"slug": household.slug})
        too_long = "a" * 101

        response = client.post(url, {"partner_1_name": too_long, "partner_2_name": "Sam"})

        assert response.status_code == 200
        assert household.partners.count() == 0

    def test_double_submit_does_not_create_second_pair(self, client):
        household = Household.objects.create(slug="double-submit")
        url = reverse("households:detail", kwargs={"slug": household.slug})

        first = client.post(url, {"partner_1_name": "Alex", "partner_2_name": "Sam"})
        second = client.post(url, {"partner_1_name": "Alex", "partner_2_name": "Sam"})

        assert first.status_code == 302
        assert second.status_code == 302
        assert second.url == url
        assert household.partners.count() == 2

    def test_duplicate_partner_names_are_allowed(self, client):
        household = Household.objects.create(slug="dup-names")
        url = reverse("households:detail", kwargs={"slug": household.slug})

        response = client.post(url, {"partner_1_name": "Alex", "partner_2_name": "Alex"})

        assert response.status_code == 302
        assert household.partners.count() == 2
        assert list(household.partners.values_list("name", flat=True)) == ["Alex", "Alex"]
