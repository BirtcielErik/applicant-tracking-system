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
    path("candidates/", views.candidate_list, name="candidate_list"),
    path("candidates/new/", views.candidate_create, name="candidate_create"),
    path("candidates/<int:pk>/", views.candidate_detail, name="candidate_detail"),
    path("candidates/<int:pk>/edit/", views.candidate_edit, name="candidate_edit"),
    path(
        "applications/<int:pk>/move/",
        views.application_move,
        name="application_move",
    ),
]
