import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


def make_user(username, *roles):
    user = get_user_model().objects.create_user(username, password="password")
    user.groups.set(Group.objects.filter(name__in=roles))
    return user


@pytest.fixture
def recruiter(db):
    return make_user("recruiter", "Recruiter")


@pytest.fixture
def manager(db):
    return make_user("manager", "Hiring Manager")


@pytest.fixture
def dual_role_user(db):
    return make_user("dual", "Recruiter", "Hiring Manager")
