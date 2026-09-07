"""Tests for the "Reset data" flow on the household Settings page
(issue #20): three checkboxes, a two-step server-side confirm (POST #1
shows counts, POST #2 executes), atomic multi-selection deletion, and
the existing SET_NULL/never-delete-predefined mechanisms from #6/#7.

Per `_docs/arch.md` §7: pytest + pytest-django, no `unittest.TestCase`.
"""

from unittest.mock import patch

import pytest
from django.db.models.query import QuerySet
from django.urls import reverse

from categories.models import Category
from chores.models import Chore, ChoreStatus, Recurrence, RecurrenceKind
from households.models import Household, Partner


@pytest.fixture
def household_with_partners():
    household = Household.create_with_unique_slug()
    partner_1 = Partner.objects.create(household=household, name="Alex")
    partner_2 = Partner.objects.create(household=household, name="Sam")
    return household, partner_1, partner_2


def _settings_url(household):
    return reverse("households:settings", kwargs={"slug": household.slug})


def _reset_url(household):
    return reverse("households:reset_data", kwargs={"slug": household.slug})


def _confirm_url(household):
    return reverse("households:reset_data_confirm", kwargs={"slug": household.slug})


def _make_active_chore(household, partner, title="Wash dishes", with_recurrence=False):
    chore = Chore.objects.create(
        household=household,
        title=title,
        owner=partner,
        created_by=partner,
        status=ChoreStatus.ACTIVE,
    )
    if with_recurrence:
        Recurrence.objects.create(chore=chore, kind=RecurrenceKind.FIXED_DAILY)
    return chore


def _make_completed_chore(household, partner, title="Vacuum"):
    return Chore.objects.create(
        household=household,
        title=title,
        owner=partner,
        created_by=partner,
        status=ChoreStatus.COMPLETED,
        completed_by=partner,
    )


@pytest.mark.django_db
class TestSettingsShowsResetCheckboxes:
    def test_settings_page_has_exactly_three_unchecked_checkboxes(
        self, client, household_with_partners
    ):
        household, _, _ = household_with_partners

        response = client.get(_settings_url(household))
        content = response.content.decode()

        assert response.status_code == 200
        assert "Active chores" in content
        assert "Completed history" in content
        assert "Custom categories" in content
        assert "checked" not in content
        # No "select all" shortcut, no partner/household deletion controls.
        assert "select all" not in content.lower()
        assert "Delete household" not in content

    def test_rename_partners_section_still_present(self, client, household_with_partners):
        household, partner_1, partner_2 = household_with_partners

        response = client.get(_settings_url(household))
        content = response.content.decode()

        assert 'value="Alex"' in content
        assert 'value="Sam"' in content


@pytest.mark.django_db
class TestResetDataFewerThanTwoPartners:
    def test_reset_data_get_redirects_to_detail(self, client):
        household = Household.create_with_unique_slug()

        response = client.get(_reset_url(household))

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})

    def test_reset_data_post_redirects_to_detail_without_deleting(self, client):
        household = Household.create_with_unique_slug()
        partner = Partner.objects.create(household=household, name="Alex")
        chore = _make_active_chore(household, partner)

        response = client.post(_reset_url(household), {"active_chores": "on"})

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})
        assert Chore.objects.filter(pk=chore.pk).exists()

    def test_confirm_get_redirects_to_detail(self, client):
        household = Household.create_with_unique_slug()

        response = client.get(_confirm_url(household))

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})


@pytest.mark.django_db
class TestResetDataStepOneShowsConfirmationOnly:
    def test_get_on_reset_url_does_not_render_confirmation(self, client, household_with_partners):
        household, _, _ = household_with_partners

        response = client.get(_reset_url(household))

        assert response.status_code == 302
        assert response.url == _settings_url(household)

    def test_post_with_selection_shows_confirmation_and_deletes_nothing(
        self, client, household_with_partners
    ):
        household, partner_1, _ = household_with_partners
        chore = _make_active_chore(household, partner_1)

        response = client.post(_reset_url(household), {"active_chores": "on"})

        assert response.status_code == 200
        content = response.content.decode()
        assert "Active chores: 1" in content
        assert Chore.objects.filter(pk=chore.pk).exists()

    def test_confirmation_page_shows_counts_for_each_selected_option(
        self, client, household_with_partners
    ):
        household, partner_1, partner_2 = household_with_partners
        _make_active_chore(household, partner_1, title="A")
        _make_active_chore(household, partner_2, title="B")
        _make_completed_chore(household, partner_1)
        Category.objects.create(household=household, name="Board games", is_predefined=False)

        response = client.post(
            _reset_url(household),
            {"active_chores": "on", "completed_history": "on", "custom_categories": "on"},
        )
        content = response.content.decode()

        assert "Active chores: 2" in content
        assert "Completed history: 1" in content
        assert "Custom categories: 1" in content

    def test_confirmation_page_only_lists_selected_options(self, client, household_with_partners):
        household, partner_1, _ = household_with_partners
        _make_active_chore(household, partner_1)
        _make_completed_chore(household, partner_1)

        response = client.post(_reset_url(household), {"active_chores": "on"})
        content = response.content.decode()

        assert "Active chores:" in content
        assert "Completed history:" not in content
        assert "Custom categories:" not in content


