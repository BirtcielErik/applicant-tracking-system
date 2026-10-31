from datetime import date

import pytest
from django.urls import reverse

from ats import services
from ats.admin import JobOpeningAdmin
from ats.models import Application, Candidate, JobOpening, StageChange
from ats.pipeline import ACTIVE_STAGES, Stage
from ats.tests.conftest import (
    fail_on_second_move,
    make_application,
    make_candidate,
    make_user,
)


def make_applications(job, stages, prefix="Applicant"):
    return [
        make_application(job, stage, make_candidate(prefix, str(index)))
        for index, stage in enumerate(stages)
    ]


def test_close_rejects_active_applications_and_leaves_outcomes_alone(job, manager):
    active = make_applications(job, ACTIVE_STAGES, "Active")
    outcomes = make_applications(
        job, [Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN], "Outcome"
    )

    services.close_job(manager, job)

    job.refresh_from_db()
    assert job.status == JobOpening.Status.CLOSED
    assert job.closed_at is not None
    for application, previous in zip(active, ACTIVE_STAGES, strict=True):
        application.refresh_from_db()
        assert application.stage == Stage.REJECTED
        change = application.stage_changes.get()
        assert change.from_stage == previous
        assert change.to_stage == Stage.REJECTED
        assert change.changed_by == manager
        assert change.reason == StageChange.Reason.JOB_CLOSED
    for application, stage in zip(
        outcomes, [Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN], strict=True
    ):
        application.refresh_from_db()
        assert application.stage == stage
        assert not application.stage_changes.exists()


def test_close_is_refused_while_an_application_is_in_offer(job, manager):
    offer = make_application(job, Stage.OFFER, make_candidate("Olivia", "Offer"))
    active = make_application(job, Stage.INTERVIEW, make_candidate("Ian", "Active"))

    with pytest.raises(services.JobCloseRefused) as refusal:
        services.close_job(manager, job)

    assert list(refusal.value.applications) == [offer]
    job.refresh_from_db()
    assert job.status == JobOpening.Status.OPEN
    assert job.closed_at is None
    active.refresh_from_db()
    assert active.stage == Stage.INTERVIEW
    assert not StageChange.objects.exists()


def test_reopen_with_restore_returns_only_applications_rejected_by_the_close(
    job, manager
):
    closed_out = make_application(
        job, Stage.INTERVIEW, make_candidate("Rita", "Restored")
    )
    turned_down = make_application(
        job, Stage.SCREENING, make_candidate("Nora", "Normal")
    )
    services.move_application(manager, turned_down, Stage.REJECTED)
    archived = make_application(
        job, Stage.FINAL_REVIEW, make_candidate("Arlo", "Archived")
    )
    services.close_job(manager, job)
    Candidate.objects.filter(pk=archived.candidate_id).update(is_archived=True)

    restored, skipped = services.reopen_job(manager, job, restore=True)

    assert (restored, skipped) == (1, 1)
    job.refresh_from_db()
    assert job.status == JobOpening.Status.OPEN
    assert job.closed_at is None
    closed_out.refresh_from_db()
    assert closed_out.stage == Stage.INTERVIEW
    change = closed_out.stage_changes.first()
    assert change.from_stage == Stage.REJECTED
    assert change.to_stage == Stage.INTERVIEW
    assert change.changed_by == manager
    assert change.reason == StageChange.Reason.JOB_REOPENED
    for application in [turned_down, archived]:
        application.refresh_from_db()
        assert application.stage == Stage.REJECTED
        reasons = application.stage_changes.values_list("reason", flat=True)
        assert StageChange.Reason.JOB_REOPENED not in reasons


def test_close_returns_the_number_rejected(job, manager):
    make_applications(job, ACTIVE_STAGES)

    assert services.close_job(manager, job) == len(ACTIVE_STAGES)


def test_close_applies_nothing_when_a_move_fails(job, manager, monkeypatch):
    applications = make_applications(job, [Stage.APPLIED, Stage.SCREENING])
    fail_on_second_move(monkeypatch)

    with pytest.raises(RuntimeError):
        services.close_job(manager, job)

    job = JobOpening.objects.get(pk=job.pk)
    assert job.status == JobOpening.Status.OPEN
    assert job.closed_at is None
    assert not StageChange.objects.exists()
    applications[0].refresh_from_db()
    assert applications[0].stage == Stage.APPLIED


def test_reopen_applies_nothing_when_a_restore_fails(job, manager, monkeypatch):
    applications = make_applications(job, [Stage.APPLIED, Stage.SCREENING])
    services.close_job(manager, job)
    changes = StageChange.objects.count()
    fail_on_second_move(monkeypatch)

    with pytest.raises(RuntimeError):
        services.reopen_job(manager, job, restore=True)

    job = JobOpening.objects.get(pk=job.pk)
    assert job.status == JobOpening.Status.CLOSED
    assert job.closed_at is not None
    assert StageChange.objects.count() == changes
    applications[0].refresh_from_db()
    assert applications[0].stage == Stage.REJECTED


