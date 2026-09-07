"""Tests for the household-scoped Settings page (issue #19).

Covers: rendering with current names pre-filled, a successful rename
(same pk via `refresh_from_db`), the FK-display propagation into chore
ownership/history on the household detail page, blank/whitespace/
too-long rejection, duplicate-name-allowed, a no-op rename, and the
0/1-partner redirect. Per `_docs/arch.md` §7: pytest + pytest-django,
no `unittest.TestCase`.
"""

import pytest
from django.urls import reverse

from chores.models import Chore, ChoreStatus
from households.models import PARTNER_NAME_MAX_LENGTH, Household, Partner


@pytest.fixture
def household_with_partners():
    household = Household.create_with_unique_slug()
    partner_1 = Partner.objects.create(household=household, name="Alex")
    partner_2 = Partner.objects.create(household=household, name="Sam")
    return household, partner_1, partner_2


def _settings_url(household):
    return reverse("households:settings", kwargs={"slug": household.slug})


@pytest.mark.django_db
class TestSettingsGet:
    def test_shows_both_partners_current_names_prefilled(self, client, household_with_partners):
        household, partner_1, partner_2 = household_with_partners

        response = client.get(_settings_url(household))
        content = response.content.decode()

        assert response.status_code == 200
        assert 'value="Alex"' in content
        assert 'value="Sam"' in content


@pytest.mark.django_db
class TestSettingsRename:
    def test_valid_rename_updates_correct_partner_row(self, client, household_with_partners):
        household, partner_1, partner_2 = household_with_partners

        response = client.post(
            _settings_url(household),
            {"partner_1_name": "Alexandra", "partner_2_name": "Sam"},
        )

        assert response.status_code == 302
        partner_1_pk_before = partner_1.pk
        partner_2_pk_before = partner_2.pk
        partner_1.refresh_from_db()
        partner_2.refresh_from_db()
        assert partner_1.pk == partner_1_pk_before
        assert partner_2.pk == partner_2_pk_before
        assert partner_1.name == "Alexandra"
        assert partner_2.name == "Sam"

    def test_rename_trims_leading_and_trailing_whitespace(self, client, household_with_partners):
        household, partner_1, partner_2 = household_with_partners

        client.post(
            _settings_url(household),
            {"partner_1_name": "  Alexandra ", "partner_2_name": "Sam"},
        )

        partner_1.refresh_from_db()
        assert partner_1.name == "Alexandra"

    def test_rename_to_own_current_name_is_a_noop_success(self, client, household_with_partners):
        household, partner_1, partner_2 = household_with_partners

        response = client.post(
            _settings_url(household),
            {"partner_1_name": "Alex", "partner_2_name": "Sam"},
        )

        assert response.status_code == 302
        partner_1.refresh_from_db()
        partner_2.refresh_from_db()
        assert partner_1.name == "Alex"
        assert partner_2.name == "Sam"

    def test_duplicate_names_across_partners_allowed(self, client, household_with_partners):
        household, partner_1, partner_2 = household_with_partners

        response = client.post(
            _settings_url(household),
            {"partner_1_name": "Jordan", "partner_2_name": "Jordan"},
        )

        assert response.status_code == 302
        partner_1.refresh_from_db()
        partner_2.refresh_from_db()
        assert partner_1.name == "Jordan"
        assert partner_2.name == "Jordan"

    def test_successful_rename_redirects_back_to_settings(self, client, household_with_partners):
        household, partner_1, partner_2 = household_with_partners

        response = client.post(
            _settings_url(household),
            {"partner_1_name": "Alexandra", "partner_2_name": "Sam"},
        )

        assert response.url == _settings_url(household)

        follow_up = client.get(response.url)
        content = follow_up.content.decode()
        assert 'value="Alexandra"' in content
        assert "messages" not in content or "error" not in content.lower()


@pytest.mark.django_db
class TestSettingsRenameValidation:
    def test_blank_name_rejected_and_old_name_unchanged(self, client, household_with_partners):
        household, partner_1, partner_2 = household_with_partners

        response = client.post(
            _settings_url(household),
            {"partner_1_name": "", "partner_2_name": "Sam"},
        )

        assert response.status_code == 200
        partner_1.refresh_from_db()
        assert partner_1.name == "Alex"
        assert response.context["form"].errors

    def test_whitespace_only_name_rejected_and_old_name_unchanged(
        self, client, household_with_partners
    ):
        household, partner_1, partner_2 = household_with_partners

        response = client.post(
            _settings_url(household),
            {"partner_1_name": "   ", "partner_2_name": "Sam"},
        )

        assert response.status_code == 200
        partner_1.refresh_from_db()
        assert partner_1.name == "Alex"
        assert response.context["form"].errors

    def test_too_long_name_rejected_and_old_name_unchanged(self, client, household_with_partners):
        household, partner_1, partner_2 = household_with_partners
        too_long = "x" * (PARTNER_NAME_MAX_LENGTH + 1)

        response = client.post(
            _settings_url(household),
            {"partner_1_name": too_long, "partner_2_name": "Sam"},
        )

        assert response.status_code == 200
        partner_1.refresh_from_db()
        assert partner_1.name == "Alex"
        assert response.context["form"].errors


@pytest.mark.django_db
class TestSettingsFewerThanTwoPartners:
    def test_zero_partners_redirects_to_household_detail(self, client):
        household = Household.create_with_unique_slug()

        response = client.get(_settings_url(household))

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})

    def test_one_partner_redirects_to_household_detail(self, client):
        household = Household.create_with_unique_slug()
        Partner.objects.create(household=household, name="Alex")

        response = client.get(_settings_url(household))

        assert response.status_code == 302
        assert response.url == reverse("households:detail", kwargs={"slug": household.slug})


@pytest.mark.django_db
class TestRenamePropagatesViaForeignKey:
    def test_rename_reflects_in_active_chore_owner_and_completed_history(
        self, client, household_with_partners
    ):
        household, partner_1, partner_2 = household_with_partners

        active_chore = Chore.objects.create(
            household=household,
            title="Wash dishes",
            owner=partner_1,
            created_by=partner_1,
            status=ChoreStatus.ACTIVE,
        )
        completed_chore = Chore.objects.create(
            household=household,
            title="Vacuum",
            owner=partner_2,
            created_by=partner_2,
            status=ChoreStatus.COMPLETED,
            completed_by=partner_2,
        )

        response = client.post(
            _settings_url(household),
            {"partner_1_name": "Alexandra", "partner_2_name": "Samantha"},
        )
        assert response.status_code == 302

        detail_response = client.get(reverse("households:detail", kwargs={"slug": household.slug}))
        content = detail_response.content.decode()

        assert "Alexandra" in content
        assert "Samantha" in content
        assert "Alex<" not in content

        # No copied string on the Chore rows -- the display is purely via
        # the FK, so re-fetching the same rows shows the new names too.
        active_chore.refresh_from_db()
        completed_chore.refresh_from_db()
        assert active_chore.owner.name == "Alexandra"
        assert completed_chore.completed_by.name == "Samantha"
