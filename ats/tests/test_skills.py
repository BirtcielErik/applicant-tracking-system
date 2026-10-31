import re

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from ats import services
from ats.models import JobOpening, Skill
from ats.tests.conftest import make_user


def job_data(**overrides):
    return {"title": "Support Engineer", **overrides}


def ticked_skill_names(html):
    pks = re.findall(r'<input[^>]*name="skills" value="(\d+)"[^>]*checked', html)
    return set(Skill.objects.filter(pk__in=pks).values_list("name", flat=True))


def test_adding_an_existing_name_in_another_case_reuses_the_skill(db):
    existing = Skill.objects.create(name="Python")

    skill = services.get_or_create_skill("python")

    assert skill == existing
    assert Skill.objects.count() == 1


def test_rename_allows_a_case_change_but_refuses_another_skills_name(db):
    python = Skill.objects.create(name="python")
    java = Skill.objects.create(name="Java")

    services.rename_skill(python, "PYTHON")
    with pytest.raises(ValidationError):
        services.rename_skill(java, "python")

    python.refresh_from_db()
    java.refresh_from_db()
    assert python.name == "PYTHON"
    assert java.name == "Java"


def test_inline_add_keeps_the_ticked_skills_and_ticks_the_new_one(client, recruiter):
    ticked = Skill.objects.create(name="Python")
    Skill.objects.create(name="Go")
    client.force_login(recruiter)

    response = client.post(
        reverse("ats:skill_add"), {"skills": [ticked.pk], "new_skill": "Django"}
    )

    content = response.content.decode()
    assert ticked_skill_names(content) == {"Python", "Django"}
    assert 'name="title"' not in content


def test_database_refuses_a_case_variant_of_an_existing_skill(db):
    Skill.objects.create(name="Python")

    with pytest.raises(IntegrityError), transaction.atomic():
        Skill.objects.create(name="PYTHON")


def test_adding_a_new_skill_trims_the_name_and_reuses_it_when_it_exists(db):
    created = services.get_or_create_skill("  Python ")

    assert created.name == "Python"
    assert services.get_or_create_skill(" python") == created


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_adding_an_invalid_name_is_refused(db, name):
    with pytest.raises(ValidationError):
        services.get_or_create_skill(name)

    assert not Skill.objects.exists()


def test_inline_add_of_an_existing_name_ticks_the_existing_skill(client, recruiter):
    Skill.objects.create(name="Python")
    client.force_login(recruiter)

    response = client.post(reverse("ats:skill_add"), {"new_skill": "python"})

    assert ticked_skill_names(response.content.decode()) == {"Python"}
    assert Skill.objects.count() == 1


def test_inline_add_of_a_blank_name_shows_the_error_and_keeps_the_ticks(
    client, recruiter
):
    ticked = Skill.objects.create(name="Python")
    client.force_login(recruiter)

    response = client.post(
        reverse("ats:skill_add"), {"skills": [ticked.pk], "new_skill": "  "}
    )

    content = response.content.decode()
    assert "This field cannot be blank." in content
    assert ticked_skill_names(content) == {"Python"}
    assert Skill.objects.count() == 1


def test_inline_add_requires_the_add_skill_permission(client, db):
    client.force_login(make_user("no-role"))

    response = client.post(reverse("ats:skill_add"), {"new_skill": "Python"})

    assert response.status_code == 403
    assert not Skill.objects.exists()


def test_inline_add_refuses_get(client, recruiter):
    client.force_login(recruiter)

    assert client.get(reverse("ats:skill_add")).status_code == 405


def test_job_form_includes_the_picker_and_htmx(client, recruiter):
    Skill.objects.create(name="Python")
    client.force_login(recruiter)

    content = client.get(reverse("ats:job_create")).content.decode()

    assert 'name="skills"' in content
    assert f'hx-post="{reverse("ats:skill_add")}"' in content
    assert "ats/js/htmx.min.js" in content


def test_create_tags_the_job_with_the_ticked_skills(client, recruiter):
    python = Skill.objects.create(name="Python")
    Skill.objects.create(name="Go")
    client.force_login(recruiter)

    client.post(reverse("ats:job_create"), job_data(skills=[python.pk]))

    assert list(JobOpening.objects.get().skills.all()) == [python]


def test_edit_shows_the_current_skills_and_replaces_them(client, recruiter, job):
    python = Skill.objects.create(name="Python")
    go = Skill.objects.create(name="Go")
    job.skills.add(python)
    url = reverse("ats:job_edit", args=[job.pk])
    client.force_login(recruiter)

    assert ticked_skill_names(client.get(url).content.decode()) == {"Python"}

    client.post(url, job_data(skills=[go.pk]))

    assert list(job.skills.all()) == [go]


def test_validation_error_keeps_the_ticked_skills(client, recruiter):
    python = Skill.objects.create(name="Python")
    client.force_login(recruiter)

    response = client.post(
        reverse("ats:job_create"), job_data(title="", skills=[python.pk])
    )

    assert ticked_skill_names(response.content.decode()) == {"Python"}
    assert not JobOpening.objects.exists()


def test_unknown_skill_in_a_forged_post_renders_the_error(client, recruiter):
    client.force_login(recruiter)

    response = client.post(reverse("ats:job_create"), job_data(skills=[999]))

    assert "is not one of the available choices" in response.content.decode()
    assert not JobOpening.objects.exists()


def test_job_detail_shows_the_jobs_skills(client, recruiter, job):
    job.skills.add(Skill.objects.create(name="Python"))
    Skill.objects.create(name="Unrelated")
    client.force_login(recruiter)

    content = client.get(reverse("ats:job_detail", args=[job.pk])).content.decode()

    assert '<span class="badge badge-outline">Python</span>' in content
    assert "Unrelated" not in content


