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


class FeedbackCard(models.Model):
    """Start, Stop, or Continue feedback entry with decoupled database-level anonymity."""

    class Category(models.TextChoices):
        START = "START", "Start"
        STOP = "STOP", "Stop"
        CONTINUE = "CONTINUE", "Continue"

    cycle = models.ForeignKey(
        FeedbackCycle,
        on_delete=models.CASCADE,
        related_name="cards",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cards",
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
    )
    text = models.TextField()
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Feedback Card"
        verbose_name_plural = "Feedback Cards"
        ordering = ["created_at"]

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if not self.text or not self.text.strip():
            raise ValidationError(
                {"text": "Feedback card text cannot be blank or whitespace only."}
            )
        if self.category not in self.Category.values:
            raise ValidationError(
                {"category": f"Invalid category '{self.category}'. Must be one of {self.Category.values}."}
            )
        if self.is_anonymous:
            self.user = None

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_anonymous:
            self.user = None
        super().save(*args, **kwargs)

    def __str__(self):
        author = "Anonymous" if self.is_anonymous or not self.user else self.user.username
        return f"[{self.get_category_display()}] {self.text[:30]} ({author})"

