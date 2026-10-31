import pytest
from django.contrib.auth.models import Group, Permission

MANAGER_ONLY_CODENAMES = {
    "make_offer",
    "confirm_hire",
    "change_offer_or_hire",
    "reopen_application",
    "close_reopen_job",
    "archive_candidate",
    "rename_delete_skill",
}


@pytest.mark.django_db
def test_migrations_create_roles_and_manager_only_permissions():
    assert set(Group.objects.values_list("name", flat=True)) >= {
        "Recruiter",
        "Hiring Manager",
    }
    assert MANAGER_ONLY_CODENAMES <= set(
        Permission.objects.filter(content_type__app_label="ats").values_list(
            "codename", flat=True
        )
    )


def test_recruiter_can_work_with_pipeline_models_but_not_delete(recruiter):
    assert recruiter.has_perms(
        [
            "ats.add_candidate",
            "ats.change_candidate",
            "ats.add_jobopening",
            "ats.change_jobopening",
            "ats.add_application",
            "ats.change_application",
            "ats.view_stagechange",
        ]
    )
    assert not recruiter.has_perm("ats.delete_candidate")
    assert not recruiter.has_perm("ats.change_stagechange")


def test_role_permissions_combine(recruiter, manager, dual_role_user):
    manager_only = {f"ats.{codename}" for codename in MANAGER_ONLY_CODENAMES}
    recruiter_perms = recruiter.get_all_permissions()
    manager_perms = manager.get_all_permissions()

    assert manager_only <= manager_perms
    assert recruiter_perms <= manager_perms
    assert not manager_only & recruiter_perms
    assert dual_role_user.get_all_permissions() == recruiter_perms | manager_perms
