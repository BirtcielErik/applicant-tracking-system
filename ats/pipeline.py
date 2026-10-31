from django.db import models


class Stage(models.TextChoices):
    APPLIED = "applied", "Applied"
    SCREENING = "screening", "Screening"
    INTERVIEW = "interview", "Interview"
    FINAL_REVIEW = "final_review", "Final Review"
    OFFER = "offer", "Offer"
    HIRED = "hired", "Hired"
    REJECTED = "rejected", "Rejected"
    WITHDRAWN = "withdrawn", "Withdrawn"


ACTIVE_STAGES = (Stage.APPLIED, Stage.SCREENING, Stage.INTERVIEW, Stage.FINAL_REVIEW)
EXIT_STAGES = (Stage.REJECTED, Stage.WITHDRAWN)
IN_PROGRESS_STAGES = (*ACTIVE_STAGES, Stage.OFFER, Stage.HIRED)


def stage_before_exit(application):
    change = application.stage_changes.filter(to_stage__in=EXIT_STAGES).first()
    return change.from_stage if change else None


def refusal_reason(user, application, target):
    """Return why this move is not allowed, or None if it is."""
    source = application.stage
    if target not in Stage.values:
        return "That is not a stage."
    if target == source:
        return f"This application is already in {Stage(source).label}."
    if target in IN_PROGRESS_STAGES:
        if application.job.is_closed:
            return "This job is closed, so the application can only exit."
        if application.candidate.is_archived:
            return "This candidate is archived, so the application can only exit."
    if source in ACTIVE_STAGES:
        return active_refusal_reason(user, source, target)
    if source == Stage.OFFER:
        return offer_refusal_reason(user, target)
    if source == Stage.HIRED:
        if not user.has_perm("ats.change_offer_or_hire"):
            return "Only a hiring manager can move an application out of Hired."
        return None
    return reopen_refusal_reason(user, application, target)


def active_refusal_reason(user, source, target):
    if target == Stage.HIRED:
        return "Only an application in Offer can be hired."
    if target == Stage.OFFER:
        if source != Stage.FINAL_REVIEW:
            return "Only an application in Final Review can receive an offer."
        if not user.has_perm("ats.make_offer"):
            return "Only a hiring manager can make an offer."
    return None


def offer_refusal_reason(user, target):
    if target == Stage.HIRED:
        if not user.has_perm("ats.confirm_hire"):
            return "Only a hiring manager can confirm a hire."
    elif target in ACTIVE_STAGES:
        if not user.has_perm("ats.change_offer_or_hire"):
            return "Only a hiring manager can move an application out of Offer."
    return None


def reopen_refusal_reason(user, application, target):
    if not user.has_perm("ats.reopen_application"):
        return "Only a hiring manager can reopen an application."
    previous = stage_before_exit(application)
    if previous is None:
        return "This application has no previous stage to reopen to."
    if target != previous:
        return f"This application can only reopen to {Stage(previous).label}."
    return None


def can_transition(user, application, target):
    return refusal_reason(user, application, target) is None


def allowed_targets(user, application):
    return [
        target for target in Stage.values if can_transition(user, application, target)
    ]
