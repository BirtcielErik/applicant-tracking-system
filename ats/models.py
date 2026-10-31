from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Meta(AbstractUser.Meta):
        permissions = [
            ("make_offer", "Can make an offer"),
            ("confirm_hire", "Can confirm a hire"),
            ("change_offer_or_hire", "Can change an offer or hire"),
            ("reopen_application", "Can reopen an application"),
            ("close_reopen_job", "Can close and reopen a job"),
            ("archive_candidate", "Can archive and unarchive a candidate"),
            ("rename_delete_skill", "Can rename and delete a skill"),
        ]
