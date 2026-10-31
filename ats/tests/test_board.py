import re
from datetime import date, timedelta

import pytest
from django.contrib.staticfiles import finders
from django.db import connection
from django.templatetags.static import static
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from ats.models import Application, JobOpening, StageChange
from ats.pipeline import Stage, can_transition
from ats.tests.conftest import make_application, make_candidate, make_user


def post_move(client, application, stage):
    return client.post(
        reverse("ats:application_move", args=[application.pk]),
        {"stage": stage},
        headers={"HX-Request": "true"},
    )


def rendered_card(response, application):
    url = reverse("ats:application_move", args=[application.pk])
    card = re.search(
        rf'<li[^>]*data-move-url="{url}".*?</li>',
        response.content.decode(),
        re.DOTALL,
    )
    assert card, f"no card for {url}"
    return card.group()


def rendered_allowed_stages(response, application):
    card = rendered_card(response, application)
    allowed = re.search(r'data-allowed-stages="([^"]*)"', card)
    assert allowed, "card has no data-allowed-stages attribute"
    return set(allowed.group(1).split())


def record_change(application, user, days_ago):
    change = StageChange.objects.create(
        application=application,
        to_stage=application.stage,
        changed_by=user,
        reason=StageChange.Reason.NORMAL_MOVE,
    )
    StageChange.objects.filter(pk=change.pk).update(
        changed_at=timezone.now() - timedelta(days=days_ago)
    )


@pytest.mark.parametrize("role", ["recruiter", "manager", "dual_role_user"])
@pytest.mark.parametrize("stage", Stage.values)
def test_card_allowed_stages_match_can_transition(request, client, job, role, stage):
    application = make_application(job, stage)
    user = request.getfixturevalue(role)
    client.force_login(user)

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    assert rendered_allowed_stages(response, application) == {
        target for target in Stage.values if can_transition(user, application, target)
    }


@pytest.mark.parametrize(
    ("role", "target", "expected"),
    [
        pytest.param(
            "manager",
            Stage.OFFER,
            {
                Stage.APPLIED,
                Stage.SCREENING,
                Stage.INTERVIEW,
                Stage.FINAL_REVIEW,
                Stage.HIRED,
                Stage.REJECTED,
                Stage.WITHDRAWN,
            },
            id="allowed-manager-offer",
        ),
        pytest.param(
            "manager", Stage.REJECTED, {Stage.FINAL_REVIEW}, id="allowed-manager-exit"
        ),
        pytest.param("recruiter", Stage.REJECTED, set(), id="allowed-recruiter-exit"),
        pytest.param(
            "recruiter",
            Stage.OFFER,
            {
                Stage.APPLIED,
                Stage.SCREENING,
                Stage.INTERVIEW,
                Stage.REJECTED,
                Stage.WITHDRAWN,
            },
            id="refused-stays-in-final-review",
        ),
    ],
)
def test_move_response_carries_targets_for_the_cards_current_stage(
    request, client, job, role, target, expected
):
    application = make_application(job, Stage.FINAL_REVIEW)
    client.force_login(request.getfixturevalue(role))

    response = post_move(client, application, target)

    assert rendered_allowed_stages(response, application) == expected


@pytest.mark.parametrize(
    ("created_days_ago", "change_days_ago", "expected"),
    [
        pytest.param(40, [20, 3, 10], "Moved 3\xa0days ago", id="latest-change"),
        pytest.param(5, [], "Moved 5\xa0days ago", id="no-changes-uses-created"),
    ],
)
def test_card_shows_time_since_last_move(
    client, job, recruiter, created_days_ago, change_days_ago, expected
):
    application = make_application(job, Stage.SCREENING)
    Application.objects.filter(pk=application.pk).update(
        created_at=timezone.now() - timedelta(days=created_days_ago)
    )
    for days_ago in change_days_ago:
        record_change(application, recruiter, days_ago)
    client.force_login(recruiter)

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    assert expected in rendered_card(response, application)


