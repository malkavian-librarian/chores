from django.urls import path

from . import views

app_name = "chores"

urlpatterns = [
    path("h/<str:slug>/chores/add/", views.quick_add, name="quick_add"),
    path("h/<str:slug>/chores/<int:chore_id>/", views.chore_detail, name="chore_detail"),
    path("h/<str:slug>/chores/<int:chore_id>/delete/", views.chore_delete, name="chore_delete"),
    path(
        "h/<str:slug>/chores/<int:chore_id>/complete/", views.chore_complete, name="chore_complete"
    ),
    path(
        "h/<str:slug>/chores/<int:chore_id>/completed/",
        views.chore_just_completed,
        name="chore_just_completed",
    ),
    path("h/<str:slug>/chores/<int:chore_id>/undo/", views.chore_undo, name="chore_undo"),
    path(
        "h/<str:slug>/chores/<int:chore_id>/add-note/",
        views.chore_add_note,
        name="chore_add_note",
    ),
]
