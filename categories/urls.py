from django.urls import path

from . import views

app_name = "categories"

urlpatterns = [
    path("h/<str:slug>/categories/", views.index, name="index"),
]
