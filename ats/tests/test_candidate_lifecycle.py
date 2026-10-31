from datetime import date

import pytest
from django.urls import reverse

from ats import services
from ats.admin import CandidateAdmin
from ats.models import Application, Candidate, JobOpening, StageChange
from ats.pipeline import ACTIVE_STAGES, Stage
from ats.tests.conftest import (
    fail_on_second_move,
    make_application,
    make_candidate,
    make_user,
)
from ats.urls import urlpatterns


def apply_to_new_jobs(candidate, stages, user):
    return [
        make_application(
            JobOpening.objects.create(title=f"Role {index}", created_by=user),
            stage,
            candidate,
        )
        for index, stage in enumerate(stages)
    ]


def test_candidates_list_hides_archived_people_until_the_toggle_is_on_and_searches_both(
    client, recruiter, manager
):
    make_candidate("Alma", "Active")
    make_candidate("Sam", "Active")
    archived = make_candidate("Alma", "Archived")
    services.archive_candidate(manager, archived)
    url = reverse("ats:candidate_list")
    client.force_login(recruiter)

    default = client.get(url).content.decode()
    toggled = client.get(url, {"archived": "on"}).content.decode()
    searched = client.get(url, {"q": "alma"}).content.decode()
    toggled_search = client.get(url, {"q": "alma", "archived": "on"}).content.decode()

    assert "Alma Active" in default
    assert "Alma Archived" not in default
    assert "Alma Active" in toggled
    assert "Alma Archived" in toggled
    assert "Alma Active" in searched
    assert "Sam Active" not in searched
    assert "Alma Archived" not in searched
    assert "Alma Active" in toggled_search
    assert "Alma Archived" in toggled_search
    assert "Sam Active" not in toggled_search


def test_unarchive_with_restore_returns_only_applications_the_archive_withdrew(
    job, manager
):
    candidate = make_candidate()
    closing_job = JobOpening.objects.create(title="Closing Role", created_by=manager)
    earlier_job = JobOpening.objects.create(title="Earlier Role", created_by=manager)
    archived_out = make_application(job, Stage.INTERVIEW, candidate)
    job_closed = make_application(closing_job, Stage.SCREENING, candidate)
    withdrew_earlier = make_application(earlier_job, Stage.SCREENING, candidate)
    services.move_application(manager, withdrew_earlier, Stage.WITHDRAWN)
    services.archive_candidate(manager, candidate)
    services.close_job(manager, closing_job)

    restored, skipped = services.unarchive_candidate(manager, candidate, restore=True)

    assert (restored, skipped) == (1, 1)
    candidate.refresh_from_db()
    assert candidate.is_archived is False
    archived_out.refresh_from_db()
    assert archived_out.stage == Stage.INTERVIEW
    change = archived_out.stage_changes.first()
    assert change.from_stage == Stage.WITHDRAWN
    assert change.to_stage == Stage.INTERVIEW
    assert change.changed_by == manager
    assert change.reason == StageChange.Reason.CANDIDATE_UNARCHIVED
    for application in [job_closed, withdrew_earlier]:
        application.refresh_from_db()
        assert application.stage == Stage.WITHDRAWN
        reasons = application.stage_changes.values_list("reason", flat=True)
        assert StageChange.Reason.CANDIDATE_UNARCHIVED not in reasons


def test_list_marks_archived_people_and_keeps_the_toggle_on(client, recruiter, manager):
    services.archive_candidate(manager, make_candidate("Arlo", "Archived"))
    url = reverse("ats:candidate_list")
    client.force_login(recruiter)

    default = client.get(url).content.decode()
    toggled = client.get(url, {"archived": "on"}).content.decode()

    assert 'name="archived" checked' not in default
    assert 'name="archived" checked' in toggled
    assert ">Archived</span>" in toggled


def test_archive_withdraws_active_applications_and_leaves_other_stages_alone(manager):
    candidate = make_candidate()
    active = apply_to_new_jobs(candidate, ACTIVE_STAGES, manager)
    outcome_stages = [Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN]
    outcomes = [
        make_application(
            JobOpening.objects.create(title=f"Outcome {stage}", created_by=manager),
            stage,
            candidate,
        )
        for stage in outcome_stages
    ]

    withdrawn = services.archive_candidate(manager, candidate)

    assert withdrawn == len(ACTIVE_STAGES)
    candidate.refresh_from_db()
    assert candidate.is_archived is True
    for application, previous in zip(active, ACTIVE_STAGES, strict=True):
        application.refresh_from_db()
        assert application.stage == Stage.WITHDRAWN
        change = application.stage_changes.get()
        assert change.from_stage == previous
        assert change.to_stage == Stage.WITHDRAWN
        assert change.changed_by == manager
        assert change.reason == StageChange.Reason.CANDIDATE_ARCHIVED
    for application, stage in zip(outcomes, outcome_stages, strict=True):
        application.refresh_from_db()
        assert application.stage == stage
        assert not application.stage_changes.exists()


