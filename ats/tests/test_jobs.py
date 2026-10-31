from datetime import UTC, datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ats import services
from ats.models import JobOpening
from ats.pipeline import Stage
from ats.tests.conftest import make_application, make_candidate, make_user

CLOSED_AT = datetime(2026, 3, 5, 18, tzinfo=UTC)


def make_closed_job(created_by, title="Data Analyst"):
    return JobOpening.objects.create(
        title=title,
        status=JobOpening.Status.CLOSED,
        created_by=created_by,
        closed_at=CLOSED_AT,
    )


def job_data(**overrides):
    return {
        "title": "Support Engineer",
        "department": "",
        "location": "",
        "description": "",
        **overrides,
    }


def test_home_counts_only_active_applicants(client, recruiter, job):
    for index, stage in enumerate(Stage.values):
        make_application(job, stage, make_candidate("Applicant", str(index)))
    client.force_login(recruiter)

    response = client.get(reverse("ats:home"))

    assert 'data-active-applicants="4"' in response.content.decode()


def test_home_lists_open_jobs_by_default_and_closed_jobs_with_the_filter(
    client, recruiter, job
):
    make_closed_job(job.created_by)
    client.force_login(recruiter)

    default_page = client.get(reverse("ats:home")).content.decode()
    closed_page = client.get(reverse("ats:home"), {"status": "closed"}).content.decode()

    assert "Backend Engineer" in default_page
    assert "Data Analyst" not in default_page
    assert "Data Analyst" in closed_page
    assert "Backend Engineer" not in closed_page


def test_create_records_the_signed_in_user_and_starts_open_despite_a_forged_post(
    client, recruiter, manager
):
    client.force_login(recruiter)

    client.post(
        reverse("ats:job_create"),
        job_data(status=JobOpening.Status.CLOSED, created_by=manager.pk),
    )

    job = JobOpening.objects.get()
    assert job.created_by == recruiter
    assert job.status == JobOpening.Status.OPEN


def test_each_job_gets_its_own_count_and_a_job_with_none_shows_zero(
    client, recruiter, job
):
    other = JobOpening.objects.create(title="Designer", created_by=job.created_by)
    make_application(job, Stage.INTERVIEW)
    client.force_login(recruiter)

    jobs = client.get(reverse("ats:home")).context["jobs"]

    counts = {listed.title: listed.active_applicants for listed in jobs}
    assert counts == {job.title: 1, other.title: 0}


def test_home_query_count_does_not_grow_with_jobs(client, recruiter, job):
    make_application(job)
    client.force_login(recruiter)
    with CaptureQueriesContext(connection) as one_job:
        client.get(reverse("ats:home"))

    for index in range(5):
        creator = make_user(f"creator-{index}", "Recruiter")
        extra = JobOpening.objects.create(title=f"Job {index}", created_by=creator)
        make_application(extra, candidate=make_candidate("Extra", str(index)))
    with CaptureQueriesContext(connection) as six_jobs:
        client.get(reverse("ats:home"))

    assert len(six_jobs) == len(one_job)


def test_home_treats_an_unknown_status_as_open(client, recruiter, job):
    make_closed_job(job.created_by)
    client.force_login(recruiter)

    content = client.get(reverse("ats:home"), {"status": "banana"}).content.decode()

    assert "Backend Engineer" in content
    assert "Data Analyst" not in content


def test_home_links_to_both_filters_and_marks_the_current_one(client, recruiter):
    client.force_login(recruiter)
    home = reverse("ats:home")

    default_page = client.get(home).content.decode()
    closed_page = client.get(home, {"status": "closed"}).content.decode()

    open_tab = f'<a class="tab tab-active" role="tab" href="{home}">Open</a>'
    closed_tab = (
        f'<a class="tab tab-active" role="tab" href="{home}?status=closed">Closed</a>'
    )
    assert open_tab in default_page
    assert f'href="{home}?status=closed"' in default_page
    assert closed_tab in closed_page


def test_home_says_when_there_are_no_jobs(client, recruiter):
    client.force_login(recruiter)

    home = reverse("ats:home")

    assert "No open jobs." in client.get(home).content.decode()
    closed_page = client.get(home, {"status": "closed"}).content.decode()
    assert "No closed jobs." in closed_page


def test_home_links_each_job_to_its_board(client, recruiter, job):
    client.force_login(recruiter)

    response = client.get(reverse("ats:home"))

    assert f'href="{reverse("ats:job_detail", args=[job.pk])}"' in (
        response.content.decode()
    )


def test_home_shows_the_creator_and_the_closed_view_shows_the_closed_date(
    client, recruiter, manager, job
):
    make_closed_job(manager)
    client.force_login(recruiter)
    home = reverse("ats:home")

    default_page = client.get(home).content.decode()
    closed_page = client.get(home, {"status": "closed"}).content.decode()

    assert "<td>manager</td>" in default_page
    assert "Mar 5, 2026" not in default_page
    assert "<td>manager</td>" in closed_page
    assert "<td>Mar 5, 2026</td>" in closed_page


def test_job_detail_shows_the_details_and_creator_of_an_open_job(
    client, recruiter, manager
):
    job = JobOpening.objects.create(
        title="Backend Engineer",
        department="Engineering",
        location="Remote",
        description="Build the API.",
        created_by=manager,
    )
    client.force_login(recruiter)

    content = client.get(reverse("ats:job_detail", args=[job.pk])).content.decode()

    for text in ["Engineering", "Remote", "Build the API.", "Created by manager"]:
        assert text in content
    assert "· Closed" not in content


