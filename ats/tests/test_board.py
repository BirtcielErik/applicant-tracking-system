from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse

from ats.models import Application, StageChange
from ats.pipeline import Stage
from ats.tests.conftest import make_application, make_candidate, make_user


def post_move(client, application, stage):
    return client.post(
        reverse("ats:application_move", args=[application.pk]),
        {"stage": stage},
        headers={"HX-Request": "true"},
    )


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
