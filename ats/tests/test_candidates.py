import re

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from ats import services
from ats.models import Candidate
from ats.tests.conftest import make_candidate, make_user


def candidate_data(**overrides):
    return {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@example.com",
        "phone": "",
        "lead_source": Candidate.LeadSource.JOB_BOARD,
        "lead_source_detail": "",
        **overrides,
    }


@pytest.mark.parametrize(
    "url_name", ["ats:candidate_create", "admin:ats_candidate_add"]
)
def test_mixed_case_email_is_stored_in_lowercase(client, superuser, url_name):
    client.force_login(superuser)

    response = client.post(
        reverse(url_name), candidate_data(email="Jane.Doe@Example.COM")
    )

    assert response.status_code == 302
    assert Candidate.objects.get().email == "jane.doe@example.com"


@pytest.mark.parametrize("email", ["jane.doe@example.com", "JANE.Doe@Example.com"])
def test_duplicate_email_is_refused_with_a_link_to_the_existing_candidate(
    client, recruiter, email
):
    existing = make_candidate()
    client.force_login(recruiter)
    # A crash should fail the status assertion, as a browser would see it.
    client.raise_request_exception = False

    response = client.post(reverse("ats:candidate_create"), candidate_data(email=email))

    assert response.status_code == 200
    assert Candidate.objects.count() == 1
    url = reverse("ats:candidate_detail", args=[existing.pk])
    assert f'<a class="link" href="{url}">' in response.content.decode()


def test_saving_a_candidate_with_their_own_email_is_not_a_duplicate(client, recruiter):
    candidate = make_candidate()
    client.force_login(recruiter)

    response = client.post(
        reverse("ats:candidate_edit", args=[candidate.pk]),
        candidate_data(email="JANE.DOE@example.com", phone="555-0100"),
    )

    assert response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.email == "jane.doe@example.com"
    assert candidate.phone == "555-0100"


@pytest.mark.parametrize("query", ["jane", "DOE", "jane doe", "JANE.DOE@EXAMPLE"])
def test_list_search_finds_candidates_by_name_or_email(client, recruiter, query):
    make_candidate("Jane", "Doe")
    make_candidate("John", "Smith")
    client.force_login(recruiter)

    response = client.get(reverse("ats:candidate_list"), {"q": query})

    content = response.content.decode()
    assert "Jane Doe" in content
    assert "John Smith" not in content


def test_admin_refuses_a_duplicate_email_in_another_case(client, superuser):
    make_candidate()
    client.force_login(superuser)
    client.raise_request_exception = False

    response = client.post(
        reverse("admin:ats_candidate_add"),
        candidate_data(email="JANE.Doe@Example.com"),
    )

    assert response.status_code == 200
    assert Candidate.objects.count() == 1


def test_save_candidate_refuses_a_duplicate_email_in_another_case(db):
    make_candidate()

    with pytest.raises(ValidationError):
        services.save_candidate(
            Candidate(
                first_name="Jane",
                last_name="Twin",
                email="JANE.DOE@example.com",
                lead_source=Candidate.LeadSource.OTHER,
            )
        )

    assert Candidate.objects.count() == 1


def test_save_candidate_refuses_an_invalid_lead_source(db):
    candidate = make_candidate()
    candidate.lead_source = "newspaper"

    with pytest.raises(ValidationError):
        services.save_candidate(candidate)


def test_duplicate_email_error_escapes_the_existing_candidates_name(client, recruiter):
    make_candidate("<script>alert(1)</script>", "Doe")
    client.force_login(recruiter)

    response = client.post(
        reverse("ats:candidate_create"),
        candidate_data(email="<script>alert(1)</script>.doe@example.com"),
    )

    assert "<script>alert(1)" not in response.content.decode()