ACTIVE_STAGES = {Stage.APPLIED, Stage.SCREENING, Stage.INTERVIEW, Stage.FINAL_REVIEW}
EXIT_STAGES = {Stage.REJECTED, Stage.WITHDRAWN}


@pytest.mark.parametrize(
    ("role", "stage", "expected"),
    [
        (
            "recruiter",
            Stage.FINAL_REVIEW,
            (ACTIVE_STAGES - {Stage.FINAL_REVIEW}) | EXIT_STAGES,
        ),
        (
            "manager",
            Stage.FINAL_REVIEW,
            (ACTIVE_STAGES - {Stage.FINAL_REVIEW}) | EXIT_STAGES | {Stage.OFFER},
        ),
        ("recruiter", Stage.OFFER, EXIT_STAGES),
        ("manager", Stage.OFFER, ACTIVE_STAGES | EXIT_STAGES | {Stage.HIRED}),
        ("recruiter", Stage.HIRED, set()),
        ("manager", Stage.HIRED, ACTIVE_STAGES | EXIT_STAGES | {Stage.OFFER}),
    ],
)
def test_rendered_targets_differ_by_role(request, client, job, role, stage, expected):
    application = make_application(job, stage)
    client.force_login(request.getfixturevalue(role))

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    assert rendered_allowed_stages(response, application) == expected


def test_only_an_archived_candidates_card_shows_the_archived_badge(
    client, job, recruiter
):
    archived = make_application(job, Stage.WITHDRAWN)
    archived.candidate.is_archived = True
    archived.candidate.save()
    active = make_application(job, candidate=make_candidate("Sam", "Lee"))
    client.force_login(recruiter)

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    assert ">Archived</span>" in rendered_card(response, archived)
    assert ">Archived</span>" not in rendered_card(response, active)


def test_rejected_card_offers_only_its_previous_stage_to_a_manager(
    client, job, manager
):
    application = make_application(job, Stage.REJECTED)
    StageChange.objects.create(
        application=application,
        from_stage=Stage.INTERVIEW,
        to_stage=Stage.REJECTED,
        changed_by=manager,
        reason=StageChange.Reason.NORMAL_MOVE,
    )
    client.force_login(manager)

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    assert rendered_allowed_stages(response, application) == {Stage.INTERVIEW}


def test_closed_job_cards_only_offer_exit_stages(client, job, manager):
    application = make_application(job, Stage.INTERVIEW)
    JobOpening.objects.filter(pk=job.pk).update(status=JobOpening.Status.CLOSED)
    client.force_login(manager)

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    assert rendered_allowed_stages(response, application) == EXIT_STAGES


def test_card_shows_candidate_and_application_details(client, job, recruiter):
    candidate = make_candidate("Ann", "Lee")
    candidate.lead_source_detail = "Indeed"
    candidate.save()
    application = make_application(job, candidate=candidate)
    Application.objects.filter(pk=application.pk).update(
        application_date=date(2026, 1, 15)
    )
    client.force_login(recruiter)

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    card = rendered_card(response, application)
    assert "Ann Lee" in card
    assert "ann.lee@example.com" in card
    assert "Job Board: Indeed" in card
    assert "Applied Jan 15, 2026" in card


def test_card_links_the_candidates_name_to_their_profile(client, job, recruiter):
    application = make_application(job)
    url = reverse("ats:candidate_detail", args=[application.candidate_id])
    client.force_login(recruiter)

    page = client.get(reverse("ats:job_detail", args=[job.pk]))
    moved = client.post(
        reverse("ats:application_move", args=[application.pk]),
        {"stage": Stage.SCREENING},
    )

    link = f'href="{url}">Jane Doe</a>'
    assert link in page.content.decode()
    assert link in moved.content.decode()


def test_card_without_lead_source_detail_shows_only_the_source(client, job, recruiter):
    application = make_application(job)
    client.force_login(recruiter)

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    card = rendered_card(response, application)
    assert "Job Board" in card
    assert "Job Board:" not in card


