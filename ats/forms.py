from django import forms
from django.urls import reverse
from django.utils.html import format_html

from .models import Candidate


class CandidateForm(forms.ModelForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            is_select = isinstance(field.widget, forms.Select)
            field.widget.attrs["class"] = f"{'select' if is_select else 'input'} w-full"

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
