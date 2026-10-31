from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from . import services
from .models import Application, JobOpening
from .pipeline import Stage


def board_context(job, move_error=None):
    applications = job.applications.select_related("candidate")
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
    return render(request, "ats/job_detail.html", board_context(job))


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
        board_context(application.job, move_error),
    )