def test_board_query_count_does_not_grow_with_cards(client, job, recruiter):
    client.force_login(recruiter)
    url = reverse("ats:job_detail", args=[job.pk])
    make_application(job, candidate=make_candidate("Ann", "Lee"))
    with CaptureQueriesContext(connection) as one_card:
        client.get(url)

    for first_name in ("Bo", "Cy", "Di", "Ed"):
        application = make_application(job, candidate=make_candidate(first_name, "Lee"))
        record_change(application, recruiter, days_ago=1)
    with CaptureQueriesContext(connection) as five_cards:
        client.get(url)

    assert len(five_cards) == len(one_card)


def test_board_shows_every_column_with_a_count(client, job, recruiter):
    make_application(job, Stage.SCREENING)
    client.force_login(recruiter)

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    assert response.status_code == 200
    assert {
        column["label"]: len(column["applications"])
        for column in response.context["columns"]
    } == {
        "Applied": 0,
        "Screening": 1,
        "Interview": 0,
        "Final Review": 0,
        "Offer": 0,
        "Hired": 0,
        "Rejected": 0,
        "Withdrawn": 0,
    }
    content = response.content.decode()
    for stage in Stage.values:
        assert f'data-stage="{stage}"' in content


def test_board_loads_drag_and_drop_from_project_static_files(client, job, recruiter):
    client.force_login(recruiter)

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    for script in ("Sortable.min.js", "htmx.min.js", "board.js"):
        assert static(f"ats/js/{script}") in response.content.decode()
        assert finders.find(f"ats/js/{script}")


def test_board_requires_login(client, job):
    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    assert response.status_code == 302
    assert response.url.startswith(reverse("ats:login"))


def test_missing_job_returns_404(client, recruiter):
    client.force_login(recruiter)

    assert client.get(reverse("ats:job_detail", args=[999])).status_code == 404


def test_move_returns_full_board_with_current_data(client, job, recruiter):
    moved = make_application(job, candidate=make_candidate("Ann", "Lee"))
    colleagues = make_application(job, candidate=make_candidate("Bo", "Diaz"))
    client.force_login(recruiter)
    # A colleague moves this card after the board was loaded in this browser.
    Application.objects.filter(pk=colleagues.pk).update(stage=Stage.INTERVIEW)

    response = post_move(client, moved, Stage.SCREENING)

    assert response.status_code == 200
    content = response.content.decode()
    assert "<html" not in content
    assert "Ann Lee" in content
    assert "Bo Diaz" in content
    assert {
        column["label"]: len(column["applications"])
        for column in response.context["columns"]
    } == {
        "Applied": 0,
        "Screening": 1,
        "Interview": 1,
        "Final Review": 0,
        "Offer": 0,
        "Hired": 0,
        "Rejected": 0,
        "Withdrawn": 0,
    }


def test_move_records_the_signed_in_user(client, job, recruiter):
    application = make_application(job)
    client.force_login(recruiter)

    post_move(client, application, Stage.FINAL_REVIEW)

    change = StageChange.objects.get(application=application)
    assert change.changed_by == recruiter
    assert change.to_stage == Stage.FINAL_REVIEW


def test_refused_move_returns_board_and_changes_nothing(client, job, recruiter):
    application = make_application(job, candidate=make_candidate("Ann", "Lee"))
    client.force_login(recruiter)

    response = post_move(client, application, Stage.OFFER)

    assert response.status_code == 200
    assert "Ann Lee" in response.content.decode()
    application.refresh_from_db()
    assert application.stage == Stage.APPLIED
    assert not StageChange.objects.exists()


def test_refused_move_shows_a_toast_with_the_reason(client, job, recruiter):
    application = make_application(job, Stage.FINAL_REVIEW)
    client.force_login(recruiter)

    response = post_move(client, application, Stage.OFFER)

    content = response.content.decode()
    assert "data-move-error" in content
    assert "Only a hiring manager can make an offer." in content
    application.refresh_from_db()
    assert application.stage == Stage.FINAL_REVIEW
    assert not StageChange.objects.exists()


def test_allowed_move_shows_no_toast(client, job, recruiter):
    application = make_application(job)
    client.force_login(recruiter)

    response = post_move(client, application, Stage.SCREENING)

    assert "data-move-error" not in response.content.decode()


