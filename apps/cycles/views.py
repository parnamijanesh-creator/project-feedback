"""Views for managing Feedback Cycles and phase transitions."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.projects.models import Project, ProjectMember
from .forms import FeedbackCycleCreateForm
from .models import FeedbackCycle


class CycleCreateView(LoginRequiredMixin, View):
    """Initiates a new feedback cycle for a project (Facilitators only)."""

    def get_project_and_facilitator_check(self, request, slug):
        project = get_object_or_404(Project, slug=slug)
        membership = ProjectMember.objects.filter(project=project, user=request.user).first()
        if not membership or membership.role != ProjectMember.Role.FACILITATOR:
            raise PermissionDenied("Only project facilitators can initiate feedback cycles.")
        return project

    def get(self, request, slug):
        project = self.get_project_and_facilitator_check(request, slug)
        form = FeedbackCycleCreateForm(project=project)
        return render(request, "cycles/cycle_form.html", {"project": project, "form": form})

    def post(self, request, slug):
        project = self.get_project_and_facilitator_check(request, slug)
        form = FeedbackCycleCreateForm(request.POST, project=project)
        if form.is_valid():
            cycle = form.save(commit=False)
            cycle.project = project
            cycle.facilitator = request.user
            cycle.status = FeedbackCycle.Status.COLLECTING
            cycle.save()
            messages.success(
                request,
                f"Feedback cycle for week of {cycle.week_date} initiated successfully!",
            )
            return redirect("cycle_detail", slug=project.slug, pk=cycle.pk)

        return render(request, "cycles/cycle_form.html", {"project": project, "form": form})


class CycleDetailView(LoginRequiredMixin, View):
    """Displays cycle overview, status phase, and submissions placeholder."""

    def get(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        membership = ProjectMember.objects.filter(project=project, user=request.user).first()
        if not membership:
            raise PermissionDenied("You are not a member of this project.")

        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        is_facilitator = membership.role == ProjectMember.Role.FACILITATOR

        context = {
            "project": project,
            "cycle": cycle,
            "is_facilitator": is_facilitator,
            "status_choices": FeedbackCycle.Status.choices,
        }
        return render(request, "cycles/cycle_detail.html", context)


class CycleStatusTransitionView(LoginRequiredMixin, View):
    """Transitions a cycle status across phases (COLLECTING -> RETROSPECTIVE -> COMPLETED)."""

    def post(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        membership = ProjectMember.objects.filter(project=project, user=request.user).first()
        if not membership or membership.role != ProjectMember.Role.FACILITATOR:
            raise PermissionDenied("Only project facilitators can transition cycle statuses.")

        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        new_status = request.POST.get("status")

        if new_status not in FeedbackCycle.Status.values:
            messages.error(request, "Invalid cycle status requested.")
            return redirect("cycle_detail", slug=slug, pk=pk)

        cycle.status = new_status
        cycle.save()
        messages.success(request, f"Cycle status updated to '{cycle.get_status_display()}'.")
        return redirect("cycle_detail", slug=slug, pk=pk)
