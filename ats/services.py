from django.db import transaction

from .models import Skill, StageChange
from .pipeline import EXIT_STAGES, refusal_reason


class MoveRefused(Exception):
    pass


def save_candidate(candidate):
    candidate.full_clean()
    candidate.save()
    return candidate


@transaction.atomic
def save_job(user, job, skills=None):
    if job.pk is None:
        job.created_by = user
    job.full_clean()
    job.save()
    if skills is not None:
        job.skills.set(skills)
    return job


def get_or_create_skill(name):
    name = name.strip()
    existing = Skill.objects.filter(name__iexact=name).first()
    if existing:
        return existing
    skill = Skill(name=name)
    skill.full_clean()
    skill.save()
    return skill


def rename_skill(skill, name):
    skill.name = name.strip()
    skill.full_clean()
    skill.save()
    return skill


def delete_skill(skill):
    skill.delete()


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
