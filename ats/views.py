from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import AddApplicantForm, ApplyToJobForm, CandidateForm, JobForm
from .models import Application, Candidate, JobOpening, Skill
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
        saved = services.save_job(
            request.user, form.save(commit=False), form.cleaned_data["skills"]
        )
        return redirect("ats:job_detail", pk=saved.pk)
    return render(request, "ats/job_form.html", {"form": form, "job": job})


def submit_application(request, form, candidate, job):
    try:
        services.create_application(
            request.user, candidate, job, form.cleaned_data["application_date"]
        )
    except services.ApplicationRefused as refusal:
        form.add_error(None, str(refusal))
        return False
    return True


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


@permission_required("ats.add_application", raise_exception=True)
def job_application_create(request, pk):
    job = get_object_or_404(JobOpening, pk=pk)
    data = request.POST if request.method == "POST" else None
    form = AddApplicantForm(data, job=job, query=request.GET.get("q", "").strip())
    if form.is_valid():
        candidate = form.cleaned_data["candidate"]
        if submit_application(request, form, candidate, job):
            return redirect("ats:job_detail", pk=job.pk)
    return render(request, "ats/application_form.html", {"form": form, "job": job})


@require_POST
@permission_required("ats.add_skill", raise_exception=True)
def skill_add(request):
    selected = request.POST.getlist("skills")
    skill_error = None
    try:
        skill = services.get_or_create_skill(request.POST.get("new_skill", ""))
        selected.append(skill.pk)
    except ValidationError as error:
        skill_error = " ".join(error.messages)
    form = JobForm(initial={"skills": selected})
    return render(
        request,
        "ats/partials/skill_picker.html",
        {"form": form, "skill_error": skill_error},
    )


def skill_list_response(request, error=None):
    skills = Skill.objects.annotate(job_count=Count("jobs"))
    return render(request, "ats/skill_list.html", {"skills": skills, "error": error})


def skill_list(request):
    return skill_list_response(request)


@require_POST
@permission_required("ats.rename_delete_skill", raise_exception=True)
def skill_rename(request, pk):
    skill = get_object_or_404(Skill, pk=pk)
    old_name = skill.name
    try:
        services.rename_skill(skill, request.POST.get("name", ""))
    except ValidationError as error:
        return skill_list_response(request, " ".join(error.messages))
    if skill.name != old_name:
        messages.success(request, f"Renamed {old_name} to {skill.name}.")
    return redirect("ats:skill_list")


@require_POST
@permission_required("ats.rename_delete_skill", raise_exception=True)
def skill_delete(request, pk):
    services.delete_skill(get_object_or_404(Skill, pk=pk))
    return redirect("ats:skill_list")


def candidate_list(request):
    query = request.GET.get("q", "").strip()
    candidates = Candidate.objects.search(query)
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


@permission_required("ats.add_application", raise_exception=True)
def candidate_application_create(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    data = request.POST if request.method == "POST" else None
    form = ApplyToJobForm(data, candidate=candidate)
    if form.is_valid():
        job = form.cleaned_data["job"]
        if submit_application(request, form, candidate, job):
            messages.success(request, f"Applied {candidate} to {job}.")
            return redirect("ats:candidate_detail", pk=candidate.pk)
    return render(
        request, "ats/application_form.html", {"form": form, "candidate": candidate}
    )


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