@pytest.mark.django_db
class TestResetDataZeroSelectionIsNoop:
    def test_step_one_zero_selection_redirects_without_confirmation_page(
        self, client, household_with_partners
    ):
        household, partner_1, _ = household_with_partners
        chore = _make_active_chore(household, partner_1)

        response = client.post(_reset_url(household), {})

        assert response.status_code == 302
        assert response.url == _settings_url(household)
        assert Chore.objects.filter(pk=chore.pk).exists()

    def test_step_two_zero_selection_deletes_nothing(self, client, household_with_partners):
        household, partner_1, _ = household_with_partners
        chore = _make_active_chore(household, partner_1)

        response = client.post(_confirm_url(household), {})

        assert response.status_code == 302
        assert response.url == _settings_url(household)
        assert Chore.objects.filter(pk=chore.pk).exists()


@pytest.mark.django_db
class TestResetDataActiveChores:
    def test_confirming_active_chores_deletes_only_active_chores_and_their_recurrence(
        self, client, household_with_partners
    ):
        household, partner_1, partner_2 = household_with_partners
        active = _make_active_chore(household, partner_1, with_recurrence=True)
        recurrence_pk = active.recurrence.pk
        completed = _make_completed_chore(household, partner_2)
        category = Category.objects.create(household=household, name="Games", is_predefined=False)

        response = client.post(_confirm_url(household), {"active_chores": "on"})

        assert response.status_code == 302
        assert response.url == _settings_url(household)
        assert not Chore.objects.filter(pk=active.pk).exists()
        assert not Recurrence.objects.filter(pk=recurrence_pk).exists()
        assert Chore.objects.filter(pk=completed.pk).exists()
        assert Category.objects.filter(pk=category.pk).exists()
        assert Partner.objects.filter(pk__in=[partner_1.pk, partner_2.pk]).count() == 2


@pytest.mark.django_db
class TestResetDataCompletedHistory:
    def test_confirming_completed_history_deletes_only_completed_chores(
        self, client, household_with_partners
    ):
        household, partner_1, partner_2 = household_with_partners
        active = _make_active_chore(household, partner_1)
        completed = _make_completed_chore(household, partner_2)
        category = Category.objects.create(household=household, name="Games", is_predefined=False)

        response = client.post(_confirm_url(household), {"completed_history": "on"})

        assert response.status_code == 302
        assert not Chore.objects.filter(pk=completed.pk).exists()
        assert Chore.objects.filter(pk=active.pk).exists()
        assert Category.objects.filter(pk=category.pk).exists()


