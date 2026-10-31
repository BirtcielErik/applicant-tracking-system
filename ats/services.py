from django.db import transaction

from .models import StageChange
from .pipeline import can_transition


class MoveRefused(Exception):
    pass


@transaction.atomic
def move_application(user, application, target):
    if not can_transition(user, application, target):
        raise MoveRefused
    from_stage = application.stage
    application.stage = target
    application.save(update_fields=["stage"])
    StageChange.objects.create(
        application=application,
        from_stage=from_stage,
        to_stage=target,
        changed_by=user,
        reason=StageChange.Reason.NORMAL_MOVE,
    )
