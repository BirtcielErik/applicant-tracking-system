from django.db import transaction

from .models import StageChange
from .pipeline import EXIT_STAGES, refusal_reason


class MoveRefused(Exception):
    pass


def save_candidate(candidate):
    candidate.full_clean()
    candidate.save()
    return candidate


def save_job(user, job):
    if job.pk is None:
        job.created_by = user
    job.full_clean()
    job.save()
    return job


@transaction.atomic
def move_application(user, application, target):
    reason = refusal_reason(user, application, target)
    if reason:
        raise MoveRefused(reason)
    from_stage = application.stage
    application.stage = target
    application.save(update_fields=["stage"])
    StageChange.objects.create(
        application=application,
        from_stage=from_stage,
        to_stage=target,
        changed_by=user,
        reason=(
            StageChange.Reason.APPLICATION_REOPENED
            if from_stage in EXIT_STAGES
            else StageChange.Reason.NORMAL_MOVE
        ),
    )
