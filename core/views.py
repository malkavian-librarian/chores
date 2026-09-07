"""Placeholder views for the project skeleton.

No domain features live here yet — see `households`, `chores`, and
`categories` apps (added in later tasks) for real functionality.
"""

from django.http import HttpResponse


def home(request):
    """Bare placeholder homepage, just enough to prove the toolchain works."""
    return HttpResponse("Chores")
