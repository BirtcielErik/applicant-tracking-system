from django import forms
from django.urls import reverse
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
