"""Admin registration for RetrospectiveSession."""
from django.contrib import admin
from .models import RetrospectiveSession


@admin.register(RetrospectiveSession)
class RetrospectiveSessionAdmin(admin.ModelAdmin):
    list_display = ("cycle", "current_stage", "created_at")
    list_filter = ("current_stage",)
    search_fields = ("cycle__project__name",)
