from django.db import models
from django.contrib.auth.models import User


class Resume(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    resume_file = models.FileField(
        upload_to='resumes/'
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    extracted_text = models.TextField(
        blank=True
    )

    skills = models.TextField(
        blank=True
    )

    summary = models.TextField(
        blank=True
    )

    ats_score = models.IntegerField(
        default=0
    )

    google_score = models.IntegerField(
        default=0
    )

    amazon_score = models.IntegerField(
        default=0
    )

    tcs_score = models.IntegerField(
        default=0
    )

    infosys_score = models.IntegerField(
        default=0
    )

    def __str__(self):

        return self.user.username


class CompanyRequirement(models.Model):

    company_name = models.CharField(
        max_length=100
    )

    required_skills = models.TextField()

    def __str__(self):

        return self.company_name


class JobDescription(models.Model):
    """A job description entered by a user for job-specific matching."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    title = models.CharField(
        max_length=200
    )

    company = models.CharField(
        max_length=200,
        blank=True
    )

    description_text = models.TextField()

    required_skills = models.JSONField(
        default=list,
        blank=True
    )

    preferred_skills = models.JSONField(
        default=list,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return f"{self.title} ({self.user.username})"


class AnalysisResult(models.Model):
    """One saved analysis of one resume (general or job-specific)."""

    MODE_GENERAL = "general"
    MODE_JOB = "job"
    MODE_CHOICES = [
        (MODE_GENERAL, "General analysis"),
        (MODE_JOB, "Job-specific match"),
    ]

    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name="analyses"
    )

    job_description = models.ForeignKey(
        JobDescription,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analyses"
    )

    mode = models.CharField(
        max_length=10,
        choices=MODE_CHOICES,
        default=MODE_GENERAL
    )

    # Checklist score (0-100) defined in services/resume_quality.py
    quality_score = models.IntegerField(
        default=0
    )

    # Machine-readability indicator (0-100), not an employer ATS score
    ats_score = models.IntegerField(
        default=0
    )

    # Only set for job-specific analyses
    job_match_percentage = models.IntegerField(
        null=True,
        blank=True
    )

    matched_skills = models.JSONField(
        default=list,
        blank=True
    )

    missing_skills = models.JSONField(
        default=list,
        blank=True
    )

    # Complete structured report produced by services/analysis.py
    report = models.JSONField(
        default=dict,
        blank=True
    )

    # Hash of the inputs; identical inputs reuse the saved result
    input_hash = models.CharField(
        max_length=64,
        db_index=True
    )

    engine_version = models.CharField(
        max_length=20,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):

        return f"Analysis {self.id} of resume {self.resume_id}"