def test_closing_a_closed_job_is_refused_and_keeps_the_closed_at_time(job, manager):
    services.close_job(manager, job)
    closed_at = job.closed_at

    with pytest.raises(services.JobCloseRefused, match="already closed"):
        services.close_job(manager, job)

    job.refresh_from_db()
    assert job.closed_at == closed_at


def test_reopening_an_open_job_is_refused_and_restores_nothing(job, manager):
    application = make_application(job, Stage.INTERVIEW)
    services.close_job(manager, job)
    services.reopen_job(manager, job)

    with pytest.raises(services.JobReopenRefused, match="already open"):
        services.reopen_job(manager, job, restore=True)

    application.refresh_from_db()
    assert application.stage == Stage.REJECTED


def test_reopen_without_restore_marks_open_and_changes_no_applications(job, manager):
    application = make_application(job, Stage.INTERVIEW)
    services.close_job(manager, job)
    changes = StageChange.objects.count()

    result = services.reopen_job(manager, job)

    assert result == (0, 0)
    job.refresh_from_db()
    assert job.status == JobOpening.Status.OPEN
    assert job.closed_at is None
    application.refresh_from_db()
    assert application.stage == Stage.REJECTED
    assert StageChange.objects.count() == changes


def test_restore_ignores_an_application_with_no_stage_history(job, manager):
    make_application(job, Stage.REJECTED)
    services.close_job(manager, job)

    assert services.reopen_job(manager, job, restore=True) == (0, 0)


def test_restore_leaves_an_application_rejected_again_after_a_manual_reopen(
    job, manager
):
    application = make_application(job, Stage.INTERVIEW)
    services.close_job(manager, job)
    services.reopen_job(manager, job)
    application.refresh_from_db()
    services.move_application(manager, application, Stage.INTERVIEW)
    services.move_application(manager, application, Stage.REJECTED)
    services.close_job(manager, job)

    assert services.reopen_job(manager, job, restore=True) == (0, 0)

    application.refresh_from_db()
    assert application.stage == Stage.REJECTED


def test_closed_job_refuses_new_applications_and_leaves_the_pickers(
    client, job, manager, recruiter
):
    candidate = make_candidate()
    assert JobOpening.objects.available_for(candidate).exists()
    services.close_job(manager, job)
    client.force_login(recruiter)

    with pytest.raises(services.ApplicationRefused, match="closed"):
        services.create_application(recruiter, candidate, job, date(2026, 1, 1))

    picker = client.get(
        reverse("ats:candidate_application_create", args=[candidate.pk])
    )
    assert job.title not in picker.content.decode()
    assert not Application.objects.exists()


def test_close_page_shows_the_number_that_will_be_rejected(client, manager, job):
    make_applications(job, [*ACTIVE_STAGES, Stage.HIRED, Stage.WITHDRAWN])
    client.force_login(manager)

    content = client.get(reverse("ats:job_close", args=[job.pk])).content.decode()

    assert "<strong>4</strong> active applications" in content
    assert "Close job</button>" in content
    assert JobOpening.objects.get(pk=job.pk).status == JobOpening.Status.OPEN


def test_close_page_lists_offers_and_offers_no_confirmation(client, manager, job):
    make_application(job, Stage.OFFER, make_candidate("Olivia", "Offer"))
    make_application(job, Stage.INTERVIEW, make_candidate("Ian", "Active"))
    client.force_login(manager)

    content = client.get(reverse("ats:job_close", args=[job.pk])).content.decode()

    assert "Olivia Offer" in content
    assert "Ian Active" not in content
    assert "Close job</button>" not in content


def test_post_close_rejects_and_redirects_to_the_job_with_a_message(
    client, manager, job
):
    application = make_application(job, Stage.INTERVIEW)
    client.force_login(manager)

    response = client.post(reverse("ats:job_close", args=[job.pk]), follow=True)

    assert response.redirect_chain == [(reverse("ats:job_detail", args=[job.pk]), 302)]
    assert "Rejected 1 application." in response.content.decode()
    job.refresh_from_db()
    assert job.status == JobOpening.Status.CLOSED
    application.refresh_from_db()
    assert application.stage == Stage.REJECTED


def test_post_close_with_an_offer_lists_it_and_changes_nothing(client, manager, job):
    make_application(job, Stage.OFFER, make_candidate("Olivia", "Offer"))
    client.force_login(manager)

    response = client.post(reverse("ats:job_close", args=[job.pk]))

    assert response.status_code == 200
    assert "Olivia Offer" in response.content.decode()
    job.refresh_from_db()
    assert job.status == JobOpening.Status.OPEN


