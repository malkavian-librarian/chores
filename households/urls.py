from django.urls import path

from . import views

app_name = "households"

urlpatterns = [
    path("", views.index, name="index"),
    path("h/<str:slug>/", views.detail, name="detail"),
    path("h/<str:slug>/settings/", views.settings, name="settings"),
    path("h/<str:slug>/settings/reset/", views.reset_data, name="reset_data"),
    path(
        "h/<str:slug>/settings/reset/confirm/",
        views.reset_data_confirm,
        name="reset_data_confirm",
    ),
    path("h/<str:slug>/acting-as/", views.set_acting_as, name="set_acting_as"),
]
