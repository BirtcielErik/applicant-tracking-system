from django.db import transaction
from django.utils import timezone

from .models import Application, Skill, StageChange
from .pipeline import EXIT_STAGES, refusal_reason


class MoveRefused(Exception):
    pass


class ApplicationRefused(Exception):
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


def application_refusal_reason(candidate, job, application_date):
    if job.is_closed:
        return "This job is closed, so it cannot receive new applications."
    if candidate.is_archived:
        return "This candidate is archived, so they cannot receive new applications."
    existing = Application.objects.filter(candidate=candidate, job=job).first()
    if existing:
        if existing.stage in EXIT_STAGES:
            return (
                f"This candidate's application to this job is "
                f"{existing.get_stage_display()}, but a hiring manager can reopen it."
            )
        return "This candidate has already applied to this job."
    if application_date > timezone.localdate():
        return "The application date cannot be in the future."
    return None


@transaction.atomic
def create_application(user, candidate, job, application_date):
    reason = application_refusal_reason(candidate, job, application_date)
    if reason:
        raise ApplicationRefused(reason)
    application = Application.objects.create(
        candidate=candidate, job=job, application_date=application_date
    )
    StageChange.objects.create(
        application=application,
        to_stage=application.stage,
        changed_by=user,
        reason=StageChange.Reason.APPLICATION_CREATED,
    )
    return application


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
