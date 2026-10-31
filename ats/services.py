from django.db import transaction
from django.utils import timezone

from .models import Application, CandidateNote, JobOpening, Skill, StageChange
from .pipeline import (
    ACTIVE_STAGES,
    EXIT_STAGES,
    Stage,
    in_progress_refusal_reason,
    refusal_reason,
)


class MoveRefused(Exception):
    pass


class ApplicationRefused(Exception):
    pass


class JobCloseRefused(Exception):
    def __init__(self, message, applications=()):
        super().__init__(message)
        self.applications = applications


class JobReopenRefused(Exception):
    pass


class CandidateArchiveRefused(Exception):
    pass


class CandidateUnarchiveRefused(Exception):
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


def add_note(user, candidate, body, application=None):
    note = CandidateNote(
        candidate=candidate, author=user, body=body.strip(), application=application
    )
    note.full_clean()
    note.save()
    return note


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


def record_move(user, application, target, reason):
    from_stage = application.stage
    application.stage = target
    application.save(update_fields=["stage"])
    StageChange.objects.create(
        application=application,
        from_stage=from_stage,
        to_stage=target,
        changed_by=user,
        reason=reason,
    )


def offers_blocking_close(job):
    return job.applications.filter(stage=Stage.OFFER).select_related("candidate")


def applications_rejected_by_close(job):
    return job.applications.filter(stage__in=ACTIVE_STAGES)


def latest_changes_with_reason(applications, reason):
    """Return (application, change) pairs whose latest change has this reason."""
    pairs = (
        (application, application.stage_changes.first()) for application in applications
    )
    return [
        (application, change)
        for application, change in pairs
        if change and change.reason == reason
    ]


def applications_closed_out(job):
    return latest_changes_with_reason(
        job.applications.filter(stage=Stage.REJECTED).select_related("candidate"),
        StageChange.Reason.JOB_CLOSED,
    )


@transaction.atomic
def close_job(user, job):
    if job.is_closed:
        raise JobCloseRefused("This job is already closed.")
    offers = offers_blocking_close(job)
    if offers:
        raise JobCloseRefused(
            "This job cannot be closed while applications are in Offer.", offers
        )
    applications = list(applications_rejected_by_close(job))
    for application in applications:
        record_move(user, application, Stage.REJECTED, StageChange.Reason.JOB_CLOSED)
    job.status = JobOpening.Status.CLOSED
    job.closed_at = timezone.now()
    job.save(update_fields=["status", "closed_at", "updated_at"])
    return len(applications)


@transaction.atomic
def reopen_job(user, job, restore=False):
    if not job.is_closed:
        raise JobReopenRefused("This job is already open.")
    job.status = JobOpening.Status.OPEN
    job.closed_at = None
    job.save(update_fields=["status", "closed_at", "updated_at"])
    restored = skipped = 0
    if not restore:
        return restored, skipped
    for application, change in applications_closed_out(job):
        if in_progress_refusal_reason(application):
            skipped += 1
            continue
        record_move(
            user, application, change.from_stage, StageChange.Reason.JOB_REOPENED
        )
        restored += 1
    return restored, skipped


def offers_blocking_archive(candidate):
    return candidate.applications.filter(stage=Stage.OFFER).select_related("job")


def applications_withdrawn_by_archive(candidate):
    return candidate.applications.filter(stage__in=ACTIVE_STAGES)


def applications_archived_out(candidate):
    return latest_changes_with_reason(
        candidate.applications.filter(stage=Stage.WITHDRAWN).select_related("job"),
        StageChange.Reason.CANDIDATE_ARCHIVED,
    )


@transaction.atomic
def archive_candidate(user, candidate):
    if candidate.is_archived:
        raise CandidateArchiveRefused("This candidate is already archived.")
    if offers_blocking_archive(candidate):
        raise CandidateArchiveRefused(
            "This candidate cannot be archived while an application is in Offer."
        )
    applications = list(applications_withdrawn_by_archive(candidate))
    for application in applications:
        record_move(
            user, application, Stage.WITHDRAWN, StageChange.Reason.CANDIDATE_ARCHIVED
        )
    candidate.is_archived = True
    candidate.save(update_fields=["is_archived", "updated_at"])
    return len(applications)


@transaction.atomic
def unarchive_candidate(user, candidate, restore=False):
    if not candidate.is_archived:
        raise CandidateUnarchiveRefused("This candidate is not archived.")
    candidate.is_archived = False
    candidate.save(update_fields=["is_archived", "updated_at"])
    restored = skipped = 0
    if not restore:
        return restored, skipped
    for application, change in applications_archived_out(candidate):
        if in_progress_refusal_reason(application):
            skipped += 1
            continue
        record_move(
            user,
            application,
            change.from_stage,
            StageChange.Reason.CANDIDATE_UNARCHIVED,
        )
        restored += 1
    return restored, skipped


@transaction.atomic
def move_application(user, application, target):
    reason = refusal_reason(user, application, target)
    if reason:
        raise MoveRefused(reason)
    record_move(
        user,
        application,
        target,
        (
            StageChange.Reason.APPLICATION_REOPENED
            if application.stage in EXIT_STAGES
            else StageChange.Reason.NORMAL_MOVE
        ),
    )