def test_archive_is_refused_while_an_application_is_in_offer(job, manager):
    candidate = make_candidate()
    make_application(job, Stage.OFFER, candidate)
    active = apply_to_new_jobs(candidate, [Stage.INTERVIEW], manager)[0]

    with pytest.raises(services.CandidateArchiveRefused, match="Offer"):
        services.archive_candidate(manager, candidate)

    candidate.refresh_from_db()
    assert candidate.is_archived is False
    active.refresh_from_db()
    assert active.stage == Stage.INTERVIEW
    assert not StageChange.objects.exists()


def test_archiving_an_archived_candidate_is_refused(job, manager):
    candidate = make_candidate()
    services.archive_candidate(manager, candidate)

    with pytest.raises(services.CandidateArchiveRefused, match="already archived"):
        services.archive_candidate(manager, candidate)


def test_unarchiving_an_active_candidate_is_refused_and_restores_nothing(job, manager):
    candidate = make_candidate()
    application = make_application(job, Stage.INTERVIEW, candidate)
    services.archive_candidate(manager, candidate)
    services.unarchive_candidate(manager, candidate)

    with pytest.raises(services.CandidateUnarchiveRefused, match="not archived"):
        services.unarchive_candidate(manager, candidate, restore=True)

    application.refresh_from_db()
    assert application.stage == Stage.WITHDRAWN


def test_unarchive_without_restore_clears_the_flag_and_changes_no_applications(
    job, manager
):
    candidate = make_candidate()
    application = make_application(job, Stage.INTERVIEW, candidate)
    services.archive_candidate(manager, candidate)
    changes = StageChange.objects.count()

    result = services.unarchive_candidate(manager, candidate)

    assert result == (0, 0)
    candidate.refresh_from_db()
    assert candidate.is_archived is False
    application.refresh_from_db()
    assert application.stage == Stage.WITHDRAWN
    assert StageChange.objects.count() == changes


def test_restore_leaves_an_application_withdrawn_again_after_a_manual_reopen(
    job, manager
):
    candidate = make_candidate()
    application = make_application(job, Stage.INTERVIEW, candidate)
    services.archive_candidate(manager, candidate)
    services.unarchive_candidate(manager, candidate)
    application.refresh_from_db()
    services.move_application(manager, application, Stage.INTERVIEW)
    services.move_application(manager, application, Stage.WITHDRAWN)
    services.archive_candidate(manager, candidate)

    assert services.unarchive_candidate(manager, candidate, restore=True) == (0, 0)

    application.refresh_from_db()
    assert application.stage == Stage.WITHDRAWN


def test_archive_applies_nothing_when_a_move_fails(manager, monkeypatch):
    candidate = make_candidate()
    applications = apply_to_new_jobs(
        candidate, [Stage.APPLIED, Stage.SCREENING], manager
    )
    fail_on_second_move(monkeypatch)

    with pytest.raises(RuntimeError):
        services.archive_candidate(manager, candidate)

    assert Candidate.objects.get(pk=candidate.pk).is_archived is False
    assert not StageChange.objects.exists()
    applications[0].refresh_from_db()
    assert applications[0].stage == Stage.APPLIED


def test_unarchive_applies_nothing_when_a_restore_fails(manager, monkeypatch):
    candidate = make_candidate()
    applications = apply_to_new_jobs(
        candidate, [Stage.APPLIED, Stage.SCREENING], manager
    )
    services.archive_candidate(manager, candidate)
    changes = StageChange.objects.count()
    fail_on_second_move(monkeypatch)

    with pytest.raises(RuntimeError):
        services.unarchive_candidate(manager, candidate, restore=True)

    assert Candidate.objects.get(pk=candidate.pk).is_archived is True
    assert StageChange.objects.count() == changes
    applications[0].refresh_from_db()
    assert applications[0].stage == Stage.WITHDRAWN


