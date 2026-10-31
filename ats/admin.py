from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Application, Candidate, JobOpening, StageChange, User

admin.site.register(User, UserAdmin)


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "email", "lead_source", "is_archived"]
    search_fields = ["first_name", "last_name", "email"]


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ["title", "department", "status", "created_by", "closed_at"]
    list_filter = ["status"]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["candidate", "job", "stage", "application_date"]
    list_filter = ["stage"]


@admin.register(StageChange)
class StageChangeAdmin(admin.ModelAdmin):
    list_display = [
        "application",
        "from_stage",
        "to_stage",
        "changed_by",
        "changed_at",
        "reason",
    ]
    list_filter = ["reason"]
