from django.contrib import admin

from .models import (
    Resume,
    CompanyRequirement
)

admin.site.register(Resume)

admin.site.register(CompanyRequirement)