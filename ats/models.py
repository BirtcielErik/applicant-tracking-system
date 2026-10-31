from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .pipeline import Stage


class User(AbstractUser):
    class Meta(AbstractUser.Meta):
        permissions = [
            ("make_offer", "Can make an offer"),
            ("confirm_hire", "Can confirm a hire"),
            ("change_offer_or_hire", "Can change an offer or hire"),
            ("reopen_application", "Can reopen an application"),
            ("close_reopen_job", "Can close and reopen a job"),
            ("archive_candidate", "Can archive and unarchive a candidate"),
            ("rename_delete_skill", "Can rename and delete a skill"),
        ]


class Candidate(models.Model):
    class LeadSource(models.TextChoices):
        COMPANY_WEBSITE = "company_website", "Company Website"
        JOB_BOARD = "job_board", "Job Board"
        REFERRAL = "referral", "Referral"
        OTHER = "other", "Other"

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    lead_source = models.CharField(max_length=20, choices=LeadSource)
    lead_source_detail = models.CharField(max_length=255, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class JobOpening(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    title = models.CharField(max_length=200)
    department = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status, default=Status.OPEN)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Application(models.Model):
    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="applications"
    )
    job = models.ForeignKey(
        JobOpening, on_delete=models.PROTECT, related_name="applications"
    )
    stage = models.CharField(max_length=20, choices=Stage, default=Stage.APPLIED)
    application_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["application_date", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job"], name="unique_candidate_job_application"
            ),
        ]

    def __str__(self):
        return f"{self.candidate} for {self.job}"


class StageChange(models.Model):
    class Reason(models.TextChoices):
        NORMAL_MOVE = "normal_move", "Normal move"
        JOB_CLOSED = "job_closed", "Job closed"
        CANDIDATE_ARCHIVED = "candidate_archived", "Candidate archived"
        JOB_REOPENED = "job_reopened", "Job reopened"
        CANDIDATE_UNARCHIVED = "candidate_unarchived", "Candidate unarchived"
        APPLICATION_REOPENED = "application_reopened", "Application reopened"
        APPLICATION_CREATED = "application_created", "Application created"

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="stage_changes"
    )
    from_stage = models.CharField(max_length=20, choices=Stage, blank=True)
    to_stage = models.CharField(max_length=20, choices=Stage)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stage_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=30, choices=Reason)

    class Meta:
        ordering = ["-changed_at", "-pk"]

    def __str__(self):
        return f"{self.application}: {self.from_stage} to {self.to_stage}"
