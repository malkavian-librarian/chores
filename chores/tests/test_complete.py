"""Tests for Done/Undo (chore completion with one-time Undo), issue #12.

Covers the acceptance criteria: Done sets `status`/`completed_at`/
`completed_by` correctly and attributes to the acting-as partner;
Done is rejected (403) with no acting-as partner and leaves the chore
untouched; double-Done is a no-op that doesn't overwrite
`completed_at`/`completed_by`; the post-completion page offers Undo
exactly once (reachable only immediately after a successful Done, not
on reload/revisit); Undo reverts all three fields and puts the chore
back in the active household list; Undo on a chore that isn't
currently completed is a no-op; GETs to either endpoint never mutate
state.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from chores.models import Chore, ChoreStatus
from households.models import Household, Partner
from households.views import _acting_as_session_key


@pytest.mark.django_db
class TestChoreComplete:
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

    def _complete_url(self, household, chore):
        return reverse(
            "chores:chore_complete", kwargs={"slug": household.slug, "chore_id": chore.pk}
        )

    def _just_completed_url(self, household, chore):
        return reverse(
            "chores:chore_just_completed", kwargs={"slug": household.slug, "chore_id": chore.pk}
        )

    def _undo_url(self, household, chore):
        return reverse("chores:chore_undo", kwargs={"slug": household.slug, "chore_id": chore.pk})

    def _detail_url(self, household, chore):
        return reverse("chores:chore_detail", kwargs={"slug": household.slug, "chore_id": chore.pk})

    def _act_as(self, client, household, partner):
        session = client.session
        session[_acting_as_session_key(household.slug)] = partner.pk
        session.save()

    # -- Done sets fields, attributed to acting-as partner --

    def test_done_sets_status_completed_at_and_completed_by(self, client):
        household, alice, bob = self._household_with_partners("complete-sets-fields")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, bob)

        before = timezone.now()
        response = client.post(self._complete_url(household, chore))
        after = timezone.now()

        assert response.status_code == 302
        assert response.url == self._just_completed_url(household, chore)
        chore.refresh_from_db()
        assert chore.status == ChoreStatus.COMPLETED
        assert chore.completed_by == bob
        assert before <= chore.completed_at <= after

    def test_done_attributes_to_the_acting_as_partner_not_owner(self, client):
        household, alice, bob = self._household_with_partners("complete-attribution")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, bob)

        client.post(self._complete_url(household, chore))

        chore.refresh_from_db()
        assert chore.completed_by == bob
        assert chore.owner == alice

    # -- Done unavailable / rejected with no acting-as --

    def test_done_button_hidden_with_no_acting_as(self, client):
        household, alice, bob = self._household_with_partners("complete-button-hidden")
        chore = self._chore(household, owner=alice, created_by=alice)

        response = client.get(self._detail_url(household, chore))

        assert ">Done<" not in response.content.decode()

    def test_done_button_shown_with_acting_as(self, client):
        household, alice, bob = self._household_with_partners("complete-button-shown")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        response = client.get(self._detail_url(household, chore))

        assert ">Done<" in response.content.decode()

    def test_direct_done_post_with_no_acting_as_is_rejected_and_untouched(self, client):
        household, alice, bob = self._household_with_partners("complete-reject-no-acting-as")
        chore = self._chore(household, owner=alice, created_by=alice)

        response = client.post(self._complete_url(household, chore))

        assert response.status_code == 403
        chore.refresh_from_db()
        assert chore.status == ChoreStatus.ACTIVE
        assert chore.completed_at is None
        assert chore.completed_by is None

    def test_get_on_complete_url_does_not_mutate(self, client):
        household, alice, bob = self._household_with_partners("complete-get-noop")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        response = client.get(self._complete_url(household, chore))

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.status == ChoreStatus.ACTIVE

    # -- double-Done is a no-op --

    def test_double_done_does_not_overwrite_completed_at_or_completed_by(self, client):
        household, alice, bob = self._household_with_partners("complete-double-done")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        chore.refresh_from_db()
        first_completed_at = chore.completed_at
        first_completed_by = chore.completed_by

        self._act_as(client, household, bob)
        response = client.post(self._complete_url(household, chore))

        assert response.status_code != 500
        chore.refresh_from_db()
        assert chore.completed_at == first_completed_at
        assert chore.completed_by == first_completed_by

    # -- post-completion page: one-time Undo --

    def test_just_completed_page_shows_undo_right_after_done(self, client):
        household, alice, bob = self._household_with_partners("complete-page-shows-undo")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        response = client.get(self._just_completed_url(household, chore))

        assert response.status_code == 200
        assert ">Undo<" in response.content.decode()

    def test_just_completed_page_reload_no_longer_shows_undo(self, client):
        household, alice, bob = self._household_with_partners("complete-page-reload-no-undo")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        client.get(self._just_completed_url(household, chore))
        response = client.get(self._just_completed_url(household, chore))

        assert response.status_code == 302
        assert response.url == self._detail_url(household, chore)

    def test_visiting_just_completed_url_directly_without_done_redirects(self, client):
        household, alice, bob = self._household_with_partners("complete-direct-visit-no-undo")
        chore = self._chore(household, owner=alice, created_by=alice, status=ChoreStatus.COMPLETED)

        response = client.get(self._just_completed_url(household, chore))

        assert response.status_code == 302
        assert response.url == self._detail_url(household, chore)

    def test_chore_detail_page_never_shows_undo(self, client):
        household, alice, bob = self._household_with_partners("complete-detail-no-undo")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        response = client.get(self._detail_url(household, chore))

        assert ">Undo<" not in response.content.decode()

    def test_household_list_never_shows_undo(self, client):
        household, alice, bob = self._household_with_partners("complete-household-no-undo")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        assert ">Undo<" not in response.content.decode()


@pytest.mark.django_db
class TestChoreUndo:
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

    def _complete_url(self, household, chore):
        return reverse(
            "chores:chore_complete", kwargs={"slug": household.slug, "chore_id": chore.pk}
        )

    def _undo_url(self, household, chore):
        return reverse("chores:chore_undo", kwargs={"slug": household.slug, "chore_id": chore.pk})

    def _detail_url(self, household, chore):
        return reverse("chores:chore_detail", kwargs={"slug": household.slug, "chore_id": chore.pk})

    def _act_as(self, client, household, partner):
        session = client.session
        session[_acting_as_session_key(household.slug)] = partner.pk
        session.save()

    def test_undo_reverts_status_completed_at_and_completed_by(self, client):
        household, alice, bob = self._household_with_partners("undo-reverts-fields")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, bob)
        client.post(self._complete_url(household, chore))

        response = client.post(self._undo_url(household, chore))

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.status == ChoreStatus.ACTIVE
        assert chore.completed_at is None
        assert chore.completed_by is None

    def test_undone_chore_reappears_in_active_household_list(self, client):
        household, alice, bob = self._household_with_partners("undo-reappears-in-list")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))

        client.post(self._undo_url(household, chore))
        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))

        assert chore.title in response.content.decode()

    def test_undo_when_not_completed_is_a_noop(self, client):
        household, alice, bob = self._household_with_partners("undo-noop-not-completed")
        chore = self._chore(household, owner=alice, created_by=alice)

        response = client.post(self._undo_url(household, chore))

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.status == ChoreStatus.ACTIVE
        assert chore.completed_at is None
        assert chore.completed_by is None

    def test_undo_after_already_undone_is_a_noop(self, client):
        household, alice, bob = self._household_with_partners("undo-noop-already-undone")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))
        client.post(self._undo_url(household, chore))

        response = client.post(self._undo_url(household, chore))

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.status == ChoreStatus.ACTIVE
        assert chore.completed_at is None
        assert chore.completed_by is None

    def test_get_on_undo_url_does_not_mutate(self, client):
        household, alice, bob = self._household_with_partners("undo-get-noop")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))

        response = client.get(self._undo_url(household, chore))

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.status == ChoreStatus.COMPLETED


@pytest.mark.django_db
class TestCompletedChoreExcludedFromActiveList:
    def test_completed_chore_excluded_from_active_household_list(self, client):
        household = Household.objects.create(slug="complete-excluded-from-active-list")
        alice = Partner.objects.create(household=household, name="Alice")
        bob = Partner.objects.create(household=household, name="Bob")
        Chore.objects.create(
            household=household,
            title="Finished task",
            owner=alice,
            created_by=alice,
            status=ChoreStatus.COMPLETED,
            completed_at=timezone.now(),
            completed_by=alice,
        )
        Chore.objects.create(household=household, title="Pending task", owner=bob, created_by=bob)

        response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))
        content = response.content.decode()

        assert "Pending task" in content
        assert "Finished task" not in content
