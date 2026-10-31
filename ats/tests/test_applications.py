from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from ats.models import Application, JobOpening, StageChange
from ats.pipeline import Stage
from ats.services import ApplicationRefused, create_application
from ats.tests.conftest import make_application, make_candidate, make_user


def close_job(job, candidate):
    job.status = JobOpening.Status.CLOSED
    job.save()


def archive_candidate(job, candidate):
    candidate.is_archived = True
    candidate.save()


def apply_already(job, candidate):
    make_application(job, candidate=candidate)


def no_setup(job, candidate):
    pass


def test_new_application_starts_in_applied_with_an_initial_stage_change(job, recruiter):
    candidate = make_candidate()
    applied_on = timezone.localdate() - timedelta(days=3)

    application = create_application(recruiter, candidate, job, applied_on)

    application.refresh_from_db()
    assert application.candidate == candidate
    assert application.job == job
    assert application.stage == Stage.APPLIED
    assert application.application_date == applied_on
    assert list(
        application.stage_changes.values_list(
            "from_stage", "to_stage", "changed_by", "reason"
        )
    ) == [("", Stage.APPLIED, recruiter.pk, StageChange.Reason.APPLICATION_CREATED)]


@pytest.mark.parametrize(
    ("arrange", "days_ahead", "message"),
    [
        (close_job, 0, "This job is closed"),
        (archive_candidate, 0, "This candidate is archived"),
        (apply_already, 0, "already applied"),
        (no_setup, 1, "cannot be in the future"),
    ],
)
def test_invalid_application_is_refused_and_saves_nothing(
    job, recruiter, arrange, days_ahead, message
):
    candidate = make_candidate()
    arrange(job, candidate)
    applications_before = Application.objects.count()
    applied_on = timezone.localdate() + timedelta(days=days_ahead)

    with pytest.raises(ApplicationRefused, match=message):
        create_application(recruiter, candidate, job, applied_on)

    assert Application.objects.count() == applications_before
    assert not StageChange.objects.exists()


@pytest.mark.parametrize(
    ("stage", "mentions_reopen"),
    [
        (Stage.REJECTED, True),
        (Stage.WITHDRAWN, True),
        (Stage.APPLIED, False),
        (Stage.OFFER, False),
        (Stage.HIRED, False),
    ],
)
def test_duplicate_refusal_mentions_reopening_only_for_an_exited_application(
    job, recruiter, stage, mentions_reopen
):
    existing = make_application(job, stage)

    with pytest.raises(ApplicationRefused) as refusal:
        create_application(recruiter, existing.candidate, job, timezone.localdate())

    assert ("a hiring manager can reopen" in str(refusal.value)) is mentions_reopen


def test_created_timestamp_is_recorded_separately_from_application_date(job, recruiter):
    applied_on = timezone.localdate() - timedelta(days=30)

    application = create_application(recruiter, make_candidate(), job, applied_on)

    assert application.application_date == applied_on
    assert timezone.localdate(application.created_at) == timezone.localdate()


def add_applicant_url(job):
    return reverse("ats:job_application_create", args=[job.pk])


def apply_to_job_url(candidate):
    return reverse("ats:candidate_application_create", args=[candidate.pk])


def today():
    return timezone.localdate().isoformat()


def test_application_pages_require_login(client, job):
    urls = [add_applicant_url(job), apply_to_job_url(make_candidate())]

    for url in urls:
        response = client.get(url)

        assert response.status_code == 302
        assert response.url.startswith(reverse("ats:login"))


def test_account_with_no_role_cannot_create_applications(client, job):
    candidate = make_candidate()
    client.force_login(make_user("nobody"))

    board_response = client.post(
        add_applicant_url(job),
        {"candidate": candidate.pk, "application_date": today()},
    )
    candidate_response = client.post(
        apply_to_job_url(candidate),
        {"job": job.pk, "application_date": today()},
    )

    assert board_response.status_code == 403
    assert candidate_response.status_code == 403
    assert not Application.objects.exists()


def test_candidate_picker_lists_only_valid_candidates(client, recruiter, job):
    make_candidate("Valid", "Person")
    archived = make_candidate("Archived", "Person")
    archived.is_archived = True
    archived.save()
    make_application(job, candidate=make_candidate("Applied", "Person"))
    make_application(
        job, Stage.REJECTED, candidate=make_candidate("Rejected", "Person")
    )
    client.force_login(recruiter)

    content = client.get(add_applicant_url(job)).content.decode()

    assert "Valid Person (valid.person@example.com)" in content
    assert "Archived Person" not in content
    assert "Applied Person" not in content
    assert "Rejected Person" not in content


def test_candidate_picker_is_empty_for_a_closed_job(client, recruiter, job):
    make_candidate("Valid", "Person")
    close_job(job, None)
    client.force_login(recruiter)

    content = client.get(add_applicant_url(job)).content.decode()

    assert "Valid Person" not in content


@pytest.mark.parametrize("query", ["valid", "VALID.PERSON@"])
def test_candidate_picker_searches_by_name_or_email(client, recruiter, job, query):
    make_candidate("Valid", "Person")
    make_candidate("Other", "Human")
    client.force_login(recruiter)

    content = client.get(add_applicant_url(job), {"q": query}).content.decode()

    assert "Valid Person" in content
    assert "Other Human" not in content


