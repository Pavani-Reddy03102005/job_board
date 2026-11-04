import os

from django import forms
from django.core.exceptions import ValidationError

from .models import Resume

MAX_UPLOAD_BYTES = 5 * 1024 * 1024      # 5 MB, as promised on the upload page
ALLOWED_EXTENSIONS = (".pdf", ".docx")
MIN_JD_WORDS = 30


class ResumeForm(forms.ModelForm):

    class Meta:

        model = Resume

        fields = ['resume_file']

    def clean_resume_file(self):

        upload = self.cleaned_data.get('resume_file')

        if not upload:
            raise ValidationError("Please choose a file to upload.")

        ext = os.path.splitext(upload.name)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                "Only PDF (.pdf) and Word (.docx) files are supported."
            )

        if upload.size > MAX_UPLOAD_BYTES:
            raise ValidationError("The file is too large. The maximum size is 5 MB.")

        if upload.size == 0:
            raise ValidationError("The file is empty.")

        # Check the real file signature, not just the extension
        upload.seek(0)
        head = upload.read(1024)
        upload.seek(0)

        if ext == ".pdf" and b"%PDF-" not in head:
            raise ValidationError("This file is not a valid PDF.")

        if ext == ".docx" and not head.startswith(b"PK"):
            raise ValidationError("This file is not a valid Word (.docx) document.")

        return upload


class AnalysisForm(forms.Form):

    MODE_CHOICES = [
        ("general", "General resume analysis"),
        ("job", "Job-specific matching"),
    ]

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        widget=forms.RadioSelect,
        initial="general"
    )

    job_title = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Python Developer"
        })
    )

    company = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Optional"
        })
    )

    job_description = forms.CharField(
        max_length=15000,
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 10,
            "placeholder": "Paste the complete job description here"
        })
    )

    def clean(self):

        data = super().clean()

        if data.get("mode") == "job":

            if not (data.get("job_title") or "").strip():
                self.add_error("job_title", "Enter the job title.")

            jd = (data.get("job_description") or "").strip()

            if len(jd.split()) < MIN_JD_WORDS:
                self.add_error(
                    "job_description",
                    "Paste the full job description (at least %d words) so the "
                    "comparison is meaningful." % MIN_JD_WORDS
                )

        return data