from itertools import permutations

import pytest
from django.db import IntegrityError, transaction

from ats.models import Application, StageChange
from ats.pipeline import ACTIVE_STAGES, EXIT_STAGES, Stage, can_transition
from ats.services import MoveRefused, move_application
from ats.tests.conftest import make_application


def test_candidate_can_only_apply_once_per_job(job):
    application = make_application(job)

    with pytest.raises(IntegrityError), transaction.atomic():
        Application.objects.create(candidate=application.candidate, job=job)


def test_move_between_active_stages_saves_stage_and_records_change(job, recruiter):
    application = make_application(job, Stage.INTERVIEW)

    move_application(recruiter, application, Stage.APPLIED)

    application.refresh_from_db()
    assert application.stage == Stage.APPLIED
    change = StageChange.objects.get(application=application)
    assert change.from_stage == Stage.INTERVIEW
    assert change.to_stage == Stage.APPLIED
    assert change.changed_by == recruiter
    assert change.changed_at is not None
    assert change.reason == StageChange.Reason.NORMAL_MOVE


def test_move_outside_active_stages_is_refused_and_changes_nothing(job, manager):
    application = make_application(job, Stage.APPLIED)

    with pytest.raises(MoveRefused, match="Only an application in Final Review"):
        move_application(manager, application, Stage.OFFER)

    application.refresh_from_db()
    assert application.stage == Stage.APPLIED
    assert not StageChange.objects.exists()


@pytest.mark.parametrize(("from_stage", "target"), list(permutations(ACTIVE_STAGES, 2)))
def test_every_active_to_active_move_is_allowed(job, recruiter, from_stage, target):
    application = make_application(job, from_stage)

    move_application(recruiter, application, target)

    application.refresh_from_db()
    assert application.stage == target


@pytest.mark.parametrize("exit_stage", EXIT_STAGES)
@pytest.mark.parametrize("previous", [Stage.INTERVIEW, Stage.OFFER, Stage.HIRED])
def test_manager_reopen_restores_previous_stage(job, manager, previous, exit_stage):
    application = make_application(job, previous)
    move_application(manager, application, exit_stage)

    assert can_transition(manager, application, previous)
    move_application(manager, application, previous)

    application.refresh_from_db()
    assert application.stage == previous
    change = application.stage_changes.first()
    assert change.from_stage == exit_stage
    assert change.to_stage == previous
    assert change.changed_by == manager
    assert change.reason == StageChange.Reason.APPLICATION_REOPENED


@pytest.mark.parametrize("exit_stage", EXIT_STAGES)
def test_only_a_manager_can_reopen_and_only_to_the_previous_stage(
    job, recruiter, manager, exit_stage
):
    application = make_application(job, Stage.OFFER)
    move_application(manager, application, exit_stage)

    assert not can_transition(recruiter, application, Stage.OFFER)
    for target in set(Stage) - {Stage.OFFER}:
        assert not can_transition(manager, application, target)


def test_reopen_without_exit_history_is_refused(job, manager):
    application = make_application(job, Stage.REJECTED)

    with pytest.raises(MoveRefused, match="no previous stage"):
        move_application(manager, application, Stage.APPLIED)


def test_refused_reopen_names_the_stage_it_can_return_to(job, manager):
    application = make_application(job, Stage.INTERVIEW)
    move_application(manager, application, Stage.REJECTED)

    with pytest.raises(MoveRefused, match="can only reopen to Interview"):
        move_application(manager, application, Stage.OFFER)


def test_reopen_uses_the_most_recent_exit(job, manager):
    application = make_application(job, Stage.INTERVIEW)
    move_application(manager, application, Stage.REJECTED)
    move_application(manager, application, Stage.INTERVIEW)
    move_application(manager, application, Stage.SCREENING)
    move_application(manager, application, Stage.WITHDRAWN)

    assert can_transition(manager, application, Stage.SCREENING)
    assert not can_transition(manager, application, Stage.INTERVIEW)


@pytest.mark.parametrize("target", [Stage.INTERVIEW, "not-a-stage", None])
def test_move_to_current_or_invalid_stage_is_refused(job, recruiter, target):
    application = make_application(job, Stage.INTERVIEW)

    with pytest.raises(MoveRefused):
        move_application(recruiter, application, target)

    assert not StageChange.objects.exists()
