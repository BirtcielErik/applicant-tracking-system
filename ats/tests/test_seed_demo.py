from datetime import timedelta

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.utils import timezone

from ats.management.commands.seed_demo import DEMO_PASSWORD
from ats.models import (
    Application,
    Candidate,
    CandidateNote,
    JobOpening,
    Skill,
    StageChange,
)
from ats.pipeline import Stage
from ats.tests.conftest import make_application, make_candidate, make_user

pytestmark = pytest.mark.django_db


def row_counts():
    return [
        model.objects.count()
        for model in (
            get_user_model(),
            JobOpening,
            Skill,
            Candidate,
            Application,
            StageChange,
            CandidateNote,
        )
    ]


def test_seed_demo_populates_every_stage_with_matching_history():
    call_command("seed_demo", verbosity=0)

    assert set(Application.objects.values_list("stage", flat=True)) == set(Stage.values)
    for application in Application.objects.all():
        assert application.stage_changes.first().to_stage == application.stage


def test_seed_demo_backdates_stage_history():
    call_command("seed_demo", verbosity=0)

    for application in Application.objects.all():
        latest = application.stage_changes.first()
        assert latest.changed_at < timezone.now() - timedelta(hours=1)


def test_seed_demo_includes_a_closed_job_and_an_archived_candidate():
    call_command("seed_demo", verbosity=0)

    closed = JobOpening.objects.get(status=JobOpening.Status.CLOSED)
    assert closed.closed_at is not None
    assert closed.applications.exists()
    assert Candidate.objects.get(is_archived=True).applications.exists()


def test_seed_demo_closes_its_job_through_the_real_close():
    call_command("seed_demo", verbosity=0)

    closed = JobOpening.objects.get(status=JobOpening.Status.CLOSED)
    closed_out = closed.applications.filter(
        stage_changes__reason=StageChange.Reason.JOB_CLOSED
    )
    assert closed_out.count() == 3
    assert closed_out.filter(candidate__is_archived=True).count() == 1


def test_seed_demo_tags_every_job_with_skills_and_shares_them_between_jobs():
    Skill.objects.create(name="Stale")

    call_command("seed_demo", verbosity=0)

    for job in JobOpening.objects.all():
        assert job.skills.exists()
    assert Skill.objects.get(name="Python").jobs.count() == 2
    assert not Skill.objects.filter(name="Stale").exists()


def test_seed_demo_adds_backdated_tagged_and_untagged_notes():
    call_command("seed_demo", verbosity=0)

    notes = CandidateNote.objects.all()
    assert notes.filter(application__isnull=True).exists()
    assert notes.filter(application__isnull=False).exists()
    for note in notes:
        assert note.created_at < timezone.now() - timedelta(hours=1)
        if note.application:
            assert note.application.candidate == note.candidate


def test_seed_demo_removes_notes_written_by_old_accounts():
    author = make_user("someone-else")
    CandidateNote.objects.create(
        candidate=make_candidate("Extra", "Person"), author=author, body="Old note"
    )

    call_command("seed_demo", verbosity=0)

    assert not CandidateNote.objects.filter(body="Old note").exists()
    assert not get_user_model().objects.filter(username="someone-else").exists()


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
