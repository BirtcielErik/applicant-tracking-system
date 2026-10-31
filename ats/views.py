from django.contrib.auth.decorators import permission_required
from django.db.models import Count, Max, Q, Value
from django.db.models.functions import Coalesce, Concat
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import CandidateForm, JobForm
from .models import Application, Candidate, JobOpening
from .pipeline import ACTIVE_STAGES, Stage, allowed_targets


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


def candidate_form_response(request, candidate=None):
    data = request.POST if request.method == "POST" else None
    form = CandidateForm(data, instance=candidate)
    if form.is_valid():
        saved = services.save_candidate(form.save(commit=False))
        return redirect("ats:candidate_detail", pk=saved.pk)
    return render(
        request, "ats/candidate_form.html", {"form": form, "candidate": candidate}
    )


def job_form_response(request, job=None):
    data = request.POST if request.method == "POST" else None
    form = JobForm(data, instance=job)
    if form.is_valid():
        saved = services.save_job(request.user, form.save(commit=False))
        return redirect("ats:job_detail", pk=saved.pk)
    return render(request, "ats/job_form.html", {"form": form, "job": job})


def home(request):
    show_closed = request.GET.get("status") == JobOpening.Status.CLOSED
    status = JobOpening.Status.CLOSED if show_closed else JobOpening.Status.OPEN
    jobs = (
        JobOpening.objects.filter(status=status)
        .select_related("created_by")
        .annotate(
            active_applicants=Count(
                "applications", filter=Q(applications__stage__in=ACTIVE_STAGES)
            )
        )
    )
    return render(request, "ats/home.html", {"jobs": jobs, "show_closed": show_closed})


@permission_required("ats.add_jobopening", raise_exception=True)
def job_create(request):
    return job_form_response(request)


def job_detail(request, pk):
    job = get_object_or_404(JobOpening.objects.select_related("created_by"), pk=pk)
    return render(request, "ats/job_detail.html", board_context(job, request.user))


@permission_required("ats.change_jobopening", raise_exception=True)
def job_edit(request, pk):
    return job_form_response(request, get_object_or_404(JobOpening, pk=pk))


def candidate_list(request):
    query = request.GET.get("q", "").strip()
    candidates = Candidate.objects.annotate(
        full_name=Concat("first_name", Value(" "), "last_name")
    ).filter(Q(full_name__icontains=query) | Q(email__icontains=query))
    return render(
        request,
        "ats/candidate_list.html",
        {"candidates": candidates, "query": query},
    )


@permission_required("ats.add_candidate", raise_exception=True)
def candidate_create(request):
    return candidate_form_response(request)


def candidate_detail(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    return render(request, "ats/candidate_detail.html", {"candidate": candidate})


@permission_required("ats.change_candidate", raise_exception=True)
def candidate_edit(request, pk):
    return candidate_form_response(request, get_object_or_404(Candidate, pk=pk))


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
