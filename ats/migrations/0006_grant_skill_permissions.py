from django.db import migrations

ROLES = ["Recruiter", "Hiring Manager"]

# Renaming and deleting go through the manager-only rename_delete_skill permission.
ACTIONS = ["add", "view"]


def get_permissions(apps):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    # As in 0002: Django creates permissions after all migrations finish, too late
    # to assign them here. The later step finds these rows and leaves them in place.
    content_type, _ = ContentType.objects.get_or_create(app_label="ats", model="skill")
    return [
        Permission.objects.get_or_create(
            content_type=content_type,
            codename=f"{action}_skill",
            defaults={"name": f"Can {action} skill"},
        )[0]
        for action in ACTIONS
    ]


def grant_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    permissions = get_permissions(apps)
    for group in Group.objects.filter(name__in=ROLES):
        group.permissions.add(*permissions)


def revoke_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    permissions = get_permissions(apps)
    for group in Group.objects.filter(name__in=ROLES):
        group.permissions.remove(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("ats", "0005_skill_jobopening_skills"),
    ]

    operations = [
        migrations.RunPython(grant_permissions, revoke_permissions),
    ]
