"""Tests for the quick-add chore view, issue #8.

Covers the acceptance criteria: title-only defaults, owner
default/override from the "acting as" session partner, required
explicit owner when no "acting as" partner is set, created_by
attribution logic, blank-title validation (0 rows created), optional
due_date/category, the post-submit redirect, and the <2-partners
redirect-not-crash guard.
"""

import datetime

import pytest
from django.urls import reverse

from categories.models import Category
from chores.models import Chore, ChoreStatus
from households.models import Household, Partner
from households.views import _acting_as_session_key


@pytest.mark.django_db
class TestQuickAddChore:
    def _household_with_partners(self, slug):
        household = Household.objects.create(slug=slug)
        alice = Partner.objects.create(household=household, name="Alice")
        bob = Partner.objects.create(household=household, name="Bob")
        return household, alice, bob

    def _url(self, household):
        return reverse("chores:quick_add", kwargs={"slug": household.slug})

    def _act_as(self, client, household, partner):
        session = client.session
        session[_acting_as_session_key(household.slug)] = partner.pk
        session.save()

    def test_get_renders_form(self, client):
        household, alice, bob = self._household_with_partners("quick-add-get")

        response = client.get(self._url(household))

        assert response.status_code == 200
        assert "Add details" in response.content.decode()

    def test_title_only_creates_chore_with_defaults(self, client):
        household, alice, bob = self._household_with_partners("quick-add-title-only")
        self._act_as(client, household, alice)

        # A real browser always submits the (pre-selected) owner <select>
        # value even when the visitor never touches it -- this is what
        # "title-only" looks like on the wire once the acting-as default
        # is pre-selected in the rendered form.
        response = client.post(self._url(household), {"title": "Wash dishes", "owner": alice.pk})

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})
        assert Chore.objects.count() == 1
        chore = Chore.objects.get()
        assert chore.title == "Wash dishes"
        assert chore.description == ""
        assert chore.due_date is None
        assert chore.category is None
        assert chore.status == ChoreStatus.ACTIVE
        assert chore.owner == alice
        assert chore.created_by == alice

    def test_owner_overridable_to_other_partner(self, client):
        household, alice, bob = self._household_with_partners("quick-add-override-owner")
        self._act_as(client, household, alice)

        response = client.post(self._url(household), {"title": "Mow the lawn", "owner": bob.pk})

        assert response.status_code == 302
        chore = Chore.objects.get()
        assert chore.owner == bob
        # created_by always follows the acting-as partner when one is set,
        # regardless of who was picked as owner.
        assert chore.created_by == alice

    def test_no_acting_as_requires_explicit_owner(self, client):
        household, alice, bob = self._household_with_partners("quick-add-no-acting-as")

        response = client.post(self._url(household), {"title": "Take out trash"})

        assert response.status_code == 200
        assert Chore.objects.count() == 0
        assert "This field is required" in response.content.decode()

    def test_no_acting_as_with_explicit_owner_sets_created_by_to_owner(self, client):
        household, alice, bob = self._household_with_partners("quick-add-no-acting-as-owner")

        response = client.post(self._url(household), {"title": "Take out trash", "owner": bob.pk})

        assert response.status_code == 302
        chore = Chore.objects.get()
        assert chore.owner == bob
        assert chore.created_by == bob

    def test_blank_title_is_rejected_and_creates_zero_rows(self, client):
        household, alice, bob = self._household_with_partners("quick-add-blank-title")
        self._act_as(client, household, alice)

        response = client.post(
            self._url(household),
            {"title": "   ", "description": "Some notes to preserve"},
        )

        assert response.status_code == 200
        assert Chore.objects.count() == 0
        content = response.content.decode()
        assert "This field is required" in content
        assert "Some notes to preserve" in content

    def test_due_date_and_category_are_set_when_provided(self, client):
        household, alice, bob = self._household_with_partners("quick-add-due-date-category")
        self._act_as(client, household, alice)
        category = Category.objects.create(household=household, name="Kitchen")

        response = client.post(
            self._url(household),
            {
                "title": "Deep clean fridge",
                "owner": alice.pk,
                "due_date": "2026-01-15",
                "category": category.pk,
            },
        )

        assert response.status_code == 302
        chore = Chore.objects.get()
        assert chore.due_date == datetime.date(2026, 1, 15)
        assert chore.category == category

    def test_created_chore_title_visible_on_household_page(self, client):
        household, alice, bob = self._household_with_partners("quick-add-visible-after-redirect")
        self._act_as(client, household, alice)

        client.post(self._url(household), {"title": "Water the plants", "owner": alice.pk})
        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        assert "Water the plants" in response.content.decode()

    def test_fewer_than_two_partners_redirects_without_error(self, client):
        household = Household.objects.create(slug="quick-add-one-partner")
        Partner.objects.create(household=household, name="Alice")

        response = client.get(self._url(household))

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})
        assert Chore.objects.count() == 0

    def test_zero_partners_redirects_without_error(self, client):
        household = Household.objects.create(slug="quick-add-zero-partners")

        response = client.get(self._url(household))

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})
