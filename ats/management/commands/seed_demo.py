from datetime import timedelta
from itertools import pairwise

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from ats import services
from ats.models import (
    Application,
    Candidate,
    CandidateNote,
    JobOpening,
    Skill,
    StageChange,
)
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

JOB_SKILLS = {
    "Backend Engineer": ["Python", "Django", "SQL"],
    "Product Designer": ["Figma", "User Research"],
    "Account Executive": ["Negotiation", "Salesforce"],
    "Data Analyst": ["Python", "SQL", "Tableau"],
}

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
    # Still active here, so closing the job rejects them. Kira is archived after
    # the close, so restoring on reopen skips her application.
    ("Chloe", "Data Analyst", 15, TO_FINAL_REVIEW[:2]),
    ("Dev", "Data Analyst", 18, TO_FINAL_REVIEW[:3]),
    ("Kira", "Data Analyst", 16, TO_FINAL_REVIEW[:2]),
    # Still active here, so archiving Kira withdraws it and unarchiving restores it.
    ("Kira", "Product Designer", 7, TO_FINAL_REVIEW[:2]),
]
CLOSED_JOB_AGE = timedelta(days=2)
ARCHIVE_AGE = timedelta(days=1)

# (candidate first name, author, job title or None, days ago, body)
NOTES = [
    ("Ava", "recruiter", None, 2, "Prefers remote work."),
    ("Ben", "recruiter", "Backend Engineer", 3, "Phone screen went well."),
    ("Ben", "recruiter", None, 4, "Available to start in two weeks."),
    ("Dev", "manager", "Backend Engineer", 1, "Strong final review panel."),
    ("Elena", "manager", "Backend Engineer", 1, "Verbal offer made."),
    ("Jamal", "manager", "Backend Engineer", 5, "Declined the offer."),
    ("Jamal", "recruiter", "Product Designer", 2, "Portfolio requested."),
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
        for title, names in JOB_SKILLS.items():
            jobs[title].skills.set(services.get_or_create_skill(n) for n in names)
        candidates = {row[0]: self.seed_candidate(*row) for row in CANDIDATES}
        for first_name, title, days_ago, stages in APPLICATIONS:
            self.seed_application(
                candidates[first_name], jobs[title], days_ago, stages, manager
            )
        for first_name, author, title, days_ago, body in NOTES:
            self.seed_note(
                candidates[first_name],
                users[author],
                jobs.get(title),
                days_ago,
                body,
            )
        self.seed_closed_job(jobs[CLOSED_JOB], manager)
        self.seed_archived_candidate(candidates[ARCHIVED_CANDIDATE], manager)

        names = ", ".join(name for name, _ in USERS)
        self.stdout.write(f"Demo users: {names} (password: {DEMO_PASSWORD})")
        for job in jobs.values():
            url = reverse("ats:job_detail", args=[job.pk])
            self.stdout.write(f"{job.title}: {url}")

    def reset(self):
        # Children go first because their foreign keys protect the parent rows.
        CandidateNote.objects.all().delete()
        StageChange.objects.all().delete()
        Application.objects.all().delete()
        Candidate.objects.all().delete()
        JobOpening.objects.all().delete()
        Skill.objects.all().delete()
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

    def seed_closed_job(self, job, user):
        services.close_job(user, job)
        # Both timestamps are set automatically, so backdating needs an update.
        closed_at = timezone.now() - CLOSED_JOB_AGE
        JobOpening.objects.filter(pk=job.pk).update(closed_at=closed_at)
        StageChange.objects.filter(
            application__job=job, reason=StageChange.Reason.JOB_CLOSED
        ).update(changed_at=closed_at)

    def seed_archived_candidate(self, candidate, user):
        services.archive_candidate(user, candidate)
        # changed_at is set automatically, so backdating needs a separate update.
        StageChange.objects.filter(
            application__candidate=candidate,
            reason=StageChange.Reason.CANDIDATE_ARCHIVED,
        ).update(changed_at=timezone.now() - ARCHIVE_AGE)

    def seed_note(self, candidate, author, job, days_ago, body):
        application = candidate.applications.get(job=job) if job else None
        note = services.add_note(author, candidate, body, application)
        # created_at is set automatically, so backdating needs a separate update.
        CandidateNote.objects.filter(pk=note.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
