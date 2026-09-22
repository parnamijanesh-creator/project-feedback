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
        clusters = []

        if retro_session:
            # Cards are revealed! Query all submitted cards across the cycle
            all_cards = cycle.cards.select_related("user", "cluster").all()
            start_cards = all_cards.filter(category=FeedbackCard.Category.START)
            stop_cards = all_cards.filter(category=FeedbackCard.Category.STOP)
            continue_cards = all_cards.filter(category=FeedbackCard.Category.CONTINUE)
            clusters = retro_session.clusters.prefetch_related("cards").all()

        context = {
            "project": project,
            "cycle": cycle,
            "retro_session": retro_session,
            "is_facilitator": is_facilitator,
            "start_cards": start_cards,
            "stop_cards": stop_cards,
            "continue_cards": continue_cards,
            "clusters": clusters,
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


class RetroRunClusteringView(LoginRequiredMixin, View):
    """Triggers AI-assisted clustering of revealed feedback cards."""

    def post(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        membership = ProjectMember.objects.filter(project=project, user=request.user).first()
        if not membership or membership.role != ProjectMember.Role.FACILITATOR:
            raise PermissionDenied("Only project facilitators can run AI clustering.")

        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        retro_session = getattr(cycle, "retro_session", None)
        if not retro_session:
            messages.error(request, "Please reveal cards before running AI clustering.")
            return redirect("retro_board", slug=slug, pk=pk)

        cards_count = cycle.cards.count()
        if cards_count < 2:
            messages.warning(request, "At least 2 cards are required to generate AI clusters.")
            return redirect("retro_board", slug=slug, pk=pk)

        from apps.ai_insights.services.clustering import AIClusteringService

        service = AIClusteringService()
        clusters = service.cluster_session(retro_session)

        if clusters:
            messages.success(
                request,
                f"Generated {len(clusters)} AI thematic cluster{'s' if len(clusters) > 1 else ''}.",
            )
        else:
            messages.error(
                request,
                "AI clustering could not be completed. You can organize clusters manually.",
            )

        return redirect("retro_board", slug=slug, pk=pk)
