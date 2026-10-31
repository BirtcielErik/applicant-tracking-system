from itertools import permutations

import pytest

from ats.models import JobOpening
from ats.pipeline import ACTIVE_STAGES, EXIT_STAGES, Stage, can_transition
from ats.services import move_application
from ats.tests.conftest import make_application

EVERYONE = ("recruiter", "manager", "dual_role_user")
MANAGERS = ("manager", "dual_role_user")

# The plan's transition table. Any pair not listed is refused for every role.
TRANSITIONS = [
    (ACTIVE_STAGES, ACTIVE_STAGES, EVERYONE),
    ((Stage.FINAL_REVIEW,), (Stage.OFFER,), MANAGERS),
    ((Stage.OFFER,), (Stage.HIRED,), MANAGERS),
    ((Stage.OFFER,), ACTIVE_STAGES, MANAGERS),
    ((*ACTIVE_STAGES, Stage.OFFER), EXIT_STAGES, EVERYONE),
    ((Stage.HIRED,), tuple(Stage), MANAGERS),
]


def roles_allowed(from_stage, target):
    for from_stages, targets, roles in TRANSITIONS:
        if from_stage in from_stages and target in targets:
            return roles
    return ()


def close_job(application):
    application.job.status = JobOpening.Status.CLOSED
    application.job.save()


def archive_candidate(application):
    application.candidate.is_archived = True
    application.candidate.save()


@pytest.mark.parametrize("role", EVERYONE)
@pytest.mark.parametrize(("from_stage", "target"), list(permutations(Stage, 2)))
def test_can_transition_matches_the_transition_table(
    request, job, role, from_stage, target
):
    user = request.getfixturevalue(role)
    application = make_application(job, from_stage)

    assert can_transition(user, application, target) == (
        role in roles_allowed(from_stage, target)
    )


@pytest.mark.parametrize("role", EVERYONE)
@pytest.mark.parametrize("stage", list(Stage))
def test_moving_to_the_current_stage_is_not_a_move(request, job, role, stage):
    user = request.getfixturevalue(role)
    application = make_application(job, stage)

    assert not can_transition(user, application, stage)


@pytest.mark.parametrize("block", [close_job, archive_candidate])
@pytest.mark.parametrize(
    ("stages_held", "target", "allowed"),
    [
        ([Stage.INTERVIEW], Stage.SCREENING, False),
        ([Stage.FINAL_REVIEW], Stage.OFFER, False),
        ([Stage.OFFER], Stage.HIRED, False),
        ([Stage.OFFER], Stage.FINAL_REVIEW, False),
        ([Stage.HIRED], Stage.OFFER, False),
        ([Stage.INTERVIEW, Stage.REJECTED], Stage.INTERVIEW, False),
        ([Stage.OFFER, Stage.WITHDRAWN], Stage.OFFER, False),
        ([Stage.HIRED, Stage.REJECTED], Stage.HIRED, False),
        ([Stage.INTERVIEW], Stage.REJECTED, True),
        ([Stage.OFFER], Stage.WITHDRAWN, True),
        ([Stage.HIRED], Stage.REJECTED, True),
    ],
)
def test_in_progress_guard_refuses_entry_and_allows_exits(
    job, manager, block, stages_held, target, allowed
):
    application = make_application(job, stages_held[0])
    for stage in stages_held[1:]:
        move_application(manager, application, stage)
    block(application)

    assert can_transition(manager, application, target) == allowed
