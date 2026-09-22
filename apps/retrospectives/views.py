"""Views for managing Retrospective Sessions and Card Reveal."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.cycles.models import FeedbackCard, FeedbackCycle
from apps.projects.models import Project, ProjectMember
from .models import RetrospectiveSession


class RetroBoardView(LoginRequiredMixin, View):
    """Main retrospective board view for revealing cards and progressing meeting stages."""

    def get(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        membership = ProjectMember.objects.filter(project=project, user=request.user).first()
        if not membership:
            raise PermissionDenied("You are not a member of this project.")

        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        is_facilitator = membership.role == ProjectMember.Role.FACILITATOR
        retro_session = getattr(cycle, "retro_session", None)

        start_cards = []
        stop_cards = []
        continue_cards = []

        if retro_session:
            # Cards are revealed! Query all submitted cards across the cycle
            all_cards = cycle.cards.select_related("user").all()
            start_cards = all_cards.filter(category=FeedbackCard.Category.START)
            stop_cards = all_cards.filter(category=FeedbackCard.Category.STOP)
            continue_cards = all_cards.filter(category=FeedbackCard.Category.CONTINUE)

        context = {
            "project": project,
            "cycle": cycle,
            "retro_session": retro_session,
            "is_facilitator": is_facilitator,
            "start_cards": start_cards,
            "stop_cards": stop_cards,
            "continue_cards": continue_cards,
        }
        return render(request, "retrospectives/board.html", context)


class RetroRevealView(LoginRequiredMixin, View):
    """Triggers the Reveal Cards stage, transitioning cycle to RETROSPECTIVE and creating session."""

    def post(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        membership = ProjectMember.objects.filter(project=project, user=request.user).first()
        if not membership or membership.role != ProjectMember.Role.FACILITATOR:
            raise PermissionDenied("Only project facilitators can reveal cards.")

        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)

        # Transition cycle status to RETROSPECTIVE
        cycle.status = FeedbackCycle.Status.RETROSPECTIVE
        cycle.save()

        # Initialize or activate RetrospectiveSession in REVEAL stage
        retro_session, created = RetrospectiveSession.objects.get_or_create(
            cycle=cycle,
            defaults={"current_stage": RetrospectiveSession.Stage.REVEAL},
        )
        if not created and retro_session.current_stage != RetrospectiveSession.Stage.REVEAL:
            retro_session.current_stage = RetrospectiveSession.Stage.REVEAL
            retro_session.save()

        messages.success(request, "Cards revealed! The retrospective session is now in session.")
        return redirect("retro_board", slug=slug, pk=pk)
