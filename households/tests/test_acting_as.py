"""Tests for the "acting as" partner switch, issue #23.

Covers the acceptance criteria: picker shown once two partners exist,
selection stored/scoped per household, persists across reload,
switching updates immediately, unselected initial state, and the
stale-partner-id fallback.
"""

import pytest
from django.urls import reverse

from households.models import Household, Partner
from households.views import _acting_as_session_key


@pytest.mark.django_db
class TestActingAsPicker:
    def test_picker_shown_once_two_partners_exist(self, client):
        household = Household.objects.create(slug="two-partners")
        Partner.objects.create(household=household, name="Alex")
        Partner.objects.create(household=household, name="Sam")

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        content = response.content.decode()
        assert response.status_code == 200
        assert "Acting as Alex" in content
        assert "Acting as Sam" in content

    def test_no_picker_shown_with_zero_partners(self, client):
        household = Household.objects.create(slug="zero-partners")

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        content = response.content.decode()
        assert response.status_code == 200
        assert "Acting as " not in content

    def test_unselected_initial_state_renders_without_error(self, client):
        household = Household.objects.create(slug="unselected")
        Partner.objects.create(household=household, name="Alex")
        Partner.objects.create(household=household, name="Sam")

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        content = response.content.decode()
        assert response.status_code == 200
        assert "Acting as:" not in content

    def test_selecting_a_partner_stores_scoped_session_key_and_redirects(self, client):
        household = Household.objects.create(slug="select-partner")
        alex = Partner.objects.create(household=household, name="Alex")
        Partner.objects.create(household=household, name="Sam")
        url = reverse("households:set_acting_as", kwargs={"slug": household.slug})

        response = client.post(url, {"partner_id": alex.pk})

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})
        assert client.session[_acting_as_session_key(household.slug)] == alex.pk

    def test_selection_displayed_after_redirect_and_on_reload(self, client):
        household = Household.objects.create(slug="displayed-after-select")
        alex = Partner.objects.create(household=household, name="Alex")
        Partner.objects.create(household=household, name="Sam")
        select_url = reverse("households:set_acting_as", kwargs={"slug": household.slug})
        detail_url = reverse("households:detail", kwargs={"slug": household.slug})

        client.post(select_url, {"partner_id": alex.pk})
        response = client.get(detail_url)

        assert "Acting as: Alex" in response.content.decode()

        # Reload (plain GET, no new selection) still shows the same value.
        response_again = client.get(detail_url)
        assert "Acting as: Alex" in response_again.content.decode()

    def test_switching_partner_updates_immediately(self, client):
        household = Household.objects.create(slug="switch-partner")
        alex = Partner.objects.create(household=household, name="Alex")
        sam = Partner.objects.create(household=household, name="Sam")
        select_url = reverse("households:set_acting_as", kwargs={"slug": household.slug})
        detail_url = reverse("households:detail", kwargs={"slug": household.slug})

        client.post(select_url, {"partner_id": alex.pk})
        assert "Acting as: Alex" in client.get(detail_url).content.decode()

        client.post(select_url, {"partner_id": sam.pk})
        content = client.get(detail_url).content.decode()

        assert "Acting as: Sam" in content
        assert "Acting as: Alex" not in content

    def test_second_household_does_not_leak_first_households_selection(self, client):
        first = Household.objects.create(slug="first-household")
        alex = Partner.objects.create(household=first, name="Alex")
        Partner.objects.create(household=first, name="Sam")

        second = Household.objects.create(slug="second-household")
        Partner.objects.create(household=second, name="Robin")
        Partner.objects.create(household=second, name="Jamie")

        client.post(
            reverse("households:set_acting_as", kwargs={"slug": first.slug}),
            {"partner_id": alex.pk},
        )

        response = client.get(reverse("households:detail", kwargs={"slug": second.slug}))
        content = response.content.decode()

        assert response.status_code == 200
        assert "Acting as:" not in content

    def test_stale_partner_id_in_session_falls_back_without_500(self, client):
        household = Household.objects.create(slug="stale-partner")
        Partner.objects.create(household=household, name="Alex")
        Partner.objects.create(household=household, name="Sam")

        session = client.session
        session[_acting_as_session_key(household.slug)] = 999999
        session.save()

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))
        content = response.content.decode()

        assert response.status_code == 200
        assert "Acting as:" not in content

    def test_invalid_partner_id_posted_is_ignored_without_error(self, client):
        household = Household.objects.create(slug="invalid-post")
        Partner.objects.create(household=household, name="Alex")
        Partner.objects.create(household=household, name="Sam")
        select_url = reverse("households:set_acting_as", kwargs={"slug": household.slug})

        response = client.post(select_url, {"partner_id": 999999})

        assert response.status_code == 302
        assert _acting_as_session_key(household.slug) not in client.session