def test_archived_candidate_refuses_new_applications_and_leaves_the_pickers(
    client, job, manager, recruiter
):
    candidate = make_candidate()
    assert Candidate.objects.available_for(job).exists()
    services.archive_candidate(manager, candidate)
    client.force_login(recruiter)

    with pytest.raises(services.ApplicationRefused, match="archived"):
        services.create_application(recruiter, candidate, job, date(2026, 1, 1))

    picker = client.get(reverse("ats:job_application_create", args=[job.pk]))
    assert candidate.email not in picker.content.decode()
    assert not Application.objects.exists()


def test_archive_page_shows_the_number_that_will_be_withdrawn(client, manager):
    candidate = make_candidate()
    apply_to_new_jobs(candidate, [*ACTIVE_STAGES, Stage.HIRED], manager)
    client.force_login(manager)

    content = client.get(
        reverse("ats:candidate_archive", args=[candidate.pk])
    ).content.decode()

    assert "<strong>4</strong> active applications" in content
    assert "Archive candidate</button>" in content
    assert Candidate.objects.get(pk=candidate.pk).is_archived is False


def test_archive_page_lists_offers_and_offers_no_confirmation(client, manager, job):
    candidate = make_candidate()
    make_application(job, Stage.OFFER, candidate)
    client.force_login(manager)

    content = client.get(
        reverse("ats:candidate_archive", args=[candidate.pk])
    ).content.decode()

    assert job.title in content
    assert "Archive candidate</button>" not in content


def test_post_archive_withdraws_and_redirects_to_the_candidate_with_a_message(
    client, manager, job
):
    candidate = make_candidate()
    application = make_application(job, Stage.INTERVIEW, candidate)
    client.force_login(manager)

    response = client.post(
        reverse("ats:candidate_archive", args=[candidate.pk]), follow=True
    )

    assert response.redirect_chain == [
        (reverse("ats:candidate_detail", args=[candidate.pk]), 302)
    ]
    assert "Withdrew 1 application." in response.content.decode()
    candidate.refresh_from_db()
    assert candidate.is_archived is True
    application.refresh_from_db()
    assert application.stage == Stage.WITHDRAWN


def test_post_archive_with_an_offer_explains_and_changes_nothing(client, manager, job):
    candidate = make_candidate()
    make_application(job, Stage.OFFER, candidate)
    client.force_login(manager)

    response = client.post(reverse("ats:candidate_archive", args=[candidate.pk]))

    assert response.status_code == 200
    assert "cannot be archived" in response.content.decode()
    candidate.refresh_from_db()
    assert candidate.is_archived is False


def test_archive_page_for_an_archived_candidate_says_so(client, manager):
    candidate = make_candidate()
    services.archive_candidate(manager, candidate)
    client.force_login(manager)

    response = client.post(reverse("ats:candidate_archive", args=[candidate.pk]))

    assert response.status_code == 200
    assert "already archived" in response.content.decode()


def test_unarchive_page_offers_restore_only_when_something_can_be_restored(
    client, manager, job
):
    candidate = make_candidate()
    url = reverse("ats:candidate_unarchive", args=[candidate.pk])
    services.archive_candidate(manager, candidate)
    client.force_login(manager)
    assert 'name="restore"' not in client.get(url).content.decode()

    client.post(url)
    candidate.refresh_from_db()
    make_application(job, Stage.INTERVIEW, candidate)
    services.archive_candidate(manager, candidate)

    content = client.get(url).content.decode()
    assert 'name="restore"' in content
    assert "Restore 1 application withdrawn by the archive" in content
    assert "checked" not in content


def test_post_unarchive_without_the_checkbox_does_not_restore(client, manager, job):
    candidate = make_candidate()
    application = make_application(job, Stage.INTERVIEW, candidate)
    services.archive_candidate(manager, candidate)
    client.force_login(manager)

    response = client.post(
        reverse("ats:candidate_unarchive", args=[candidate.pk]), follow=True
    )

    content = response.content.decode()
    assert "Unarchived Jane Doe." in content
    assert "Restored" not in content
    application.refresh_from_db()
    assert application.stage == Stage.WITHDRAWN


def test_post_unarchive_with_restore_reports_restored_and_skipped(client, manager, job):
    candidate = make_candidate()
    closing_job = JobOpening.objects.create(title="Closing Role", created_by=manager)
    make_application(job, Stage.INTERVIEW, candidate)
    make_application(closing_job, Stage.APPLIED, candidate)
    services.archive_candidate(manager, candidate)
    services.close_job(manager, closing_job)
    client.force_login(manager)

    response = client.post(
        reverse("ats:candidate_unarchive", args=[candidate.pk]),
        {"restore": "on"},
        follow=True,
    )

    content = response.content.decode()
    assert "Restored 1 application." in content
    assert "Skipped 1 application for closed jobs." in content


