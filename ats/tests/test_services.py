from itertools import permutations

import pytest
from django.db import IntegrityError, transaction

from ats.models import Application, StageChange
from ats.pipeline import ACTIVE_STAGES, Stage
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

    with pytest.raises(MoveRefused):
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


@pytest.mark.parametrize("target", [Stage.INTERVIEW, "not-a-stage", None])
def test_move_to_current_or_invalid_stage_is_refused(job, recruiter, target):
    application = make_application(job, Stage.INTERVIEW)

    with pytest.raises(MoveRefused):
        move_application(recruiter, application, target)

    assert not StageChange.objects.exists()
