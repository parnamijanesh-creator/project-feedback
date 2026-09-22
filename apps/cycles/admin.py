"""Admin registrations for feedback cycles."""
from django.contrib import admin
from .models import FeedbackCycle


@admin.register(FeedbackCycle)
class FeedbackCycleAdmin(admin.ModelAdmin):
    list_display = ("project", "week_date", "status", "facilitator", "created_at")
    list_filter = ("status", "project")
    search_fields = ("project__name", "facilitator__username")
