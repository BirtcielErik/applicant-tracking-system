from datetime import timedelta
from itertools import pairwise

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from ats.models import Application, Candidate, JobOpening, StageChange
from ats.pipeline import Stage

DEMO_PASSWORD = "demo-password"

USERS = [
    ("recruiter", ["Recruiter"]),
    ("manager", ["Hiring Manager"]),
    ("dual", ["Recruiter", "Hiring Manager"]),
]

JOBS = [
    ("Backend Engineer", "Engineering", "Remote"),
    ("Product Designer", "Design", "Amarillo, TX"),
    ("Account Executive", "Sales", "Dallas, TX"),
    ("Data Analyst", "Operations", "Remote"),
]
CLOSED_JOB = "Data Analyst"

LeadSource = Candidate.LeadSource
CANDIDATES = [
    ("Ava", "Nguyen", LeadSource.COMPANY_WEBSITE, ""),
    ("Ben", "Carter", LeadSource.JOB_BOARD, "Indeed"),
    ("Chloe", "Ramirez", LeadSource.REFERRAL, "Referred by Maria Lopez"),
    ("Dev", "Patel", LeadSource.JOB_BOARD, "LinkedIn"),
    ("Elena", "Rossi", LeadSource.OTHER, "Career fair"),
    ("Farid", "Haddad", LeadSource.COMPANY_WEBSITE, ""),
    ("Grace", "Kim", LeadSource.REFERRAL, "Referred by Tom Reed"),
    ("Hugo", "Martin", LeadSource.JOB_BOARD, "Indeed"),
    ("Iris", "Olsen", LeadSource.COMPANY_WEBSITE, ""),
    ("Jamal", "Wright", LeadSource.OTHER, "Conference"),
    ("Kira", "Novak", LeadSource.JOB_BOARD, "LinkedIn"),
]
ARCHIVED_CANDIDATE = "Kira"

TO_FINAL_REVIEW = [
    Stage.APPLIED,
    Stage.SCREENING,
    Stage.INTERVIEW,
    Stage.FINAL_REVIEW,
]
TO_OFFER = [*TO_FINAL_REVIEW, Stage.OFFER]

# (candidate first name, job title, days ago, stages in the order they were held)
APPLICATIONS = [
    ("Ava", "Backend Engineer", 2, [Stage.APPLIED]),
    ("Ben", "Backend Engineer", 5, [Stage.APPLIED, Stage.SCREENING]),
    ("Chloe", "Backend Engineer", 9, TO_FINAL_REVIEW[:3]),
    ("Dev", "Backend Engineer", 14, TO_FINAL_REVIEW),
    ("Elena", "Backend Engineer", 20, TO_OFFER),
    ("Farid", "Backend Engineer", 30, [*TO_OFFER, Stage.HIRED]),
    ("Grace", "Backend Engineer", 12, [Stage.APPLIED, Stage.REJECTED]),
    ("Hugo", "Backend Engineer", 11, [Stage.APPLIED, Stage.WITHDRAWN]),
    ("Iris", "Backend Engineer", 1, [Stage.APPLIED]),
    ("Jamal", "Backend Engineer", 25, [*TO_OFFER, Stage.REJECTED]),
    ("Kira", "Backend Engineer", 10, [*TO_FINAL_REVIEW[:2], Stage.WITHDRAWN]),
    ("Ava", "Product Designer", 6, [Stage.APPLIED, Stage.SCREENING]),
    ("Jamal", "Product Designer", 3, [Stage.APPLIED]),
    ("Ben", "Account Executive", 4, [Stage.APPLIED]),
    ("Iris", "Account Executive", 8, TO_FINAL_REVIEW[:3]),
    ("Grace", "Data Analyst", 40, [*TO_OFFER, Stage.HIRED]),
    ("Hugo", "Data Analyst", 35, [*TO_FINAL_REVIEW[:3], Stage.REJECTED]),
]


class Command(BaseCommand):
    help = "Reset the application to the demo data. Only superusers are kept."

    @transaction.atomic
    def handle(self, *args, **options):
        self.reset()
        users = {name: self.seed_user(name, roles) for name, roles in USERS}
        manager = users["manager"]
        jobs = {
            title: JobOpening.objects.create(
                title=title,
                department=department,
                location=location,
                created_by=manager,
            )
            for title, department, location in JOBS
        }
        candidates = {row[0]: self.seed_candidate(*row) for row in CANDIDATES}
        for first_name, title, days_ago, stages in APPLICATIONS:
            self.seed_application(
                candidates[first_name], jobs[title], days_ago, stages, manager
            )
        JobOpening.objects.filter(title=CLOSED_JOB).update(
            status=JobOpening.Status.CLOSED, closed_at=timezone.now()
        )
        Candidate.objects.filter(first_name=ARCHIVED_CANDIDATE).update(is_archived=True)

        names = ", ".join(name for name, _ in USERS)
        self.stdout.write(f"Demo users: {names} (password: {DEMO_PASSWORD})")
        for job in jobs.values():
            url = reverse("ats:job_detail", args=[job.pk])
            self.stdout.write(f"{job.title}: {url}")

    def reset(self):
        # Children go first because their foreign keys protect the parent rows.
        StageChange.objects.all().delete()
        Application.objects.all().delete()
        Candidate.objects.all().delete()
        JobOpening.objects.all().delete()
        get_user_model().objects.filter(is_superuser=False).delete()

    def seed_user(self, username, roles):
        user = get_user_model().objects.create_user(username, password=DEMO_PASSWORD)
        user.groups.set(Group.objects.filter(name__in=roles))
        return user

    def seed_candidate(self, first_name, last_name, lead_source, detail):
        return Candidate.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=f"{first_name}.{last_name}@example.com".lower(),
            lead_source=lead_source,
            lead_source_detail=detail,
        )

    def seed_application(self, candidate, job, days_ago, stages, user):
        application = Application.objects.create(
            candidate=candidate,
            job=job,
            stage=stages[-1],
            application_date=timezone.localdate() - timedelta(days=days_ago),
        )
        self.seed_stage_change(
            application,
            "",
            stages[0],
            user,
            StageChange.Reason.APPLICATION_CREATED,
            timedelta(days=days_ago),
        )
        # Moves are spread evenly between the application date and today.
        step = timedelta(days=days_ago) / len(stages)
        for index, (from_stage, to_stage) in enumerate(pairwise(stages), start=1):
            self.seed_stage_change(
                application,
                from_stage,
                to_stage,
                user,
                StageChange.Reason.NORMAL_MOVE,
                step * (len(stages) - index),
            )

    def seed_stage_change(self, application, from_stage, to_stage, user, reason, age):
        change = StageChange.objects.create(
            application=application,
            from_stage=from_stage,
            to_stage=to_stage,
            changed_by=user,
            reason=reason,
        )
        # changed_at is set automatically, so backdating needs a separate update.
        StageChange.objects.filter(pk=change.pk).update(changed_at=timezone.now() - age)
