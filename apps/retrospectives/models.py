"""Domain models for Interactive Retrospective Sessions."""
from django.db import models


class RetrospectiveSession(models.Model):
    """Real-time retrospective meeting session for an active feedback cycle."""

    class Stage(models.TextChoices):
        REVEAL = "REVEAL", "Reveal"
        CLUSTER = "CLUSTER", "Cluster"
        VOTE = "VOTE", "Vote"
        DISCUSS = "DISCUSS", "Discuss"
        SUMMARY = "SUMMARY", "Summary"

    cycle = models.OneToOneField(
        "cycles.FeedbackCycle",
        on_delete=models.CASCADE,
        related_name="retro_session",
    )
    current_stage = models.CharField(
        max_length=20,
        choices=Stage.choices,
        default=Stage.REVEAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Retrospective Session"
        verbose_name_plural = "Retrospective Sessions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Retro for {self.cycle.project.name} (Week of {self.cycle.week_date}) - {self.get_current_stage_display()}"