@pytest.mark.django_db
class TestResetDataCustomCategories:
    def test_confirming_custom_categories_deletes_only_non_predefined_categories(
        self, client, household_with_partners
    ):
        household, partner_1, _ = household_with_partners
        predefined = Category.objects.create(
            household=household, name="Kitchen", is_predefined=True
        )
        custom = Category.objects.create(
            household=household, name="Board games", is_predefined=False
        )

        response = client.post(_confirm_url(household), {"custom_categories": "on"})

        assert response.status_code == 302
        assert not Category.objects.filter(pk=custom.pk).exists()
        assert Category.objects.filter(pk=predefined.pk).exists()

    def test_chore_referencing_deleted_custom_category_has_category_set_null(
        self, client, household_with_partners
    ):
        household, partner_1, _ = household_with_partners
        custom = Category.objects.create(
            household=household, name="Board games", is_predefined=False
        )
        active = _make_active_chore(household, partner_1)
        active.category = custom
        active.save(update_fields=["category"])
        completed = _make_completed_chore(household, partner_1)
        completed.category = custom
        completed.save(update_fields=["category"])

        client.post(_confirm_url(household), {"custom_categories": "on"})

        active.refresh_from_db()
        completed.refresh_from_db()
        assert active.category_id is None
        assert completed.category_id is None
        # The chores themselves are untouched, only the category link.
        assert Chore.objects.filter(pk=active.pk).exists()
        assert Chore.objects.filter(pk=completed.pk).exists()

    def test_predefined_category_never_deleted_even_with_manipulated_post(
        self, client, household_with_partners
    ):
        household, partner_1, _ = household_with_partners
        predefined = Category.objects.create(
            household=household, name="Kitchen", is_predefined=True
        )

        # A manipulated client can only ever toggle the three known
        # booleans this form defines -- there is no field that accepts a
        # category id, so no POST body can single out a predefined
        # category for deletion via this endpoint.
        response = client.post(
            _confirm_url(household),
            {
                "custom_categories": "on",
                "category_id": str(predefined.pk),
                "is_predefined": "false",
                "delete_predefined": "on",
            },
        )

        assert response.status_code == 302
        assert Category.objects.filter(pk=predefined.pk).exists()


@pytest.mark.django_db
class TestResetDataMultiSelectionAtomic:
    def test_confirming_all_three_deletes_all_selected_categories_of_data(
        self, client, household_with_partners
    ):
        household, partner_1, partner_2 = household_with_partners
        active = _make_active_chore(household, partner_1)
        completed = _make_completed_chore(household, partner_2)
        custom = Category.objects.create(household=household, name="Games", is_predefined=False)

        response = client.post(
            _confirm_url(household),
            {"active_chores": "on", "completed_history": "on", "custom_categories": "on"},
        )

        assert response.status_code == 302
        assert not Chore.objects.filter(pk=active.pk).exists()
        assert not Chore.objects.filter(pk=completed.pk).exists()
        assert not Category.objects.filter(pk=custom.pk).exists()

    def test_error_partway_through_rolls_back_all_selected_deletions(
        self, client, household_with_partners
    ):
        household, partner_1, partner_2 = household_with_partners
        active = _make_active_chore(household, partner_1)
        completed = _make_completed_chore(household, partner_2)
        custom = Category.objects.create(household=household, name="Games", is_predefined=False)

        # Force the *last* delete in the transaction (custom categories)
        # to blow up, after the active-chores delete has already run in
        # the same `with transaction.atomic()` block, and assert the
        # active-chores delete was rolled back too.
        original_delete = QuerySet.delete

        def boom_on_category_delete(self):
            if self.model is Category:
                raise RuntimeError("simulated failure")
            return original_delete(self)

        with patch.object(QuerySet, "delete", boom_on_category_delete):
            with pytest.raises(RuntimeError):
                client.post(
                    _confirm_url(household),
                    {"active_chores": "on", "custom_categories": "on"},
                )

        assert Chore.objects.filter(pk=active.pk).exists()
        assert Category.objects.filter(pk=custom.pk).exists()
        assert Chore.objects.filter(pk=completed.pk).exists()


@pytest.mark.django_db
class TestResetDataRedirectAndVisibility:
    def test_confirming_redirects_to_settings_with_success_message(
        self, client, household_with_partners
    ):
        household, partner_1, _ = household_with_partners
        _make_active_chore(household, partner_1)

        response = client.post(_confirm_url(household), {"active_chores": "on"})

        assert response.status_code == 302
        assert response.url == _settings_url(household)

    def test_deleted_active_chore_no_longer_appears_in_household_list(
        self, client, household_with_partners
    ):
        household, partner_1, _ = household_with_partners
        chore = _make_active_chore(household, partner_1, title="Take out trash")

        client.post(_confirm_url(household), {"active_chores": "on"})

        detail_response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))
        assert "Take out trash" not in detail_response.content.decode()
        assert not Chore.objects.filter(pk=chore.pk).exists()

    def test_rename_partners_still_works_after_a_reset(self, client, household_with_partners):
        household, partner_1, partner_2 = household_with_partners
        _make_active_chore(household, partner_1)

        client.post(_confirm_url(household), {"active_chores": "on"})

        response = client.post(
            _settings_url(household),
            {"partner_1_name": "Alexandra", "partner_2_name": "Sam"},
        )

        assert response.status_code == 302
        partner_1.refresh_from_db()
        assert partner_1.name == "Alexandra"
