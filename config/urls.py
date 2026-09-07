"""URL configuration for the chores project."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("categories.urls")),
    path("", include("households.urls")),
    path("", include("chores.urls")),
]
