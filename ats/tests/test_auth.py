import pytest
from django.urls import NoReverseMatch, resolve, reverse
from django.urls.exceptions import Resolver404

from .conftest import make_user


def test_home_redirects_anonymous_visitors_to_login(client, recruiter):
    home_url = reverse("ats:home")

    response = client.get(home_url)

    assert response.status_code == 302
    assert response.url == f"{reverse('ats:login')}?next={home_url}"

    client.force_login(recruiter)

    assert client.get(home_url).status_code == 200


def test_login_page_is_public_and_uses_daisyui(client):
    response = client.get(reverse("ats:login"))

    assert response.status_code == 200
    assert 'class="btn btn-primary' in response.content.decode()


def test_login_with_valid_credentials_redirects_home(client, recruiter):
    response = client.post(
        reverse("ats:login"), {"username": "recruiter", "password": "password"}
    )

    assert response.status_code == 302
    assert response.url == reverse("ats:home")
    assert client.get(reverse("ats:home")).status_code == 200


def test_login_returns_to_the_requested_page(client, recruiter):
    response = client.post(
        reverse("ats:login"),
        {"username": "recruiter", "password": "password", "next": "/"},
    )

    assert response.url == "/"


def test_login_with_wrong_password_shows_an_error(client, recruiter):
    response = client.post(
        reverse("ats:login"), {"username": "recruiter", "password": "wrong"}
    )

    assert response.status_code == 200
    assert 'class="alert alert-error"' in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_signed_in_user_is_sent_away_from_login(client, recruiter):
    client.force_login(recruiter)

    response = client.get(reverse("ats:login"))

    assert response.status_code == 302
    assert response.url == reverse("ats:home")


def test_logout_ends_the_session(client, recruiter):
    client.force_login(recruiter)

    response = client.post(reverse("ats:logout"))

    assert response.status_code == 302
    assert response.url == reverse("ats:login")
    assert client.get(reverse("ats:home")).status_code == 302


def test_logout_refuses_get(client, recruiter):
    client.force_login(recruiter)

    assert client.get(reverse("ats:logout")).status_code == 405
    assert client.get(reverse("ats:home")).status_code == 200


def test_user_with_no_role_can_sign_in_but_has_no_permissions(client, db):
    user = make_user("no-role")
    client.force_login(user)

    assert client.get(reverse("ats:home")).status_code == 200
    assert user.get_all_permissions() == set()


@pytest.mark.parametrize("path", ["/signup/", "/register/", "/accounts/signup/"])
def test_there_is_no_public_signup_page(path):
    with pytest.raises(Resolver404):
        resolve(path)


def test_there_is_no_named_signup_route():
    with pytest.raises(NoReverseMatch):
        reverse("ats:signup")
