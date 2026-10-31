from django.db import migrations

ROLES = ["Recruiter", "Hiring Manager"]

MODEL_PERMISSIONS = [
    ("candidate", "candidate", ["add", "change", "view"]),
    ("jobopening", "job opening", ["add", "change", "view"]),
    ("application", "application", ["add", "change", "view"]),
    ("stagechange", "stage change", ["view"]),
]


def get_permissions(apps):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    # As in 0002: Django creates permissions after all migrations finish, too late
    # to assign them here. The later step finds these rows and leaves them in place.
    permissions = []
    for model, verbose_name, actions in MODEL_PERMISSIONS:
        content_type, _ = ContentType.objects.get_or_create(
            app_label="ats", model=model
        )
        for action in actions:
            permission, _ = Permission.objects.get_or_create(
                content_type=content_type,
                codename=f"{action}_{model}",
                defaults={"name": f"Can {action} {verbose_name}"},
            )
            permissions.append(permission)
    return permissions


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
        ("ats", "0003_pipeline_models"),
    ]

    operations = [
        migrations.RunPython(grant_permissions, revoke_permissions),
    ]
