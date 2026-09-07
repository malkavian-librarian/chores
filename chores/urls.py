from django.urls import path

from . import views

app_name = "chores"

urlpatterns = [
    path("h/<str:slug>/chores/add/", views.quick_add, name="quick_add"),
]
