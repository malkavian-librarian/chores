from django.urls import path

from . import views

app_name = "households"

urlpatterns = [
    path("", views.index, name="index"),
    path("h/<str:slug>/", views.detail, name="detail"),
]
