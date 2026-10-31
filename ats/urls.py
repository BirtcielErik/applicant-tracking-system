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
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path(
        "applications/<int:pk>/move/",
        views.application_move,
        name="application_move",
    ),
]
