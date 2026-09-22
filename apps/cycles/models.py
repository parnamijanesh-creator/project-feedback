"""Domain models for Feedback Cycles."""
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone


def get_current_week_start():
    """Return Monday of the current calendar week."""
    today = timezone.now().date()
    return today - timedelta(days=today.weekday())


class FeedbackCycle(models.Model):
    """Weekly feedback collection and retrospective cycle within a project."""

    class Status(models.TextChoices):
        COLLECTING = "COLLECTING", "Collecting Feedback"
        RETROSPECTIVE = "RETROSPECTIVE", "Retrospective"
        COMPLETED = "COMPLETED", "Completed"

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="cycles",
    )
    facilitator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="facilitated_cycles",
    )
    week_date = models.DateField(default=get_current_week_start)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COLLECTING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Feedback Cycle"
        verbose_name_plural = "Feedback Cycles"
        ordering = ["-week_date", "-created_at"]

    def __str__(self):
        return f"{self.project.name} - Week of {self.week_date} ({self.get_status_display()})"