def test_board_page_shows_no_toast(client, job, recruiter):
    client.force_login(recruiter)

    response = client.get(reverse("ats:job_detail", args=[job.pk]))

    assert "data-move-error" not in response.content.decode()


def test_manager_move_through_the_endpoint_records_the_change(client, job, manager):
    application = make_application(job, Stage.FINAL_REVIEW)
    client.force_login(manager)

    response = post_move(client, application, Stage.OFFER)

    assert "data-move-error" not in response.content.decode()
    application.refresh_from_db()
    assert application.stage == Stage.OFFER
    assert StageChange.objects.get().to_stage == Stage.OFFER


@pytest.mark.parametrize(
    ("role", "stage", "target"),
    [
        ("recruiter", Stage.FINAL_REVIEW, Stage.OFFER),
        ("recruiter", Stage.OFFER, Stage.HIRED),
        ("recruiter", Stage.OFFER, Stage.FINAL_REVIEW),
        ("recruiter", Stage.HIRED, Stage.OFFER),
        ("recruiter", Stage.REJECTED, Stage.APPLIED),
        ("manager", Stage.APPLIED, Stage.OFFER),
        ("manager", Stage.SCREENING, Stage.HIRED),
        ("manager", Stage.WITHDRAWN, Stage.HIRED),
        ("manager", Stage.APPLIED, "not-a-stage"),
        ("manager", Stage.APPLIED, ""),
    ],
)
def test_hand_crafted_post_cannot_bypass_a_rule(
    request, client, job, role, stage, target
):
    application = make_application(job, stage)
    client.force_login(request.getfixturevalue(role))

    response = post_move(client, application, target)

    assert response.status_code == 200
    assert "data-move-error" in response.content.decode()
    application.refresh_from_db()
    assert application.stage == stage
    assert not StageChange.objects.exists()


def test_move_without_a_stage_is_refused(client, job, manager):
    application = make_application(job)
    client.force_login(manager)

    response = client.post(reverse("ats:application_move", args=[application.pk]))

    assert "data-move-error" in response.content.decode()
    assert not StageChange.objects.exists()


def test_closed_job_refusal_explains_itself(client, job, manager):
    application = make_application(job, Stage.INTERVIEW)
    JobOpening.objects.filter(pk=job.pk).update(status=JobOpening.Status.CLOSED)
    client.force_login(manager)

    response = post_move(client, application, Stage.SCREENING)

    assert "This job is closed" in response.content.decode()
    application.refresh_from_db()
    assert application.stage == Stage.INTERVIEW


def test_archived_candidate_refusal_explains_itself(client, job, manager):
    candidate = make_candidate()
    candidate.is_archived = True
    candidate.save()
    application = make_application(job, Stage.INTERVIEW, candidate)
    client.force_login(manager)

    response = post_move(client, application, Stage.SCREENING)

    assert "This candidate is archived" in response.content.decode()
    application.refresh_from_db()
    assert application.stage == Stage.INTERVIEW


def test_move_to_the_current_stage_records_nothing(client, job, recruiter):
    application = make_application(job, Stage.SCREENING)
    client.force_login(recruiter)

    response = post_move(client, application, Stage.SCREENING)

    assert response.status_code == 200
    assert not StageChange.objects.exists()


def test_move_requires_login(client, job):
    application = make_application(job)

    response = post_move(client, application, Stage.SCREENING)

    assert response.status_code == 302
    assert response.url.startswith(reverse("ats:login"))
    application.refresh_from_db()
    assert application.stage == Stage.APPLIED


def test_move_is_forbidden_without_a_role(client, job):
    application = make_application(job)
    client.force_login(make_user("no-role"))

    response = post_move(client, application, Stage.SCREENING)

    assert response.status_code == 403
    application.refresh_from_db()
    assert application.stage == Stage.APPLIED


def test_move_rejects_get(client, job, recruiter):
    application = make_application(job)
    client.force_login(recruiter)

    url = reverse("ats:application_move", args=[application.pk])

    assert client.get(url).status_code == 405
