"""Tests for the optional completion note, issue #13.

Covers the acceptance criteria: the "Add note" form is present
alongside Undo on the one-time confirmation page; a non-blank note
saves to `chore.note`; blank/whitespace-only text is treated as no
note and stored as `""`, not a string of spaces; resubmitting a note
overwrites rather than appends; skipping the note entirely (never
POSTing to add-note) leaves `note` as `""` and the completion
untouched; Undo clears the note along with the other completion
fields; the endpoint requires an acting-as partner and only applies
while the chore is currently completed; GET never mutates.
"""

import pytest
from django.urls import reverse

from chores.models import Chore, ChoreStatus
from households.models import Household, Partner
from households.views import _acting_as_session_key


@pytest.mark.django_db
class TestChoreAddNote:
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

    def _add_note_url(self, household, chore):
        return reverse(
            "chores:chore_add_note", kwargs={"slug": household.slug, "chore_id": chore.pk}
        )

    def _undo_url(self, household, chore):
        return reverse("chores:chore_undo", kwargs={"slug": household.slug, "chore_id": chore.pk})

    def _detail_url(self, household, chore):
        return reverse("chores:chore_detail", kwargs={"slug": household.slug, "chore_id": chore.pk})

    def _act_as(self, client, household, partner):
        session = client.session
        session[_acting_as_session_key(household.slug)] = partner.pk
        session.save()

    # -- "Add note" is shown alongside Undo --

    def test_just_completed_page_shows_add_note_form(self, client):
        household, alice, bob = self._household_with_partners("note-page-shows-form")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        client.post(self._complete_url(household, chore))
        response = client.get(self._just_completed_url(household, chore))

        content = response.content.decode()
        assert ">Undo<" in content
        assert self._add_note_url(household, chore) in content

    # -- non-blank note saves --

    def test_non_blank_note_saves_to_chore(self, client):
        household, alice, bob = self._household_with_partners("note-saves-non-blank")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))

        response = client.post(self._add_note_url(household, chore), {"note": "Used the good soap"})

        assert response.status_code == 200
        chore.refresh_from_db()
        assert chore.note == "Used the good soap"
        assert chore.status == ChoreStatus.COMPLETED

    def test_note_is_stripped_before_saving(self, client):
        household, alice, bob = self._household_with_partners("note-stripped")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))

        client.post(self._add_note_url(household, chore), {"note": "  padded note  "})

        chore.refresh_from_db()
        assert chore.note == "padded note"

    # -- blank/whitespace treated as no note --

    def test_blank_note_is_stored_as_empty_string(self, client):
        household, alice, bob = self._household_with_partners("note-blank-stored-empty")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))

        client.post(self._add_note_url(household, chore), {"note": ""})

        chore.refresh_from_db()
        assert chore.note == ""

    def test_whitespace_only_note_is_stored_as_empty_string_not_spaces(self, client):
        household, alice, bob = self._household_with_partners("note-whitespace-empty")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))

        client.post(self._add_note_url(household, chore), {"note": "   \t  "})

        chore.refresh_from_db()
        assert chore.note == ""

    # -- resubmitting overwrites, doesn't append --

    def test_resubmitting_a_note_overwrites_rather_than_appends(self, client):
        household, alice, bob = self._household_with_partners("note-resubmit-overwrites")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))

        client.post(self._add_note_url(household, chore), {"note": "First note"})
        client.post(self._add_note_url(household, chore), {"note": "Second note"})

        chore.refresh_from_db()
        assert chore.note == "Second note"
        assert "First note" not in chore.note

    # -- skipping is the default, non-blocking path --

    def test_skipping_the_note_leaves_it_empty_and_completion_untouched(self, client):
        household, alice, bob = self._household_with_partners("note-skip-default")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        response = client.post(self._complete_url(household, chore))

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.status == ChoreStatus.COMPLETED
        assert chore.note == ""

    # -- Undo clears the note --

    def test_undo_clears_the_note(self, client):
        household, alice, bob = self._household_with_partners("note-undo-clears")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))
        client.post(self._add_note_url(household, chore), {"note": "Some note"})

        response = client.post(self._undo_url(household, chore))

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.note == ""
        assert chore.status == ChoreStatus.ACTIVE
        assert chore.completed_at is None
        assert chore.completed_by is None

    # -- permission mirrors chore_complete --

    def test_add_note_with_no_acting_as_is_rejected_and_untouched(self, client):
        household, alice, bob = self._household_with_partners("note-reject-no-acting-as")
        chore = self._chore(household, owner=alice, created_by=alice, status=ChoreStatus.COMPLETED)

        response = client.post(self._add_note_url(household, chore), {"note": "Sneaky note"})

        assert response.status_code == 403
        chore.refresh_from_db()
        assert chore.note == ""

    def test_add_note_when_chore_not_completed_is_a_noop(self, client):
        household, alice, bob = self._household_with_partners("note-noop-not-completed")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)

        response = client.post(self._add_note_url(household, chore), {"note": "Too early"})

        assert response.status_code == 302
        assert response.url == self._detail_url(household, chore)
        chore.refresh_from_db()
        assert chore.note == ""

    def test_get_on_add_note_url_does_not_mutate(self, client):
        household, alice, bob = self._household_with_partners("note-get-noop")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))

        response = client.get(self._add_note_url(household, chore))

        assert response.status_code == 302
        chore.refresh_from_db()
        assert chore.note == ""

    def test_no_max_length_enforced_on_note(self, client):
        household, alice, bob = self._household_with_partners("note-no-max-length")
        chore = self._chore(household, owner=alice, created_by=alice)
        self._act_as(client, household, alice)
        client.post(self._complete_url(household, chore))
        long_note = "x" * 5000

        client.post(self._add_note_url(household, chore), {"note": long_note})

        chore.refresh_from_db()
        assert chore.note == long_note
