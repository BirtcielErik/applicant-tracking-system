from datetime import UTC, datetime

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import dateformat, timezone

from ats import services
from ats.models import CandidateNote, JobOpening, StageChange
from ats.pipeline import Stage
from ats.tests.conftest import make_application, make_candidate, make_user
from ats.urls import urlpatterns


def test_note_cannot_be_tagged_to_another_candidates_application(recruiter, job):
    candidate = make_candidate("Jane", "Doe")
    other_application = make_application(job, candidate=make_candidate("Sam", "Lee"))

    with pytest.raises(ValidationError):
        services.add_note(
            recruiter, candidate, "Great interview", application=other_application
        )

    assert not CandidateNote.objects.exists()


def test_note_post_returns_only_the_new_note_or_the_error(client, recruiter):
    candidate = make_candidate()
    services.add_note(recruiter, candidate, "Earlier note")
    client.force_login(recruiter)
    url = reverse("ats:candidate_note_add", args=[candidate.pk])

    added = client.post(url, {"body": "Prefers remote work"})

    assert added.status_code == 200
    html = added.content.decode()
    assert "Prefers remote work" in html
    assert 'hx-swap-oob="afterbegin:#note-list"' in html
    assert "Earlier note" not in html
    assert "<html" not in html

    refused = client.post(url, {"body": "   "})

    assert refused.status_code == 200
    html = refused.content.decode()
    assert "This field is required." in html
    assert "hx-swap-oob" not in html
    assert "<html" not in html
    assert CandidateNote.objects.count() == 2


def backdate(application, stage, day):
    StageChange.objects.filter(application=application, to_stage=stage).update(
        changed_at=datetime(2026, 1, day, 12, tzinfo=UTC)
    )


def test_stage_history_merges_applications_newest_first(
    client, recruiter, manager, job
):
    candidate = make_candidate()
    other_job = JobOpening.objects.create(title="Data Analyst", created_by=manager)
    today = timezone.localdate()
    backend = services.create_application(recruiter, candidate, job, today)
    analyst = services.create_application(manager, candidate, other_job, today)
    services.move_application(recruiter, backend, Stage.SCREENING)
    services.move_application(manager, analyst, Stage.INTERVIEW)
    backdate(backend, Stage.APPLIED, 10)
    backdate(analyst, Stage.APPLIED, 12)
    backdate(analyst, Stage.INTERVIEW, 13)
    backdate(backend, Stage.SCREENING, 15)
    someone_else = services.create_application(
        recruiter, make_candidate("Sam", "Lee"), job, today
    )
    services.move_application(recruiter, someone_else, Stage.FINAL_REVIEW)
    client.force_login(recruiter)

    response = client.get(reverse("ats:candidate_detail", args=[candidate.pk]))

    rows = response.content.decode().split("<tr data-stage-change")[1:]
    assert len(rows) == 4
    expected = [
        ("Jan 15, 2026", "Backend Engineer", "Screening", "recruiter", "Normal move"),
        ("Jan 13, 2026", "Data Analyst", "Interview", "manager", "Normal move"),
        ("Jan 12, 2026", "Data Analyst", "Applied", "manager", "Application created"),
        (
            "Jan 10, 2026",
            "Backend Engineer",
            "Applied",
            "recruiter",
            "Application created",
        ),
    ]
    for row, details in zip(rows, expected, strict=True):
        for detail in details:
            assert detail in row


def test_add_note_records_author_candidate_tag_and_trimmed_body(recruiter, job):
    application = make_application(job)

    note = services.add_note(
        recruiter, application.candidate, "  Great interview  ", application
    )

    note.refresh_from_db()
    assert note.author == recruiter
    assert note.candidate == application.candidate
    assert note.application == application
    assert note.body == "Great interview"


def test_add_note_tag_is_optional(recruiter):
    note = services.add_note(recruiter, make_candidate(), "Prefers remote work")

    assert note.application is None


@pytest.mark.parametrize("body", ["", "   "])
def test_add_note_refuses_an_empty_body(recruiter, body):
    with pytest.raises(ValidationError):
        services.add_note(recruiter, make_candidate(), body)

    assert not CandidateNote.objects.exists()