def test_job_detail_shows_the_closed_date_of_a_closed_job(client, recruiter, manager):
    job = make_closed_job(manager)
    client.force_login(recruiter)

    content = client.get(reverse("ats:job_detail", args=[job.pk])).content.decode()

    assert "· Closed Mar 5, 2026" in content


def test_job_detail_colors_the_status_badge_by_status(client, recruiter, manager, job):
    closed_job = make_closed_job(manager)
    client.force_login(recruiter)

    open_page = client.get(reverse("ats:job_detail", args=[job.pk]))
    closed_page = client.get(reverse("ats:job_detail", args=[closed_job.pk]))

    assert 'badge-success align-middle">Open<' in open_page.content.decode()
    assert 'badge-error align-middle">Closed<' in closed_page.content.decode()


def test_create_saves_every_field_and_redirects_to_the_board(client, recruiter):
    client.force_login(recruiter)

    response = client.post(
        reverse("ats:job_create"),
        job_data(
            department="Support",
            location="Remote",
            description="Help our customers.",
        ),
    )

    job = JobOpening.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("ats:job_detail", args=[job.pk])
    assert job.title == "Support Engineer"
    assert job.department == "Support"
    assert job.location == "Remote"
    assert job.description == "Help our customers."


def test_department_location_and_description_are_optional(client, recruiter):
    client.force_login(recruiter)

    response = client.post(reverse("ats:job_create"), job_data())

    assert response.status_code == 302
    assert JobOpening.objects.get().department == ""


def test_edit_form_shows_the_current_values_and_saves_changes(client, recruiter, job):
    url = reverse("ats:job_edit", args=[job.pk])
    client.force_login(recruiter)

    assert 'value="Backend Engineer"' in client.get(url).content.decode()

    response = client.post(url, job_data(title="Staff Engineer"))

    assert response.status_code == 302
    assert response.url == reverse("ats:job_detail", args=[job.pk])
    job.refresh_from_db()
    assert job.title == "Staff Engineer"


def test_edit_keeps_the_creator_and_status_despite_a_forged_post(
    client, recruiter, manager, job
):
    client.force_login(recruiter)

    client.post(
        reverse("ats:job_edit", args=[job.pk]),
        job_data(status=JobOpening.Status.CLOSED, created_by=recruiter.pk),
    )

    job.refresh_from_db()
    assert job.title == "Support Engineer"
    assert job.created_by == manager
    assert job.status == JobOpening.Status.OPEN


def test_blank_title_renders_the_error_and_saves_nothing(client, recruiter):
    client.force_login(recruiter)

    response = client.post(reverse("ats:job_create"), job_data(title=""))

    assert response.status_code == 200
    assert "This field is required." in response.content.decode()
    assert not JobOpening.objects.exists()


def test_save_job_refuses_a_blank_title(recruiter):
    with pytest.raises(ValidationError):
        services.save_job(recruiter, JobOpening(title=""))

    assert not JobOpening.objects.exists()


def test_edit_returns_404_for_a_missing_job(client, recruiter):
    client.force_login(recruiter)

    assert client.get(reverse("ats:job_edit", args=[999])).status_code == 404


@pytest.mark.parametrize("fixture", ["recruiter", "manager", "dual_role_user"])
def test_every_role_can_create_and_edit(client, request, job, fixture):
    client.force_login(request.getfixturevalue(fixture))

    assert client.get(reverse("ats:job_create")).status_code == 200
    created = client.post(reverse("ats:job_create"), job_data())
    edited = client.post(reverse("ats:job_edit", args=[job.pk]), job_data())

    assert created.status_code == 302
    assert edited.status_code == 302


@pytest.mark.parametrize("method", ["get", "post"])
def test_account_with_no_role_cannot_create_or_edit(client, job, method):
    client.force_login(make_user("no-role"))
    send = getattr(client, method)

    created = send(reverse("ats:job_create"), job_data())
    edited = send(reverse("ats:job_edit", args=[job.pk]), job_data())

    assert created.status_code == 403
    assert edited.status_code == 403
    job.refresh_from_db()
    assert JobOpening.objects.count() == 1
    assert job.title == "Backend Engineer"


def test_create_and_edit_links_are_hidden_from_an_account_with_no_role(client, job):
    client.force_login(make_user("no-role"))

    home = client.get(reverse("ats:home")).content.decode()
    detail = client.get(reverse("ats:job_detail", args=[job.pk])).content.decode()

    assert reverse("ats:job_create") not in home
    assert reverse("ats:job_edit", args=[job.pk]) not in detail


def test_create_and_edit_links_are_shown_to_a_recruiter(client, recruiter, job):
    client.force_login(recruiter)

    home = client.get(reverse("ats:home")).content.decode()
    detail = client.get(reverse("ats:job_detail", args=[job.pk])).content.decode()

    assert reverse("ats:job_create") in home
    assert reverse("ats:job_edit", args=[job.pk]) in detail


@pytest.mark.parametrize(
    "url_name, args", [("ats:job_create", []), ("ats:job_edit", [1])]
)
def test_job_forms_redirect_anonymous_visitors_to_login(client, db, url_name, args):
    url = reverse(url_name, args=args)

    response = client.get(url)

    assert response.status_code == 302
    assert response.url == f"{reverse('ats:login')}?next={url}"