def test_create_saves_every_field_and_redirects_to_the_candidate(client, recruiter):
    client.force_login(recruiter)

    response = client.post(
        reverse("ats:candidate_create"),
        candidate_data(
            phone="555-0100",
            lead_source=Candidate.LeadSource.REFERRAL,
            lead_source_detail="Referred by Maria Lopez",
        ),
    )

    candidate = Candidate.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("ats:candidate_detail", args=[candidate.pk])
    assert candidate.first_name == "Jane"
    assert candidate.last_name == "Doe"
    assert candidate.email == "jane.doe@example.com"
    assert candidate.phone == "555-0100"
    assert candidate.lead_source == Candidate.LeadSource.REFERRAL
    assert candidate.lead_source_detail == "Referred by Maria Lopez"


def test_edit_form_shows_the_current_values_and_saves_changes(client, recruiter):
    candidate = make_candidate()
    url = reverse("ats:candidate_edit", args=[candidate.pk])
    client.force_login(recruiter)

    assert 'value="jane.doe@example.com"' in client.get(url).content.decode()

    response = client.post(
        url, candidate_data(first_name="Janet", email="janet.doe@example.com")
    )

    assert response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.first_name == "Janet"
    assert candidate.email == "janet.doe@example.com"


def test_edit_changing_to_another_candidates_email_is_refused(client, recruiter):
    make_candidate()
    other = make_candidate("John", "Smith")
    client.force_login(recruiter)

    response = client.post(
        reverse("ats:candidate_edit", args=[other.pk]),
        candidate_data(email="JANE.DOE@example.com"),
    )

    assert response.status_code == 200
    other.refresh_from_db()
    assert other.email == "john.smith@example.com"


def test_phone_and_lead_source_detail_are_optional(client, recruiter):
    client.force_login(recruiter)

    response = client.post(reverse("ats:candidate_create"), candidate_data())

    assert response.status_code == 302
    assert Candidate.objects.get().phone == ""


def test_form_marks_only_the_required_fields(client, recruiter):
    client.force_login(recruiter)

    content = client.get(reverse("ats:candidate_create")).content.decode()

    marked = set(re.findall(r'for="id_(\w+)">[^<]*<span[^>]*>\*</span>', content))
    assert marked == {"first_name", "last_name", "email", "lead_source"}


def test_lead_source_offers_exactly_the_four_sources(client, recruiter):
    client.force_login(recruiter)

    response = client.get(reverse("ats:candidate_create"))

    labels = [
        label
        for value, label in response.context["form"].fields["lead_source"].choices
        if value
    ]
    assert labels == ["Company Website", "Job Board", "Referral", "Other"]


@pytest.mark.parametrize(
    "overrides, error",
    [
        ({"first_name": ""}, "This field is required."),
        ({"last_name": ""}, "This field is required."),
        ({"email": ""}, "This field is required."),
        ({"email": "not-an-email"}, "Enter a valid email address."),
        ({"lead_source": ""}, "This field is required."),
        ({"lead_source": "newspaper"}, "Select a valid choice."),
    ],
)
def test_invalid_form_renders_the_error_and_saves_nothing(
    client, recruiter, overrides, error
):
    client.force_login(recruiter)

    response = client.post(reverse("ats:candidate_create"), candidate_data(**overrides))

    assert response.status_code == 200
    assert error in response.content.decode()
    assert not Candidate.objects.exists()


def test_blank_search_lists_every_candidate(client, recruiter):
    make_candidate("Jane", "Doe")
    make_candidate("John", "Smith")
    client.force_login(recruiter)

    content = client.get(reverse("ats:candidate_list"), {"q": "  "}).content.decode()

    assert "Jane Doe" in content
    assert "John Smith" in content


def test_search_with_no_match_says_so_and_keeps_the_query(client, recruiter):
    make_candidate()
    client.force_login(recruiter)

    content = client.get(reverse("ats:candidate_list"), {"q": "zzz"}).content.decode()

    assert "No candidates found." in content
    assert 'value="zzz"' in content


