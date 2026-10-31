import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from ats.models import Application, Candidate, JobOpening
from ats.pipeline import Stage


def make_user(username, *roles):
    user = get_user_model().objects.create_user(username, password="password")
    user.groups.set(Group.objects.filter(name__in=roles))
    return user


def make_candidate(first_name="Jane", last_name="Doe"):
    return Candidate.objects.create(
        first_name=first_name,
        last_name=last_name,
        email=f"{first_name}.{last_name}@example.com".lower(),
        lead_source=Candidate.LeadSource.JOB_BOARD,
    )


def make_application(job, stage=Stage.APPLIED, candidate=None):
    return Application.objects.create(
        candidate=candidate or make_candidate(), job=job, stage=stage
    )


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def recruiter(db):
    return make_user("recruiter", "Recruiter")


@pytest.fixture
def manager(db):
    return make_user("manager", "Hiring Manager")


@pytest.fixture
def dual_role_user(db):
    return make_user("dual", "Recruiter", "Hiring Manager")


@pytest.fixture
def job(manager):
    return JobOpening.objects.create(title="Backend Engineer", created_by=manager)