def test_note_post_can_tag_the_candidates_own_application(client, recruiter, job):
    application = make_application(job)
    client.force_login(recruiter)

    response = client.post(
        reverse("ats:candidate_note_add", args=[application.candidate.pk]),
        {"body": "Great interview", "application": application.pk},
    )

    assert CandidateNote.objects.get().application == application
    assert "Backend Engineer" in response.content.decode()


def test_hand_crafted_post_cannot_tag_another_candidates_application(
    client, recruiter, job
):
    candidate = make_candidate()
    other_application = make_application(job, candidate=make_candidate("Sam", "Lee"))
    client.force_login(recruiter)

    response = client.post(
        reverse("ats:candidate_note_add", args=[candidate.pk]),
        {"body": "Great interview", "application": other_application.pk},
    )

    assert "Select a valid choice" in response.content.decode()
    assert not CandidateNote.objects.exists()


def test_note_form_offers_only_the_candidates_own_applications(client, recruiter, job):
    application = make_application(job)
    make_application(job, candidate=make_candidate("Sam", "Lee"))
    client.force_login(recruiter)

    response = client.get(
        reverse("ats:candidate_detail", args=[application.candidate.pk])
    )

    assert list(response.context["form"].fields["application"].queryset) == [
        application
    ]


def test_detail_page_shows_notes_newest_first_with_author_time_and_tag(
    client, recruiter, manager, job
):
    application = make_application(job)
    candidate = application.candidate
    older = services.add_note(recruiter, candidate, "Older note")
    newer = services.add_note(recruiter, candidate, "Newer note", application)
    client.force_login(manager)

    html = client.get(reverse("ats:candidate_detail", args=[candidate.pk])).content
    html = html.decode().split('id="note-list"')[1]

    assert html.index("Newer note") < html.index("Older note")
    assert '<span class="badge badge-outline badge-sm">Backend Engineer' in html
    assert "recruiter" in html
    for note in (older, newer):
        created_at = timezone.localtime(note.created_at)
        assert dateformat.format(created_at, "M j, Y g:i A") in html


def test_detail_page_lists_all_applications_with_current_stage(
    client, recruiter, manager, job
):
    candidate = make_candidate()
    other_job = JobOpening.objects.create(title="Data Analyst", created_by=manager)
    make_application(job, Stage.INTERVIEW, candidate)
    make_application(other_job, Stage.REJECTED, candidate)
    client.force_login(recruiter)

    response = client.get(reverse("ats:candidate_detail", args=[candidate.pk]))

    rows = response.content.decode().split("<tr data-application")[1:]
    assert len(rows) == 2
    assert "Backend Engineer" in rows[0]
    assert "Interview" in rows[0]
    assert "Data Analyst" in rows[1]
    assert "Rejected" in rows[1]


def test_note_form_is_hidden_without_permission(client, db):
    candidate = make_candidate()
    client.force_login(make_user("no-role"))

    response = client.get(reverse("ats:candidate_detail", args=[candidate.pk]))

    assert 'id="note-form"' not in response.content.decode()


def test_adding_a_note_is_forbidden_without_permission(client, db):
    candidate = make_candidate()
    client.force_login(make_user("no-role"))

    response = client.post(
        reverse("ats:candidate_note_add", args=[candidate.pk]), {"body": "Hello"}
    )

    assert response.status_code == 403
    assert not CandidateNote.objects.exists()


def test_adding_a_note_requires_login(client, db):
    candidate = make_candidate()

    response = client.post(
        reverse("ats:candidate_note_add", args=[candidate.pk]), {"body": "Hello"}
    )

    assert response.status_code == 302
    assert response.url.startswith(reverse("ats:login"))
    assert not CandidateNote.objects.exists()


def test_note_endpoint_only_accepts_post(client, recruiter):
    candidate = make_candidate()
    client.force_login(recruiter)

    response = client.get(reverse("ats:candidate_note_add", args=[candidate.pk]))

    assert response.status_code == 405


def test_the_only_note_route_adds_a_note():
    note_routes = [
        pattern.name for pattern in urlpatterns if "note" in str(pattern.pattern)
    ]

    assert note_routes == ["candidate_note_add"]


def test_staff_cannot_change_or_delete_notes(recruiter, manager):
    for user in (recruiter, manager):
        assert user.has_perms(["ats.add_candidatenote", "ats.view_candidatenote"])
        assert not user.has_perm("ats.change_candidatenote")
        assert not user.has_perm("ats.delete_candidatenote")