def test_list_links_to_the_candidate(client, recruiter):
    candidate = make_candidate()
    client.force_login(recruiter)

    response = client.get(reverse("ats:candidate_list"))

    url = reverse("ats:candidate_detail", args=[candidate.pk])
    assert f'href="{url}"' in response.content.decode()


def test_navigation_links_to_the_candidates_list(client, recruiter):
    client.force_login(recruiter)

    response = client.get(reverse("ats:home"))

    assert f'href="{reverse("ats:candidate_list")}"' in response.content.decode()


def test_detail_shows_contact_details_and_lead_source(client, recruiter):
    candidate = Candidate.objects.create(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="555-0100",
        lead_source=Candidate.LeadSource.JOB_BOARD,
        lead_source_detail="Indeed",
    )
    client.force_login(recruiter)

    response = client.get(reverse("ats:candidate_detail", args=[candidate.pk]))

    content = response.content.decode()
    for text in ["Jane Doe", "jane.doe@example.com", "555-0100", "Job Board: Indeed"]:
        assert text in content


def test_detail_returns_404_for_a_missing_candidate(client, recruiter):
    client.force_login(recruiter)

    response = client.get(reverse("ats:candidate_detail", args=[999]))

    assert response.status_code == 404


@pytest.mark.parametrize("fixture", ["recruiter", "manager", "dual_role_user"])
def test_every_role_can_create_and_edit(client, db, request, fixture):
    candidate = make_candidate()
    client.force_login(request.getfixturevalue(fixture))

    assert client.get(reverse("ats:candidate_create")).status_code == 200
    created = client.post(
        reverse("ats:candidate_create"), candidate_data(email="new@example.com")
    )
    edited = client.post(
        reverse("ats:candidate_edit", args=[candidate.pk]), candidate_data()
    )

    assert created.status_code == 302
    assert edited.status_code == 302


@pytest.mark.parametrize("method", ["get", "post"])
def test_account_with_no_role_cannot_create_or_edit(client, db, method):
    candidate = make_candidate()
    client.force_login(make_user("no-role"))
    send = getattr(client, method)

    created = send(
        reverse("ats:candidate_create"), candidate_data(email="new@example.com")
    )
    edited = send(
        reverse("ats:candidate_edit", args=[candidate.pk]),
        candidate_data(first_name="Changed"),
    )

    assert created.status_code == 403
    assert edited.status_code == 403
    assert Candidate.objects.count() == 1
    candidate.refresh_from_db()
    assert candidate.first_name == "Jane"


def test_create_and_edit_links_are_hidden_from_an_account_with_no_role(client, db):
    candidate = make_candidate()
    client.force_login(make_user("no-role"))

    list_page = client.get(reverse("ats:candidate_list")).content.decode()
    detail_url = reverse("ats:candidate_detail", args=[candidate.pk])
    detail_page = client.get(detail_url).content.decode()

    assert reverse("ats:candidate_create") not in list_page
    assert reverse("ats:candidate_edit", args=[candidate.pk]) not in detail_page


def test_create_and_edit_links_are_shown_to_a_recruiter(client, recruiter):
    candidate = make_candidate()
    client.force_login(recruiter)

    list_page = client.get(reverse("ats:candidate_list")).content.decode()
    detail_url = reverse("ats:candidate_detail", args=[candidate.pk])
    detail_page = client.get(detail_url).content.decode()

    assert reverse("ats:candidate_create") in list_page
    assert reverse("ats:candidate_edit", args=[candidate.pk]) in detail_page


@pytest.mark.parametrize(
    "url_name, args",
    [
        ("ats:candidate_list", []),
        ("ats:candidate_create", []),
        ("ats:candidate_detail", [1]),
        ("ats:candidate_edit", [1]),
    ],
)
def test_candidate_pages_redirect_anonymous_visitors_to_login(
    client, db, url_name, args
):
    url = reverse(url_name, args=args)

    response = client.get(url)

    assert response.status_code == 302
    assert response.url == f"{reverse('ats:login')}?next={url}"
