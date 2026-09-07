from django.urls import path

from . import views

app_name = "categories"

urlpatterns = [
    path("h/<str:slug>/categories/", views.index, name="index"),
    path("h/<str:slug>/categories/create/", views.create, name="create"),
    path("h/<str:slug>/categories/<int:pk>/rename/", views.rename, name="rename"),
    path("h/<str:slug>/categories/<int:pk>/delete/", views.delete, name="delete"),
]
