import pytest
from django.db import IntegrityError

from households.models import Household


@pytest.mark.django_db
class TestHouseholdModel:
    def test_fields(self):
        household = Household.objects.create(slug="abc123")

        assert household.slug == "abc123"
        assert household.created_at is not None

    def test_slug_is_unique(self):
        Household.objects.create(slug="dup-slug")

        with pytest.raises(IntegrityError):
            Household.objects.create(slug="dup-slug")

    def test_create_with_unique_slug_uses_token_urlsafe(self, monkeypatch):
        monkeypatch.setattr("households.models.secrets.token_urlsafe", lambda n: "fixed-token")

        household = Household.create_with_unique_slug()

        assert household.slug == "fixed-token"

    def test_create_with_unique_slug_retries_on_collision(self, monkeypatch):
        """Forces a collision on the first attempt and asserts creation
        still succeeds with a different slug on retry (issue #2's
        collision policy)."""
        Household.objects.create(slug="taken")

        tokens = iter(["taken", "taken", "fresh"])
        monkeypatch.setattr("households.models.secrets.token_urlsafe", lambda n: next(tokens))

        household = Household.create_with_unique_slug()

        assert household.slug == "fresh"
        assert Household.objects.filter(slug="taken").count() == 1

    def test_create_with_unique_slug_gives_up_after_max_attempts(self, monkeypatch):
        Household.objects.create(slug="always-taken")
        monkeypatch.setattr("households.models.secrets.token_urlsafe", lambda n: "always-taken")

        with pytest.raises(RuntimeError):
            Household.create_with_unique_slug()
