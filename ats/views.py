from django.contrib.auth.decorators import permission_required
from django.db.models import Max
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from . import services
from .models import Application, JobOpening
from .pipeline import Stage, allowed_targets


def board_context(job, user, move_error=None):
    applications = job.applications.select_related("candidate").annotate(
        last_moved_at=Coalesce(Max("stage_changes__changed_at"), "created_at")
    )
    for application in applications:
        application.allowed_stages = " ".join(allowed_targets(user, application))
    columns = [
        {
            "stage": stage,
            "label": label,
            "applications": [a for a in applications if a.stage == stage],
        }
        for stage, label in Stage.choices
    ]
    return {"job": job, "columns": columns, "move_error": move_error}


def home(request):
    return render(request, "ats/home.html")


def job_detail(request, pk):
    job = get_object_or_404(JobOpening, pk=pk)
    return render(request, "ats/job_detail.html", board_context(job, request.user))


@require_POST
@permission_required("ats.change_application", raise_exception=True)
def application_move(request, pk):
    application = get_object_or_404(
        Application.objects.select_related("job", "candidate"), pk=pk
    )
    move_error = None
    try:
        services.move_application(request.user, application, request.POST.get("stage"))
    except services.MoveRefused as refusal:
        move_error = str(refusal)
    return render(
        request,
        "ats/partials/board.html",
        board_context(application.job, request.user, move_error),
    )
