from django import forms
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Candidate, JobOpening


class DaisyFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs["class"] = "checkbox checkbox-sm"
                continue
            if isinstance(field.widget, forms.Select):
                css_class = "select"
            elif isinstance(field.widget, forms.Textarea):
                css_class = "textarea"
            else:
                css_class = "input"
            field.widget.attrs["class"] = f"{css_class} w-full"


class CandidateForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = Candidate
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "lead_source",
            "lead_source_detail",
        ]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        existing = (
            Candidate.objects.filter(email=email).exclude(pk=self.instance.pk).first()
        )
        if existing:
            raise forms.ValidationError(
                format_html(
                    "A candidate with this email already exists: "
                    '<a class="link" href="{}">{}</a>',
                    reverse("ats:candidate_detail", args=[existing.pk]),
                    existing,
                )
            )
        return email


class JobForm(DaisyFormMixin, forms.ModelForm):
    class Meta:
        model = JobOpening
        fields = ["title", "department", "location", "description", "skills"]
        widgets = {"skills": forms.CheckboxSelectMultiple}


class CandidateChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj} ({obj.email})"


class ApplicationForm(DaisyFormMixin, forms.Form):
    application_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )


class AddApplicantForm(ApplicationForm):
    # Both forms validate against every record and only offer the valid ones, so a
    # stale or hand-crafted choice reaches the service and gets its refusal.
    candidate = CandidateChoiceField(
        queryset=Candidate.objects.all(), widget=forms.HiddenInput
    )

    field_order = ["candidate", "application_date"]

    def __init__(self, *args, job, query="", **kwargs):
        super().__init__(*args, **kwargs)
        self.available_candidates = Candidate.objects.available_for(job).search(query)

    @property
    def selected_label(self):
        candidate = getattr(self, "cleaned_data", {}).get("candidate")
        if candidate is None:
            return ""
        return self.fields["candidate"].label_from_instance(candidate)


class ApplyToJobForm(ApplicationForm):
    job = forms.ModelChoiceField(queryset=JobOpening.objects.all())

    field_order = ["job", "application_date"]

    def __init__(self, *args, candidate, **kwargs):
        super().__init__(*args, **kwargs)
        available = JobOpening.objects.available_for(candidate)
        self.fields["job"].choices = [
            ("", self.fields["job"].empty_label),
            *((job.pk, str(job)) for job in available),
        ]
