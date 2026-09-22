from django.contrib import admin
from .models import FeedbackCard, FeedbackCycle


@admin.register(FeedbackCycle)
class FeedbackCycleAdmin(admin.ModelAdmin):
    list_display = ("project", "week_date", "status", "facilitator", "created_at")
    list_filter = ("status", "project")
    search_fields = ("project__name", "facilitator__username")


@admin.register(FeedbackCard)
class FeedbackCardAdmin(admin.ModelAdmin):
    list_display = ("cycle", "category", "author_display", "is_anonymous", "created_at")
    list_filter = ("category", "is_anonymous", "cycle__project")
    search_fields = ("text", "cycle__project__name")

    @admin.display(description="Author")
    def author_display(self, obj):
        if obj.is_anonymous or not obj.user:
            return "Anonymous"
        return obj.user.username

