"""Views for managing Retrospective Sessions, Card Reveal, and Cluster Organization."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views import View

from apps.cycles.models import FeedbackCard, FeedbackCycle
from apps.projects.models import Project, ProjectMember
from .models import RetrospectiveSession, TopicCluster


def _check_membership(request, project):
    membership = ProjectMember.objects.filter(project=project, user=request.user).first()
    if not membership:
        raise PermissionDenied("You are not a member of this project.")
    return membership


class RetroBoardView(LoginRequiredMixin, View):
    """Main retrospective board view for revealing cards and progressing meeting stages."""

    def get(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        membership = _check_membership(request, project)

        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        is_facilitator = membership.role == ProjectMember.Role.FACILITATOR
        retro_session = getattr(cycle, "retro_session", None)

        start_cards = []
        stop_cards = []
        continue_cards = []
        clusters = []
        unclustered_cards = []
        active_stage = None

        if retro_session:
            # Query all cards with relations
            all_cards = cycle.cards.select_related("user", "cluster").all()
            start_cards = all_cards.filter(category=FeedbackCard.Category.START)
            stop_cards = all_cards.filter(category=FeedbackCard.Category.STOP)
            continue_cards = all_cards.filter(category=FeedbackCard.Category.CONTINUE)
            clusters = retro_session.clusters.prefetch_related("cards").all()
            unclustered_cards = all_cards.filter(cluster=None)

            # Stage from URL query param override or default to session current_stage
            active_stage = request.GET.get("stage") or retro_session.current_stage

        context = {
            "project": project,
            "cycle": cycle,
            "retro_session": retro_session,
            "is_facilitator": is_facilitator,
            "start_cards": start_cards,
            "stop_cards": stop_cards,
            "continue_cards": continue_cards,
            "clusters": clusters,
            "unclustered_cards": unclustered_cards,
            "active_stage": active_stage,
            "stage_choices": RetrospectiveSession.Stage.choices,
        }
        return render(request, "retrospectives/board.html", context)


class RetroRevealView(LoginRequiredMixin, View):
    """Triggers the Reveal Cards stage, transitioning cycle to RETROSPECTIVE and creating session."""

    def post(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        membership = _check_membership(request, project)
        if membership.role != ProjectMember.Role.FACILITATOR:
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


class RetroStageTransitionView(LoginRequiredMixin, View):
    """Transitions retrospective session stage (e.g. REVEAL -> CLUSTER -> VOTE)."""

    def post(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        membership = _check_membership(request, project)
        if membership.role != ProjectMember.Role.FACILITATOR:
            raise PermissionDenied("Only project facilitators can change retrospective stages.")

        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        retro_session = getattr(cycle, "retro_session", None)
        if not retro_session:
            messages.error(request, "Retrospective session must be started first.")
            return redirect("retro_board", slug=slug, pk=pk)

        new_stage = request.POST.get("stage")
        if new_stage in RetrospectiveSession.Stage.values:
            retro_session.current_stage = new_stage
            retro_session.save(update_fields=["current_stage"])
            messages.success(request, f"Transitioned to {retro_session.get_current_stage_display()} stage.")

        return redirect("retro_board", slug=slug, pk=pk)


class RetroRunClusteringView(LoginRequiredMixin, View):
    """Triggers AI-assisted clustering of revealed feedback cards."""

    def post(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        membership = _check_membership(request, project)
        if membership.role != ProjectMember.Role.FACILITATOR:
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


class ClusterCreateView(LoginRequiredMixin, View):
    """Creates a new topic cluster manually."""

    def post(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        _check_membership(request, project)

        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        if cycle.status == FeedbackCycle.Status.COMPLETED:
            raise PermissionDenied("Retrospective is completed and cannot be modified.")

        retro_session = getattr(cycle, "retro_session", None)
        if not retro_session:
            raise PermissionDenied("Retrospective session does not exist.")

        title = request.POST.get("title", "").strip()
        is_htmx = getattr(request, "htmx", False) or request.headers.get("HX-Request") == "true"

        if not title:
            context = {
                "project": project,
                "cycle": cycle,
                "error": "Cluster title cannot be blank.",
                "csrf_token": get_token(request),
            }
            if is_htmx:
                response = render(request, "retrospectives/partials/cluster_form.html", context, status=422)
                response["HX-Retarget"] = "#new-cluster-container"
                response["HX-Reswap"] = "outerHTML"
                return response
            messages.error(request, "Cluster title cannot be blank.")
            return redirect("retro_board", slug=slug, pk=pk)

        cluster = TopicCluster.objects.create(
            session=retro_session,
            title=title,
            is_ai_generated=False,
        )

        if is_htmx:
            item_html = render_to_string(
                "retrospectives/partials/cluster_item.html",
                {"cluster": cluster, "project": project, "cycle": cycle, "csrf_token": get_token(request)},
                request=request,
            )
            reset_form_html = render_to_string(
                "retrospectives/partials/cluster_form.html",
                {"project": project, "cycle": cycle, "csrf_token": get_token(request)},
                request=request,
            )
            # Render new cluster item and reset the new-cluster form container via OOB
            output = f'{item_html}<div id="new-cluster-container" hx-swap-oob="true">{reset_form_html}</div>'
            return HttpResponse(output)

        messages.success(request, f"Cluster '{cluster.title}' created.")
        return redirect("retro_board", slug=slug, pk=pk)


class ClusterUpdateView(LoginRequiredMixin, View):
    """Inline editing for cluster title."""

    def get(self, request, slug, pk, cluster_id):
        project = get_object_or_404(Project, slug=slug)
        _check_membership(request, project)
        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        retro_session = get_object_or_404(RetrospectiveSession, cycle=cycle)
        cluster = get_object_or_404(TopicCluster, pk=cluster_id, session=retro_session)

        return render(
            request,
            "retrospectives/partials/cluster_title_form.html",
            {"project": project, "cycle": cycle, "cluster": cluster, "csrf_token": get_token(request)},
        )

    def post(self, request, slug, pk, cluster_id):
        project = get_object_or_404(Project, slug=slug)
        _check_membership(request, project)

        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        if cycle.status == FeedbackCycle.Status.COMPLETED:
            raise PermissionDenied("Retrospective is completed and cannot be modified.")

        retro_session = get_object_or_404(RetrospectiveSession, cycle=cycle)
        cluster = get_object_or_404(TopicCluster, pk=cluster_id, session=retro_session)

        title = request.POST.get("title", "").strip()
        if not title:
            return render(
                request,
                "retrospectives/partials/cluster_title_form.html",
                {
                    "project": project,
                    "cycle": cycle,
                    "cluster": cluster,
                    "error": "Title cannot be blank.",
                    "csrf_token": get_token(request),
                },
                status=422,
            )

        cluster.title = title
        cluster.save(update_fields=["title"])

        return render(
            request,
            "retrospectives/partials/cluster_title.html",
            {"project": project, "cycle": cycle, "cluster": cluster, "csrf_token": get_token(request)},
        )


class ClusterTitleView(LoginRequiredMixin, View):
    """Returns read-only title partial for canceling inline edit."""

    def get(self, request, slug, pk, cluster_id):
        project = get_object_or_404(Project, slug=slug)
        _check_membership(request, project)
        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        retro_session = get_object_or_404(RetrospectiveSession, cycle=cycle)
        cluster = get_object_or_404(TopicCluster, pk=cluster_id, session=retro_session)

        return render(
            request,
            "retrospectives/partials/cluster_title.html",
            {"project": project, "cycle": cycle, "cluster": cluster, "csrf_token": get_token(request)},
        )


class ClusterDeleteView(LoginRequiredMixin, View):
    """Deletes a topic cluster and returns all its cards to unclustered pool."""

    def post(self, request, slug, pk, cluster_id):
        project = get_object_or_404(Project, slug=slug)
        _check_membership(request, project)

        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        if cycle.status == FeedbackCycle.Status.COMPLETED:
            raise PermissionDenied("Retrospective is completed and cannot be modified.")

        retro_session = get_object_or_404(RetrospectiveSession, cycle=cycle)
        cluster = get_object_or_404(TopicCluster, pk=cluster_id, session=retro_session)

        # Dislodge all cards belonging to this cluster
        cluster.cards.update(cluster=None)
        cluster.delete()

        is_htmx = getattr(request, "htmx", False) or request.headers.get("HX-Request") == "true"
        if is_htmx:
            unclustered_cards = cycle.cards.filter(cluster=None).select_related("user").all()
            pool_html = render_to_string(
                "retrospectives/partials/unclustered_pool.html",
                {"unclustered_cards": unclustered_cards, "project": project, "cycle": cycle},
                request=request,
            )
            # Empty response removes cluster-item from DOM, plus OOB swap updates the pool
            return HttpResponse(f'<div id="unclustered-pool" hx-swap-oob="true">{pool_html}</div>')

        messages.success(request, f"Cluster '{cluster.title}' deleted. Cards returned to unclustered pool.")
        return redirect("retro_board", slug=slug, pk=pk)


class RetroCardMoveView(LoginRequiredMixin, View):
    """Asynchronously moves a feedback card to a target cluster or to unclustered pool."""

    def post(self, request, card_id):
        card = get_object_or_404(FeedbackCard, pk=card_id)
        cycle = card.cycle
        project = cycle.project
        _check_membership(request, project)

        retro_session = getattr(cycle, "retro_session", None)
        if not retro_session or retro_session.current_stage != RetrospectiveSession.Stage.CLUSTER:
            raise PermissionDenied("Card movement is disabled when not in the CLUSTER stage.")

        cluster_id = request.POST.get("cluster_id")

        if cluster_id in [None, "", "null", "None"]:
            # Move card to unclustered pool
            card.cluster = None
            card.save(update_fields=["cluster"])
            return JsonResponse({
                "success": True,
                "card_id": card.pk,
                "cluster_id": None,
                "message": "Card moved to unclustered pool.",
            })

        try:
            target_cluster_id = int(cluster_id)
        except (ValueError, TypeError):
            return HttpResponseBadRequest("Invalid cluster_id provided.")

        try:
            target_cluster = TopicCluster.objects.get(pk=target_cluster_id)
        except TopicCluster.DoesNotExist:
            return HttpResponseBadRequest("Target cluster does not exist.")

        # Validate cross-project and cross-session isolation
        if target_cluster.session != retro_session:
            return HttpResponseBadRequest("Target cluster belongs to a different cycle or session.")

        card.cluster = target_cluster
        card.save(update_fields=["cluster"])

        return JsonResponse({
            "success": True,
            "card_id": card.pk,
            "cluster_id": target_cluster.pk,
            "message": f"Card moved to cluster '{target_cluster.title}'.",
        })
