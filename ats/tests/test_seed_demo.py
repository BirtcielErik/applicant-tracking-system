import pytest
from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command

from ats.management.commands.seed_demo import DEMO_PASSWORD
from ats.models import Application, Candidate, JobOpening, StageChange
from ats.pipeline import Stage
from ats.tests.conftest import make_application, make_candidate, make_user

pytestmark = pytest.mark.django_db


def row_counts():
    return [
        model.objects.count()
        for model in (
            get_user_model(),
            JobOpening,
            Candidate,
            Application,
            StageChange,
        )
    ]


def test_seed_demo_populates_every_stage_with_matching_history():
    call_command("seed_demo", verbosity=0)

    assert set(Application.objects.values_list("stage", flat=True)) == set(Stage.values)
    for application in Application.objects.all():
        assert application.stage_changes.first().to_stage == application.stage


def test_seed_demo_creates_a_user_in_each_role():
    call_command("seed_demo", verbosity=0)

    roles = {
        username: set(
            authenticate(username=username, password=DEMO_PASSWORD).groups.values_list(
                "name", flat=True
            )
        )
        for username in ("recruiter", "manager", "dual")
    }
    assert roles == {
        "recruiter": {"Recruiter"},
        "manager": {"Hiring Manager"},
        "dual": {"Recruiter", "Hiring Manager"},
    }


def test_seed_demo_resets_existing_data(job, recruiter):
    extra = make_application(job, candidate=make_candidate("Extra", "Person"))
    make_user("someone-else")
    call_command("seed_demo", verbosity=0)
    Application.objects.exclude(stage=Stage.APPLIED).update(stage=Stage.APPLIED)

    call_command("seed_demo", verbosity=0)

    assert not Application.objects.filter(pk=extra.pk).exists()
    assert not Candidate.objects.filter(first_name="Extra").exists()
    assert not get_user_model().objects.filter(username="someone-else").exists()
    assert set(Application.objects.values_list("stage", flat=True)) == set(Stage.values)


def test_seed_demo_restores_the_demo_password(manager):
    call_command("seed_demo", verbosity=0)

    assert authenticate(username="manager", password=DEMO_PASSWORD)


def test_seed_demo_keeps_superusers():
    get_user_model().objects.create_superuser("admin", password="original")

    call_command("seed_demo", verbosity=0)

    assert authenticate(username="admin", password="original")


def test_seed_demo_can_run_repeatedly():
    call_command("seed_demo", verbosity=0)
    first_run = row_counts()

    call_command("seed_demo", verbosity=0)

    assert row_counts() == first_run
