import datetime
from urllib.parse import quote

import pytest
from django.urls import reverse
from django.utils import timezone

from chores.models import Chore, ChoreStatus
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


@pytest.mark.django_db
class TestDetailViewChoreList:
    """Issue #9: the shared, ordered active-chore list and empty state."""

    def _household_with_partners(self, slug, name_1="Alex", name_2="Sam"):
        household = Household.objects.create(slug=slug)
        partner_1 = Partner.objects.create(household=household, name=name_1)
        partner_2 = Partner.objects.create(household=household, name=name_2)
        return household, partner_1, partner_2

    def _url(self, household):
        return reverse("households:detail", kwargs={"slug": household.slug})

    def test_empty_state_shown_with_zero_active_chores(self, client):
        household, alex, sam = self._household_with_partners("chores-empty")

        response = client.get(self._url(household))

        content = response.content.decode()
        assert "All done \U0001f389" in content
        assert reverse("chores:quick_add", kwargs={"slug": household.slug}) in content

    def test_empty_state_hidden_when_active_chore_exists(self, client):
        household, alex, sam = self._household_with_partners("chores-not-empty")
        Chore.objects.create(household=household, title="Wash dishes", owner=alex, created_by=alex)

        response = client.get(self._url(household))

        content = response.content.decode()
        assert "All done \U0001f389" not in content
        assert "Wash dishes" in content

    def test_completed_chores_never_appear(self, client):
        household, alex, sam = self._household_with_partners("chores-completed")
        Chore.objects.create(
            household=household,
            title="Done already",
            owner=alex,
            created_by=alex,
            status=ChoreStatus.COMPLETED,
        )

        response = client.get(self._url(household))

        content = response.content.decode()
        assert "Done already" not in content
        assert "All done \U0001f389" in content

    def test_chores_from_both_partners_appear_in_one_list(self, client):
        household, alex, sam = self._household_with_partners("chores-both-partners")
        Chore.objects.create(household=household, title="Alex chore", owner=alex, created_by=alex)
        Chore.objects.create(household=household, title="Sam chore", owner=sam, created_by=sam)

        response = client.get(self._url(household))

        content = response.content.decode()
        assert "Alex chore" in content
        assert "Sam chore" in content

    def test_ordering_by_owner_name_then_due_date(self, client):
        household, alex, sam = self._household_with_partners("chores-ordering", "Bea", "Amy")
        Chore.objects.create(
            household=household,
            title="Amy late",
            owner=sam,
            created_by=sam,
            due_date=datetime.date(2026, 1, 10),
        )
        Chore.objects.create(
            household=household,
            title="Amy early",
            owner=sam,
            created_by=sam,
            due_date=datetime.date(2026, 1, 1),
        )
        Chore.objects.create(
            household=household,
            title="Bea chore",
            owner=alex,
            created_by=alex,
            due_date=datetime.date(2026, 1, 1),
        )

        response = client.get(self._url(household))

        titles = [c.title for c in response.context["active_chores"]]
        assert titles == ["Amy early", "Amy late", "Bea chore"]

    def test_ordering_nulls_last_within_same_owner(self, client):
        household, alex, sam = self._household_with_partners("chores-nulls-last")
        Chore.objects.create(household=household, title="No due date", owner=alex, created_by=alex)
        Chore.objects.create(
            household=household,
            title="Has due date",
            owner=alex,
            created_by=alex,
            due_date=datetime.date(2026, 1, 1),
        )

        response = client.get(self._url(household))

        titles = [c.title for c in response.context["active_chores"]]
        assert titles == ["Has due date", "No due date"]

    def test_ordering_is_case_insensitive_by_owner_name(self, client):
        household, alex, sam = self._household_with_partners(
            "chores-case-insensitive", "bea", "Amy"
        )
        Chore.objects.create(household=household, title="bea chore", owner=alex, created_by=alex)
        Chore.objects.create(household=household, title="Amy chore", owner=sam, created_by=sam)

        response = client.get(self._url(household))

        titles = [c.title for c in response.context["active_chores"]]
        assert titles == ["Amy chore", "bea chore"]


@pytest.mark.django_db
class TestDetailViewOverdueMarking:
    """Issue #10: visible "Overdue" marker on past-due chores."""

    def _household_with_partners(self, slug, name_1="Alex", name_2="Sam"):
        household = Household.objects.create(slug=slug)
        partner_1 = Partner.objects.create(household=household, name=name_1)
        partner_2 = Partner.objects.create(household=household, name=name_2)
        return household, partner_1, partner_2

    def _url(self, household):
        return reverse("households:detail", kwargs={"slug": household.slug})

    def test_past_due_date_is_marked_overdue(self, client):
        household, alex, sam = self._household_with_partners("overdue-past")
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        Chore.objects.create(
            household=household,
            title="Late chore",
            owner=alex,
            created_by=alex,
            due_date=yesterday,
        )

        response = client.get(self._url(household))

        content = response.content.decode()
        assert "Overdue" in content
        chore = response.context["active_chores"][0]
        assert chore.is_overdue is True

    def test_due_date_today_is_not_overdue(self, client):
        household, alex, sam = self._household_with_partners("overdue-today")
        today = timezone.localdate()
        Chore.objects.create(
            household=household,
            title="Due today chore",
            owner=alex,
            created_by=alex,
            due_date=today,
        )

        response = client.get(self._url(household))

        content = response.content.decode()
        assert "Overdue" not in content
        chore = response.context["active_chores"][0]
        assert chore.is_overdue is False

    def test_future_due_date_is_not_overdue(self, client):
        household, alex, sam = self._household_with_partners("overdue-future")
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        Chore.objects.create(
            household=household,
            title="Future chore",
            owner=alex,
            created_by=alex,
            due_date=tomorrow,
        )

        response = client.get(self._url(household))

        content = response.content.decode()
        assert "Overdue" not in content
        chore = response.context["active_chores"][0]
        assert chore.is_overdue is False

    def test_no_due_date_is_not_overdue(self, client):
        household, alex, sam = self._household_with_partners("overdue-none")
        Chore.objects.create(
            household=household,
            title="No due date chore",
            owner=alex,
            created_by=alex,
        )

        response = client.get(self._url(household))

        content = response.content.decode()
        assert "Overdue" not in content
        chore = response.context["active_chores"][0]
        assert chore.is_overdue is False

    def test_ordering_unaffected_by_overdue_status(self, client):
        household, alex, sam = self._household_with_partners("overdue-ordering", "Bea", "Amy")
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        Chore.objects.create(
            household=household,
            title="Amy late overdue",
            owner=sam,
            created_by=sam,
            due_date=yesterday,
        )
        Chore.objects.create(
            household=household,
            title="Amy early",
            owner=sam,
            created_by=sam,
            due_date=datetime.date(2026, 1, 1),
        )
        Chore.objects.create(
            household=household,
            title="Bea chore",
            owner=alex,
            created_by=alex,
            due_date=datetime.date(2026, 1, 1),
        )

        response = client.get(self._url(household))

        titles = [c.title for c in response.context["active_chores"]]
        assert titles == ["Amy early", "Amy late overdue", "Bea chore"]