def test_job_picker_lists_only_open_jobs_not_already_applied_to(
    client, recruiter, manager, job
):
    candidate = make_candidate()
    JobOpening.objects.create(title="Open Role", created_by=manager)
    JobOpening.objects.create(
        title="Closed Role", status=JobOpening.Status.CLOSED, created_by=manager
    )
    make_application(job, candidate=candidate)
    client.force_login(recruiter)

    content = client.get(apply_to_job_url(candidate)).content.decode()

    assert "Open Role" in content
    assert "Closed Role" not in content
    assert job.title not in content


def test_job_picker_is_empty_for_an_archived_candidate(client, recruiter, job):
    candidate = make_candidate()
    archive_candidate(job, candidate)
    client.force_login(recruiter)

    content = client.get(apply_to_job_url(candidate)).content.decode()

    assert job.title not in content


def test_application_date_defaults_to_today(client, recruiter, job):
    client.force_login(recruiter)

    content = client.get(add_applicant_url(job)).content.decode()

    assert f'value="{today()}"' in content


def test_adding_from_the_board_shows_the_new_card_in_applied(client, recruiter, job):
    candidate = make_candidate()
    client.force_login(recruiter)

    response = client.post(
        add_applicant_url(job),
        {"candidate": candidate.pk, "application_date": today()},
        follow=True,
    )

    application = Application.objects.get()
    assert application.candidate == candidate
    assert application.stage == Stage.APPLIED
    assert response.redirect_chain[-1][0] == reverse("ats:job_detail", args=[job.pk])
    columns = {
        column["stage"]: column["applications"]
        for column in response.context["columns"]
    }
    assert [card.pk for card in columns[Stage.APPLIED]] == [application.pk]
    assert candidate.email in response.content.decode()


def test_applying_from_the_candidate_page_confirms_on_that_page(client, recruiter, job):
    candidate = make_candidate()
    client.force_login(recruiter)

    response = client.post(
        apply_to_job_url(candidate),
        {"job": job.pk, "application_date": today()},
        follow=True,
    )

    application = Application.objects.get()
    assert application.job == job
    assert application.stage == Stage.APPLIED
    assert f"Applied {candidate} to {job}." in response.content.decode()


def test_past_application_date_is_accepted_from_the_form(client, recruiter, job):
    applied_on = timezone.localdate() - timedelta(days=10)
    client.force_login(recruiter)

    client.post(
        add_applicant_url(job),
        {"candidate": make_candidate().pk, "application_date": applied_on.isoformat()},
    )

    assert Application.objects.get().application_date == applied_on


def test_future_application_date_error_renders(client, recruiter, job):
    tomorrow = timezone.localdate() + timedelta(days=1)
    client.force_login(recruiter)

    response = client.post(
        add_applicant_url(job),
        {"candidate": make_candidate().pk, "application_date": tomorrow.isoformat()},
    )

    assert response.status_code == 200
    assert "cannot be in the future" in response.content.decode()
    assert not Application.objects.exists()


def test_candidate_choice_is_kept_when_the_form_has_an_error(client, recruiter, job):
    candidate = make_candidate("Valid", "Person")
    client.force_login(recruiter)

    content = client.post(
        add_applicant_url(job),
        {"candidate": candidate.pk, "application_date": ""},
    ).content.decode()

    assert f'name="candidate" value="{candidate.pk}"' in content
    assert 'value="Valid Person (valid.person@example.com)"' in content


def test_stale_post_for_an_exited_application_explains_the_reopen(
    client, recruiter, job
):
    existing = make_application(job, Stage.WITHDRAWN)
    client.force_login(recruiter)

    response = client.post(
        add_applicant_url(job),
        {"candidate": existing.candidate.pk, "application_date": today()},
    )

    assert response.status_code == 200
    assert "a hiring manager can reopen it" in response.content.decode()
    assert Application.objects.count() == 1


def test_hand_crafted_post_for_a_closed_job_is_refused(client, recruiter, job):
    candidate = make_candidate()
    close_job(job, candidate)
    client.force_login(recruiter)

    response = client.post(
        apply_to_job_url(candidate),
        {"job": job.pk, "application_date": today()},
    )

    assert response.status_code == 200
    assert "This job is closed" in response.content.decode()
    assert not Application.objects.exists()


def test_hand_crafted_post_for_an_archived_candidate_is_refused(client, recruiter, job):
    candidate = make_candidate()
    archive_candidate(job, candidate)
    client.force_login(recruiter)

    response = client.post(
        add_applicant_url(job),
        {"candidate": candidate.pk, "application_date": today()},
    )

    assert response.status_code == 200
    assert "This candidate is archived" in response.content.decode()
    assert not Application.objects.exists()


def test_entry_point_buttons_are_shown_only_when_usable(client, recruiter, job):
    candidate = make_candidate()
    client.force_login(recruiter)
    job_url = reverse("ats:job_detail", args=[job.pk])
    candidate_url = reverse("ats:candidate_detail", args=[candidate.pk])

    assert add_applicant_url(job) in client.get(job_url).content.decode()
    assert apply_to_job_url(candidate) in client.get(candidate_url).content.decode()

    close_job(job, candidate)
    archive_candidate(job, candidate)

    assert add_applicant_url(job) not in client.get(job_url).content.decode()
    assert apply_to_job_url(candidate) not in client.get(candidate_url).content.decode()


def test_entry_point_buttons_are_hidden_without_permission(client, job):
    candidate = make_candidate()
    client.force_login(make_user("nobody"))

    job_content = client.get(reverse("ats:job_detail", args=[job.pk])).content.decode()
    candidate_content = client.get(
        reverse("ats:candidate_detail", args=[candidate.pk])
    ).content.decode()

    assert add_applicant_url(job) not in job_content
    assert apply_to_job_url(candidate) not in candidate_content
