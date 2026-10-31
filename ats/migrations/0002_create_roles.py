from django.db import migrations

ROLES = ["Recruiter", "Hiring Manager"]

MANAGER_ONLY_PERMISSIONS = [
    ("make_offer", "Can make an offer"),
    ("confirm_hire", "Can confirm a hire"),
    ("change_offer_or_hire", "Can change an offer or hire"),
    ("reopen_application", "Can reopen an application"),
    ("close_reopen_job", "Can close and reopen a job"),
    ("archive_candidate", "Can archive and unarchive a candidate"),
    ("rename_delete_skill", "Can rename and delete a skill"),
]


def create_roles(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for name in ROLES:
        Group.objects.get_or_create(name=name)

    # Django creates permissions after all migrations finish, too late to assign
    # them here. The later step finds these rows and leaves them in place.
    content_type, _ = ContentType.objects.get_or_create(app_label="ats", model="user")
    permissions = [
        Permission.objects.get_or_create(
            content_type=content_type, codename=codename, defaults={"name": name}
        )[0]
        for codename, name in MANAGER_ONLY_PERMISSIONS
    ]
    Group.objects.get(name="Hiring Manager").permissions.add(*permissions)


def delete_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ats", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_roles, delete_roles),
    ]
