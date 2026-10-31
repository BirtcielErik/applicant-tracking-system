from django.db import migrations

ROLES = ["Recruiter", "Hiring Manager"]

# Notes are append-only in the app, so neither role can change or delete them.
ACTIONS = ["add", "view"]


def get_permissions(apps):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    # As in 0002: Django creates permissions after all migrations finish, too late
    # to assign them here. The later step finds these rows and leaves them in place.
    content_type, _ = ContentType.objects.get_or_create(
        app_label="ats", model="candidatenote"
    )
    return [
        Permission.objects.get_or_create(
            content_type=content_type,
            codename=f"{action}_candidatenote",
            defaults={"name": f"Can {action} candidate note"},
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
        ("ats", "0007_candidatenote"),
    ]

    operations = [
        migrations.RunPython(grant_permissions, revoke_permissions),
    ]
