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