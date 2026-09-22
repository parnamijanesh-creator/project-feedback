"""Domain models for Projects and Team Memberships."""
from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Project(models.Model):
    """Project entity representing a team workspace for feedback cycles."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_projects",
    )

    class Meta:
        verbose_name = "Project"
        verbose_name_plural = "Projects"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Generate unique slug automatically from name if not provided or colliding."""
        if not self.slug:
            base_slug = slugify(self.name) or "project"
            slug_candidate = base_slug
            counter = 1
            # Ensure unique slug across existing projects
            while Project.objects.filter(slug=slug_candidate).exclude(pk=self.pk).exists():
                slug_candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug_candidate
        super().save(*args, **kwargs)


class ProjectMember(models.Model):
    """Associates a User with a Project under a specific role."""

    class Role(models.TextChoices):
        FACILITATOR = "FACILITATOR", "Facilitator"
        MEMBER = "MEMBER", "Member"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Project Member"
        verbose_name_plural = "Project Members"
        unique_together = ("project", "user")
        ordering = ["role", "user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()}) in {self.project.name}"