def test_skill_list_shows_names_and_job_counts(client, recruiter, job):
    job.skills.add(Skill.objects.create(name="Python"))
    Skill.objects.create(name="Go")
    client.force_login(recruiter)

    skills = client.get(reverse("ats:skill_list")).context["skills"]

    assert {skill.name: skill.job_count for skill in skills} == {"Python": 1, "Go": 0}


def test_rename_and_delete_are_hidden_from_a_recruiter(client, recruiter):
    skill = Skill.objects.create(name="Python")
    client.force_login(recruiter)

    content = client.get(reverse("ats:skill_list")).content.decode()

    assert "Python" in content
    assert reverse("ats:skill_rename", args=[skill.pk]) not in content
    assert reverse("ats:skill_delete", args=[skill.pk]) not in content


@pytest.mark.parametrize("fixture", ["manager", "dual_role_user"])
def test_rename_and_delete_are_shown_to_a_manager(client, db, request, fixture):
    skill = Skill.objects.create(name="Python")
    client.force_login(request.getfixturevalue(fixture))

    content = client.get(reverse("ats:skill_list")).content.decode()

    assert reverse("ats:skill_rename", args=[skill.pk]) in content
    assert reverse("ats:skill_delete", args=[skill.pk]) in content


def test_recruiter_cannot_rename_or_delete_a_skill(client, recruiter):
    skill = Skill.objects.create(name="Python")
    client.force_login(recruiter)

    renamed = client.post(
        reverse("ats:skill_rename", args=[skill.pk]), {"name": "Forged"}
    )
    deleted = client.post(reverse("ats:skill_delete", args=[skill.pk]))

    assert renamed.status_code == 403
    assert deleted.status_code == 403
    skill.refresh_from_db()
    assert skill.name == "Python"


def test_manager_rename_is_reflected_on_affected_jobs(client, manager, job):
    skill = Skill.objects.create(name="Pyhton")
    job.skills.add(skill)
    client.force_login(manager)

    response = client.post(
        reverse("ats:skill_rename", args=[skill.pk]), {"name": " Python "}
    )

    assert response.url == reverse("ats:skill_list")
    client.get(response.url)
    detail = client.get(reverse("ats:job_detail", args=[job.pk])).content.decode()
    assert ">Python</span>" in detail
    assert "Pyhton" not in detail


def test_successful_rename_shows_a_confirmation_once(client, manager):
    skill = Skill.objects.create(name="Pyhton")
    client.force_login(manager)
    url = reverse("ats:skill_rename", args=[skill.pk])

    response = client.post(url, {"name": "Python"}, follow=True)

    assert "Renamed Pyhton to Python." in response.content.decode()
    reloaded = client.get(reverse("ats:skill_list")).content.decode()
    assert "alert-success" not in reloaded


def test_rename_to_the_same_name_shows_no_confirmation(client, manager):
    skill = Skill.objects.create(name="Python")
    client.force_login(manager)
    url = reverse("ats:skill_rename", args=[skill.pk])

    response = client.post(url, {"name": "Python"}, follow=True)

    assert "alert-success" not in response.content.decode()


def test_refused_rename_shows_no_confirmation(client, manager):
    Skill.objects.create(name="Python")
    java = Skill.objects.create(name="Java")
    client.force_login(manager)
    url = reverse("ats:skill_rename", args=[java.pk])

    response = client.post(url, {"name": "PYTHON"}, follow=True)

    assert "alert-success" not in response.content.decode()


def test_manager_delete_removes_the_skill_from_jobs_but_keeps_them(
    client, manager, job
):
    skill = Skill.objects.create(name="Python")
    job.skills.add(skill)
    client.force_login(manager)

    client.post(reverse("ats:skill_delete", args=[skill.pk]))

    assert not Skill.objects.exists()
    assert JobOpening.objects.filter(pk=job.pk).exists()


def test_refused_rename_shows_the_error_and_the_stored_names(client, manager):
    Skill.objects.create(name="Python")
    java = Skill.objects.create(name="Java")
    client.force_login(manager)

    response = client.post(
        reverse("ats:skill_rename", args=[java.pk]), {"name": "PYTHON"}
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "A skill with this name already exists." in content
    assert 'value="Java"' in content
    assert 'value="PYTHON"' not in content


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_rename_is_refused(client, manager, name):
    skill = Skill.objects.create(name="Python")
    client.force_login(manager)

    response = client.post(reverse("ats:skill_rename", args=[skill.pk]), {"name": name})

    assert "This field cannot be blank." in response.content.decode()
    skill.refresh_from_db()
    assert skill.name == "Python"


@pytest.mark.parametrize("url_name", ["ats:skill_rename", "ats:skill_delete"])
def test_rename_and_delete_return_404_for_a_missing_skill(client, manager, url_name):
    client.force_login(manager)

    assert client.post(reverse(url_name, args=[999])).status_code == 404


@pytest.mark.parametrize("url_name", ["ats:skill_rename", "ats:skill_delete"])
def test_rename_and_delete_refuse_get(client, manager, url_name):
    skill = Skill.objects.create(name="Python")
    client.force_login(manager)

    assert client.get(reverse(url_name, args=[skill.pk])).status_code == 405
    assert Skill.objects.exists()


def test_skill_list_redirects_anonymous_visitors_to_login(client, db):
    url = reverse("ats:skill_list")

    response = client.get(url)

    assert response.status_code == 302
    assert response.url == f"{reverse('ats:login')}?next={url}"
