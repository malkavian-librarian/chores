"""Tests for the chore detail/edit view and creator-only delete, issue #11.

Covers the acceptance criteria: click-through link from the household
list, all fields shown/editable regardless of acting-as state, invalid
edits leave the stored chore unchanged, the delete button's visibility
gate, a successful delete, server-side rejection of a direct delete
POST by the non-creator or with no acting-as partner (the important
case -- bypassing the hidden button entirely), and 404s for
cross-household/nonexistent chore ids.
"""

import datetime

import pytest
from django.urls import reverse

from chores.models import Chore, ChoreStatus
from households.models import Household, Partner
from households.views import _acting_as_session_key


@pytest.mark.django_db
class TestChoreDetailView:
    def _household_with_partners(self, slug):
        household = Household.objects.create(slug=slug)
        alice = Partner.objects.create(household=household, name="Alice")
        bob = Partner.objects.create(household=household, name="Bob")
        return household, alice, bob

    def _chore(self, household, owner, created_by, **kwargs):
        defaults = {
            "household": household,
            "title": "Wash dishes",
            "owner": owner,
            "created_by": created_by,
        }
        defaults.update(kwargs)
        return Chore.objects.create(**defaults)

    def _detail_url(self, household, chore):
        return reverse("chores:chore_detail", kwargs={"slug": household.slug, "chore_id": chore.pk})

    def _delete_url(self, household, chore):
        return reverse("chores:chore_delete", kwargs={"slug": household.slug, "chore_id": chore.pk})

    def _act_as(self, client, household, partner):
        session = client.session
        session[_acting_as_session_key(household.slug)] = partner.pk
        session.save()

    # -- click-through link from the household list --

    def test_chore_title_links_to_detail_view_from_household_list(self, client):
        household, alice, bob = self._household_with_partners("detail-list-link")
        chore = self._chore(household, owner=alice, created_by=alice)

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        assert self._detail_url(household, chore) in response.content.decode()

    # -- GET shows all fields --

    def test_get_shows_all_current_field_values(self, client):
        household, alice, bob = self._household_with_partners("detail-get-fields")
        chore = self._chore(
            household,
            owner=alice,
            created_by=alice,
            description="Use the good sponge",
            due_date=datetime.date(2026, 2, 1),
        )

        response = client.get(self._detail_url(household, chore))
        content = response.content.decode()

        assert response.status_code == 200
        assert "Wash dishes" in content
        assert "Use the good sponge" in content
        assert 'value="2026-02-01"' in content

    # -- edits persist regardless of acting-as state --

    def test_valid_edit_persists_and_redirects_with_no_acting_as(self, client):
        household, alice, bob = self._household_with_partners("detail-edit-no-acting-as")
        chore = self._chore(household, owner=alice, created_by=alice)

        response = client.post(
            self._detail_url(household, chore),
            {"title": "Wash all the dishes", "owner": bob.pk},
        )

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})
        chore.refresh_from_db()
        assert chore.title == "Wash all the dishes"
        assert chore.owner == bob

    def test_valid_edit_persists_when_acting_as_creator(self, client):
        household, alice, bob = self._household_with_partners("detail-edit-as-creator")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        response = client.post(
            self._detail_url(household, chore),
            {"title": "New title", "owner": alice.pk},
        )

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.title == "New title"

    def test_valid_edit_persists_when_acting_as_non_creator(self, client):
        household, alice, bob = self._household_with_partners("detail-edit-as-non-creator")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, bob)

        response = client.post(
            self._detail_url(household, chore),
            {"title": "Edited by non-creator", "owner": bob.pk},
        )

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.title == "Edited by non-creator"
        # created_by is untouched by editing -- editing isn't authorship.
        assert chore.created_by == alice

    def test_edit_updates_description_category_due_date(self, client):
        from categories.models import Category

        household, alice, bob = self._household_with_partners("detail-edit-all-fields")
        chore = self._chore(household, owner=alice, created_by=alice)
        category = Category.objects.create(household=household, name="Kitchen")

        response = client.post(
            self._detail_url(household, chore),
            {
                "title": "Wash dishes",
                "description": "New notes",
                "owner": bob.pk,
                "due_date": "2026-03-05",
                "category": category.pk,
            },
        )

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.description == "New notes"
        assert chore.owner == bob
        assert chore.due_date == datetime.date(2026, 3, 5)
        assert chore.category == category

    # -- invalid edit re-renders with errors, no changes --

    def test_invalid_edit_rerenders_with_errors_and_does_not_change_chore(self, client):
        household, alice, bob = self._household_with_partners("detail-edit-invalid")
        chore = self._chore(household, owner=alice, created_by=alice, description="original")

        response = client.post(
            self._detail_url(household, chore),
            {"title": "   ", "description": "attempted change", "owner": alice.pk},
        )

        assert response.status_code == 200
        assert "This field is required" in response.content.decode()
        chore.refresh_from_db()
        assert chore.title == "Wash dishes"
        assert chore.description == "original"

    # -- delete button visibility --

    def test_delete_button_shown_only_to_creator(self, client):
        household, alice, bob = self._household_with_partners("detail-delete-visible-creator")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        response = client.get(self._detail_url(household, chore))

        assert ">Delete<" in response.content.decode()

    def test_delete_button_hidden_from_non_creator(self, client):
        household, alice, bob = self._household_with_partners("detail-delete-hidden-non-creator")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, bob)

        response = client.get(self._detail_url(household, chore))

        assert ">Delete<" not in response.content.decode()

    def test_delete_button_hidden_with_no_acting_as(self, client):
        household, alice, bob = self._household_with_partners("detail-delete-hidden-no-acting-as")
        chore = self._chore(household, owner=alice, created_by=alice)

        response = client.get(self._detail_url(household, chore))

        assert ">Delete<" not in response.content.decode()

    # -- delete action itself --

    def test_delete_by_creator_removes_chore_and_redirects(self, client):
        household, alice, bob = self._household_with_partners("detail-delete-success")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        response = client.post(self._delete_url(household, chore))

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})
        assert not Chore.objects.filter(pk=chore.pk).exists()

    # -- server-side rejection of direct delete POSTs (the important case) --

    def test_direct_delete_post_by_non_creator_is_rejected_not_deleted(self, client):
        household, alice, bob = self._household_with_partners("detail-delete-reject-non-creator")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, bob)

        response = client.post(self._delete_url(household, chore))

        assert response.status_code == 403
        assert Chore.objects.filter(pk=chore.pk).exists()

    def test_direct_delete_post_with_no_acting_as_is_rejected_not_deleted(self, client):
        household, alice, bob = self._household_with_partners("detail-delete-reject-no-acting-as")
        chore = self._chore(household, owner=alice, created_by=alice)

        response = client.post(self._delete_url(household, chore))

        assert response.status_code == 403
        assert Chore.objects.filter(pk=chore.pk).exists()

    def test_get_on_delete_url_does_not_delete(self, client):
        household, alice, bob = self._household_with_partners("detail-delete-get-noop")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        response = client.get(self._delete_url(household, chore))

        assert response.status_code == 302
        assert Chore.objects.filter(pk=chore.pk).exists()

    # -- 404s: cross-household / nonexistent --

    def test_detail_view_404s_for_chore_in_another_household(self, client):
        household, alice, bob = self._household_with_partners("detail-404-own-household")
        other_household, other_alice, other_bob = self._household_with_partners(
            "detail-404-other-household"
        )
        other_chore = self._chore(other_household, owner=other_alice, created_by=other_alice)

        url = reverse(
            "chores:chore_detail", kwargs={"slug": household.slug, "chore_id": other_chore.pk}
        )
        response = client.get(url)

        assert response.status_code == 404

    def test_detail_view_404s_for_nonexistent_chore_id(self, client):
        household, alice, bob = self._household_with_partners("detail-404-nonexistent")

        url = reverse("chores:chore_detail", kwargs={"slug": household.slug, "chore_id": 999999})
        response = client.get(url)

        assert response.status_code == 404

    def test_delete_view_404s_for_chore_in_another_household(self, client):
        household, alice, bob = self._household_with_partners("delete-404-own-household")
        other_household, other_alice, other_bob = self._household_with_partners(
            "delete-404-other-household"
        )
        other_chore = self._chore(other_household, owner=other_alice, created_by=other_alice)
        self._act_as(client, household, alice)

        url = reverse(
            "chores:chore_delete", kwargs={"slug": household.slug, "chore_id": other_chore.pk}
        )
        response = client.post(url)

        assert response.status_code == 404
        assert Chore.objects.filter(pk=other_chore.pk).exists()

    def test_edit_post_404s_for_chore_in_another_household(self, client):
        household, alice, bob = self._household_with_partners("edit-404-own-household")
        other_household, other_alice, other_bob = self._household_with_partners(
            "edit-404-other-household"
        )
        other_chore = self._chore(other_household, owner=other_alice, created_by=other_alice)

        url = reverse(
            "chores:chore_detail", kwargs={"slug": household.slug, "chore_id": other_chore.pk}
        )
        response = client.post(url, {"title": "Hijacked", "owner": alice.pk})

        assert response.status_code == 404
        other_chore.refresh_from_db()
        assert other_chore.title != "Hijacked"

    def test_edit_stays_active_status_after_save(self, client):
        household, alice, bob = self._household_with_partners("detail-edit-status-preserved")
        chore = self._chore(household, owner=alice, created_by=alice)

        client.post(self._detail_url(household, chore), {"title": "Renamed", "owner": alice.pk})

        chore.refresh_from_db()
        assert chore.status == ChoreStatus.ACTIVE
