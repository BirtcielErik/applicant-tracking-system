import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse


@pytest.mark.parametrize(
    "model", ["candidate", "jobopening", "application", "stagechange"]
)
def test_admin_can_open_pipeline_model_pages(client, superuser, model):
    client.force_login(superuser)

    assert client.get(reverse(f"admin:ats_{model}_changelist")).status_code == 200
    assert client.get(reverse(f"admin:ats_{model}_add")).status_code == 200


def test_admin_login_is_reachable_while_signed_out(client):
    assert client.get(reverse("admin:login")).status_code == 200


def test_admin_redirects_anonymous_visitors_to_admin_login(client):
    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("admin:login"))


def test_admin_can_create_a_user(client, superuser):
    client.force_login(superuser)

    response = client.post(
        reverse("admin:ats_user_add"),
        {
            "username": "new-recruiter",
            "usable_password": "true",
            "password1": "a-Long-pass-phrase-1",
            "password2": "a-Long-pass-phrase-1",
        },
    )

    assert response.status_code == 302
    assert get_user_model().objects.filter(username="new-recruiter").exists()


def test_admin_can_assign_roles_to_a_user(client, superuser, recruiter):
    groups = Group.objects.filter(name__in=["Recruiter", "Hiring Manager"])
    client.force_login(superuser)

    response = client.post(
        reverse("admin:ats_user_change", args=[recruiter.pk]),
        {
            "username": recruiter.username,
            "is_active": "on",
            "groups": [group.pk for group in groups],
            "date_joined_0": "2026-10-31",
            "date_joined_1": "12:00:00",
        },
    )

    assert response.status_code == 302
    assert set(recruiter.groups.all()) == set(groups)
    assert recruiter.has_perm("ats.make_offer")
