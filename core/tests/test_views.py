import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_returns_200(client):
    """The placeholder homepage responds successfully.

    This is the toolchain-proving test for the project skeleton: it
    exercises the URL config, view, and test database wiring end to
    end (per `_docs/arch.md` §7 and issue #1's acceptance criteria).
    """
    response = client.get(reverse("home"))

    assert response.status_code == 200
