from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "ats"

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="ats/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.home, name="home"),
    path("jobs/new/", views.job_create, name="job_create"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/edit/", views.job_edit, name="job_edit"),
    path("jobs/<int:pk>/close/", views.job_close, name="job_close"),
    path("jobs/<int:pk>/reopen/", views.job_reopen, name="job_reopen"),
    path(
        "jobs/<int:pk>/applications/new/",
        views.job_application_create,
        name="job_application_create",
    ),
    path("skills/", views.skill_list, name="skill_list"),
    path("skills/add/", views.skill_add, name="skill_add"),
    path("skills/<int:pk>/rename/", views.skill_rename, name="skill_rename"),
    path("skills/<int:pk>/delete/", views.skill_delete, name="skill_delete"),
    path("candidates/", views.candidate_list, name="candidate_list"),
    path("candidates/new/", views.candidate_create, name="candidate_create"),
    path("candidates/<int:pk>/", views.candidate_detail, name="candidate_detail"),
    path("candidates/<int:pk>/edit/", views.candidate_edit, name="candidate_edit"),
    path(
        "candidates/<int:pk>/archive/",
        views.candidate_archive,
        name="candidate_archive",
    ),
    path(
        "candidates/<int:pk>/unarchive/",
        views.candidate_unarchive,
        name="candidate_unarchive",
    ),
    path(
        "candidates/<int:pk>/notes/",
        views.candidate_note_add,
        name="candidate_note_add",
    ),
    path(
        "candidates/<int:pk>/applications/new/",
        views.candidate_application_create,
        name="candidate_application_create",
    ),
    path(
        "applications/<int:pk>/move/",
        views.application_move,
        name="application_move",
    ),
]