def test_close_page_for_a_closed_job_says_so(client, manager, job):
    services.close_job(manager, job)
    client.force_login(manager)

    response = client.post(reverse("ats:job_close", args=[job.pk]))

    assert response.status_code == 200
    assert "already closed" in response.content.decode()


def test_reopen_page_offers_restore_only_when_something_can_be_restored(
    client, manager, job
):
    url = reverse("ats:job_reopen", args=[job.pk])
    services.close_job(manager, job)
    client.force_login(manager)
    assert 'name="restore"' not in client.get(url).content.decode()

    client.post(url)
    job.refresh_from_db()
    make_application(job, Stage.INTERVIEW)
    services.close_job(manager, job)

    content = client.get(url).content.decode()
    assert 'name="restore"' in content
    assert "Restore 1 application rejected by the close" in content
    assert "checked" not in content


def test_post_reopen_without_the_checkbox_does_not_restore(client, manager, job):
    application = make_application(job, Stage.INTERVIEW)
    services.close_job(manager, job)
    client.force_login(manager)

    response = client.post(reverse("ats:job_reopen", args=[job.pk]), follow=True)

    content = response.content.decode()
    assert "Reopened Backend Engineer." in content
    assert "Restored" not in content
    application.refresh_from_db()
    assert application.stage == Stage.REJECTED


def test_post_reopen_with_restore_reports_restored_and_skipped(client, manager, job):
    make_application(job, Stage.INTERVIEW, make_candidate("Rita", "Restored"))
    archived = make_application(job, Stage.APPLIED, make_candidate("Arlo", "Archived"))
    services.close_job(manager, job)
    Candidate.objects.filter(pk=archived.candidate_id).update(is_archived=True)
    client.force_login(manager)

    response = client.post(
        reverse("ats:job_reopen", args=[job.pk]), {"restore": "on"}, follow=True
    )

    content = response.content.decode()
    assert "Restored 1 application." in content
    assert "Skipped 1 application for archived candidates." in content


def test_reopen_page_for_an_open_job_says_so(client, manager, job):
    client.force_login(manager)

    response = client.post(reverse("ats:job_reopen", args=[job.pk]))

    assert response.status_code == 200
    assert "already open" in response.content.decode()


@pytest.mark.parametrize("url_name", ["ats:job_close", "ats:job_reopen"])
@pytest.mark.parametrize("method", ["get", "post"])
def test_close_and_reopen_are_refused_for_recruiters_and_no_role(
    client, recruiter, job, url_name, method
):
    application = make_application(job, Stage.INTERVIEW)
    url = reverse(url_name, args=[job.pk])

    for user in [recruiter, make_user("no-role")]:
        client.force_login(user)
        assert getattr(client, method)(url).status_code == 403

    job.refresh_from_db()
    assert job.status == JobOpening.Status.OPEN
    application.refresh_from_db()
    assert application.stage == Stage.INTERVIEW


@pytest.mark.parametrize("url_name", ["ats:job_close", "ats:job_reopen"])
def test_close_and_reopen_redirect_anonymous_visitors_to_login(client, job, url_name):
    url = reverse(url_name, args=[job.pk])

    response = client.post(url)

    assert response.status_code == 302
    assert response.url == f"{reverse('ats:login')}?next={url}"


@pytest.mark.parametrize("url_name", ["ats:job_close", "ats:job_reopen"])
def test_close_and_reopen_return_404_for_a_missing_job(client, manager, url_name):
    client.force_login(manager)

    assert client.get(reverse(url_name, args=[999])).status_code == 404


def test_job_page_shows_managers_the_action_for_the_jobs_status(
    client, dual_role_user, manager, job
):
    close_url = reverse("ats:job_close", args=[job.pk])
    reopen_url = reverse("ats:job_reopen", args=[job.pk])
    detail_url = reverse("ats:job_detail", args=[job.pk])
    client.force_login(dual_role_user)

    open_page = client.get(detail_url).content.decode()
    services.close_job(manager, job)
    closed_page = client.get(detail_url).content.decode()

    assert close_url in open_page
    assert reopen_url not in open_page
    assert reopen_url in closed_page
    assert close_url not in closed_page


def test_job_page_hides_close_and_reopen_from_recruiters(
    client, recruiter, manager, job
):
    detail_url = reverse("ats:job_detail", args=[job.pk])
    client.force_login(recruiter)

    assert reverse("ats:job_close", args=[job.pk]) not in (
        client.get(detail_url).content.decode()
    )
    services.close_job(manager, job)
    assert reverse("ats:job_reopen", args=[job.pk]) not in (
        client.get(detail_url).content.decode()
    )


def test_admin_cannot_change_status_or_closed_at():
    assert {"status", "closed_at"} <= set(JobOpeningAdmin.readonly_fields)