def test_unarchive_page_for_an_active_candidate_says_so(client, manager):
    candidate = make_candidate()
    client.force_login(manager)

    response = client.post(reverse("ats:candidate_unarchive", args=[candidate.pk]))

    assert response.status_code == 200
    assert "not archived" in response.content.decode()


@pytest.mark.parametrize(
    "url_name, start_archived",
    [("ats:candidate_archive", False), ("ats:candidate_unarchive", True)],
)
@pytest.mark.parametrize("method", ["get", "post"])
def test_archive_and_unarchive_are_refused_for_recruiters_and_no_role(
    client, recruiter, job, url_name, start_archived, method
):
    candidate = make_candidate()
    candidate.is_archived = start_archived
    candidate.save()
    application = make_application(job, Stage.INTERVIEW, candidate)
    url = reverse(url_name, args=[candidate.pk])

    for user in [recruiter, make_user("no-role")]:
        client.force_login(user)
        assert getattr(client, method)(url).status_code == 403

    candidate.refresh_from_db()
    assert candidate.is_archived is start_archived
    application.refresh_from_db()
    assert application.stage == Stage.INTERVIEW


@pytest.mark.parametrize(
    "url_name", ["ats:candidate_archive", "ats:candidate_unarchive"]
)
def test_archive_and_unarchive_redirect_anonymous_visitors_to_login(
    client, db, url_name
):
    url = reverse(url_name, args=[1])

    response = client.post(url)

    assert response.status_code == 302
    assert response.url == f"{reverse('ats:login')}?next={url}"


@pytest.mark.parametrize(
    "url_name", ["ats:candidate_archive", "ats:candidate_unarchive"]
)
def test_archive_and_unarchive_return_404_for_a_missing_candidate(
    client, manager, url_name
):
    client.force_login(manager)

    assert client.get(reverse(url_name, args=[999])).status_code == 404


def test_candidate_page_shows_managers_the_action_for_the_candidates_state(
    client, dual_role_user, manager
):
    candidate = make_candidate()
    archive_url = reverse("ats:candidate_archive", args=[candidate.pk])
    unarchive_url = reverse("ats:candidate_unarchive", args=[candidate.pk])
    detail_url = reverse("ats:candidate_detail", args=[candidate.pk])
    client.force_login(dual_role_user)

    active_page = client.get(detail_url).content.decode()
    services.archive_candidate(manager, candidate)
    archived_page = client.get(detail_url).content.decode()

    assert archive_url in active_page
    assert unarchive_url not in active_page
    assert ">Archived</span>" not in active_page
    assert unarchive_url in archived_page
    assert archive_url not in archived_page
    assert ">Archived</span>" in archived_page


def test_candidate_page_hides_archive_and_unarchive_from_recruiters(
    client, recruiter, manager
):
    candidate = make_candidate()
    detail_url = reverse("ats:candidate_detail", args=[candidate.pk])
    client.force_login(recruiter)

    assert reverse("ats:candidate_archive", args=[candidate.pk]) not in (
        client.get(detail_url).content.decode()
    )
    services.archive_candidate(manager, candidate)
    assert reverse("ats:candidate_unarchive", args=[candidate.pk]) not in (
        client.get(detail_url).content.decode()
    )


def test_history_survives_archive_and_unarchive(job, manager):
    candidate = make_candidate()
    application = make_application(job, Stage.INTERVIEW, candidate)
    note = services.add_note(manager, candidate, "Prefers remote work.", application)

    services.archive_candidate(manager, candidate)
    services.unarchive_candidate(manager, candidate, restore=True)

    assert candidate.notes.get() == note
    assert list(
        application.stage_changes.order_by("pk").values_list("from_stage", "to_stage")
    ) == [
        (Stage.INTERVIEW, Stage.WITHDRAWN),
        (Stage.WITHDRAWN, Stage.INTERVIEW),
    ]


def test_the_app_has_no_route_for_deleting_a_candidate():
    assert not [
        pattern.name
        for pattern in urlpatterns
        if "candidate" in pattern.name and "delete" in pattern.name
    ]


def test_admin_cannot_change_the_archived_flag():
    assert "is_archived" in CandidateAdmin.readonly_fields
