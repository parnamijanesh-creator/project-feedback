"""Views for managing Projects and Team Memberships."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, ListView

from .forms import AddProjectMemberForm, ProjectForm, UpdateMemberRoleForm
from .models import Project, ProjectMember


class ProjectListView(LoginRequiredMixin, ListView):
    """Lists all projects where the current user is an active member."""

    template_name = "projects/project_list.html"
    context_object_name = "memberships"

    def get_queryset(self):
        return (
            ProjectMember.objects.filter(user=self.request.user)
            .select_related("project", "project__created_by")
            .order_by("-project__created_at")
        )


class ProjectCreateView(LoginRequiredMixin, CreateView):
    """Creates a new project and automatically assigns creator as FACILITATOR."""

    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"

    def form_valid(self, form):
        with transaction.atomic():
            project = form.save(commit=False)
            project.created_by = self.request.user
            project.save()

            ProjectMember.objects.create(
                project=project,
                user=self.request.user,
                role=ProjectMember.Role.FACILITATOR,
            )

        messages.success(self.request, f"Project '{project.name}' created successfully!")
        return redirect("project_detail", slug=project.slug)


class ProjectDetailView(LoginRequiredMixin, View):
    """Displays project overview, member roster, and handles member additions."""

    def get_project_and_membership(self, request, slug):
        project = get_object_or_404(Project, slug=slug)
        membership = ProjectMember.objects.filter(project=project, user=request.user).first()
        if not membership:
            raise PermissionDenied("You are not a member of this project.")
        return project, membership

    def get(self, request, slug):
        project, membership = self.get_project_and_membership(request, slug)
        is_facilitator = membership.role == ProjectMember.Role.FACILITATOR

        members = project.members.select_related("user").all()
        cycles = project.cycles.select_related("facilitator").all()
        add_member_form = AddProjectMemberForm(project=project) if is_facilitator else None

        context = {
            "project": project,
            "current_membership": membership,
            "is_facilitator": is_facilitator,
            "members": members,
            "cycles": cycles,
            "add_member_form": add_member_form,
            "role_choices": ProjectMember.Role.choices,
        }
        return render(request, "projects/project_detail.html", context)

    def post(self, request, slug):
        project, membership = self.get_project_and_membership(request, slug)
        if membership.role != ProjectMember.Role.FACILITATOR:
            raise PermissionDenied("Only facilitators can manage project members.")

        form = AddProjectMemberForm(request.POST, project=project)
        if form.is_valid():
            user_to_add = form.cleaned_user
            role = form.cleaned_data.get("role", ProjectMember.Role.MEMBER)

            ProjectMember.objects.create(
                project=project,
                user=user_to_add,
                role=role,
            )
            messages.success(
                request,
                f"Added {user_to_add.username} as {dict(ProjectMember.Role.choices).get(role, role)}.",
            )
            return redirect("project_detail", slug=project.slug)

        members = project.members.select_related("user").all()
        cycles = project.cycles.select_related("facilitator").all()
        context = {
            "project": project,
            "current_membership": membership,
            "is_facilitator": True,
            "members": members,
            "cycles": cycles,
            "add_member_form": form,
            "role_choices": ProjectMember.Role.choices,
        }
        return render(request, "projects/project_detail.html", context)


@login_required
def update_member_role_view(request, slug, member_id):
    """Allows facilitators to update member roles while ensuring >= 1 facilitator exists."""
    if request.method != "POST":
        return redirect("project_detail", slug=slug)

    project = get_object_or_404(Project, slug=slug)
    actor_membership = ProjectMember.objects.filter(project=project, user=request.user).first()
    if not actor_membership or actor_membership.role != ProjectMember.Role.FACILITATOR:
        raise PermissionDenied("Only facilitators can update member roles.")

    target_member = get_object_or_404(ProjectMember, id=member_id, project=project)
    new_role = request.POST.get("role")

    if new_role not in ProjectMember.Role.values:
        messages.error(request, "Invalid role specified.")
        return redirect("project_detail", slug=project.slug)

    # Check constraint: project must retain at least one facilitator
    if target_member.role == ProjectMember.Role.FACILITATOR and new_role != ProjectMember.Role.FACILITATOR:
        facilitator_count = ProjectMember.objects.filter(
            project=project, role=ProjectMember.Role.FACILITATOR
        ).count()
        if facilitator_count <= 1:
            messages.error(request, "A project must retain at least one Facilitator.")
            return redirect("project_detail", slug=project.slug)

    target_member.role = new_role
    target_member.save()
    messages.success(
        request,
        f"Updated role for {target_member.user.username} to {target_member.get_role_display()}.",
    )
    return redirect("project_detail", slug=project.slug)
