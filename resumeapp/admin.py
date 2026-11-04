from django.contrib import admin

from .models import (
    Resume,
    CompanyRequirement,
    JobDescription,
    AnalysisResult
)


@admin.register(CompanyRequirement)
class CompanyRequirementAdmin(admin.ModelAdmin):
    # company_name must be exactly Google, Amazon, TCS or Infosys for the
    # "Company keyword match" scores to be calculated on upload.
    list_display = ("company_name",)
    search_fields = ("company_name",)


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "resume_file", "ats_score", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("user__username", "resume_file")
    readonly_fields = ("uploaded_at",)


@admin.register(JobDescription)
class JobDescriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "company", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("title", "company", "user__username")
    readonly_fields = ("created_at",)


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = (
        "id", "resume", "mode", "quality_score", "ats_score",
        "job_match_percentage", "created_at",
    )
    list_filter = ("mode", "created_at")
    readonly_fields = ("created_at", "input_hash", "engine_version")