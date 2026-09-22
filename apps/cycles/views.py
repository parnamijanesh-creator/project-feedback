"""Views for managing Feedback Cycles, phase transitions, and card submissions."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.projects.models import Project, ProjectMember
from .forms import FeedbackCycleCreateForm
from .models import FeedbackCard, FeedbackCycle


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


class FeedbackSubmitView(LoginRequiredMixin, View):
    """Three-column feedback submission view (Start, Stop, Continue) with HTMX support."""

    def get_project_and_cycle(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        membership = ProjectMember.objects.filter(project=project, user=request.user).first()
        if not membership:
            raise PermissionDenied("You are not a member of this project.")
        cycle = get_object_or_404(FeedbackCycle, pk=pk, project=project)
        return project, cycle

    def get(self, request, slug, pk):
        project, cycle = self.get_project_and_cycle(request, slug, pk)

        # Non-Negotiable Rule #2: Private until revealed. Only query cards authored by current user
        # (either matching user FK or matching anonymous card IDs stored in active user session).
        anon_ids = request.session.get("anonymous_card_ids", [])
        user_cards = cycle.cards.filter(Q(user=request.user) | Q(id__in=anon_ids))

        context = {
            "project": project,
            "cycle": cycle,
            "start_cards": user_cards.filter(category=FeedbackCard.Category.START),
            "stop_cards": user_cards.filter(category=FeedbackCard.Category.STOP),
            "continue_cards": user_cards.filter(category=FeedbackCard.Category.CONTINUE),
        }
        return render(request, "cycles/submit.html", context)

    def post(self, request, slug, pk):
        project, cycle = self.get_project_and_cycle(request, slug, pk)

        if cycle.status != FeedbackCycle.Status.COLLECTING:
            return HttpResponseForbidden("Feedback collection is closed for this cycle.")

        category = request.POST.get("category", "").upper()
        text = request.POST.get("text", "").strip()
        is_anonymous = request.POST.get("is_anonymous") in ["on", "true", "True", True]

        if not text:
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<div class="form-error mt-1 text-xs text-rose-600">Card text cannot be blank.</div>',
                    status=422,
                )
            messages.error(request, "Card text cannot be blank.")
            return redirect("feedback_submit", slug=slug, pk=pk)

        if category not in FeedbackCard.Category.values:
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<div class="form-error mt-1 text-xs text-rose-600">Invalid category.</div>',
                    status=422,
                )
            messages.error(request, "Invalid category.")
            return redirect("feedback_submit", slug=slug, pk=pk)

        card = FeedbackCard(
            cycle=cycle,
            user=request.user if not is_anonymous else None,
            category=category,
            text=text,
            is_anonymous=is_anonymous,
        )
        card.save()

        if is_anonymous:
            anon_ids = request.session.setdefault("anonymous_card_ids", [])
            anon_ids.append(card.id)
            request.session.modified = True

        if request.headers.get("HX-Request"):
            return render(
                request,
                "cycles/partials/card_item.html",
                {"card": card, "cycle": cycle, "project": project},
            )

        messages.success(request, f"Added {card.get_category_display()} feedback card.")
        return redirect("feedback_submit", slug=slug, pk=pk)


class CardEditView(LoginRequiredMixin, View):
    """Inline HTMX card editing allowing users to update their own cards."""

    def get_card_and_verify_owner(self, request, slug, cycle_pk, card_pk):
        project = get_object_or_404(Project, slug=slug)
        membership = ProjectMember.objects.filter(project=project, user=request.user).first()
        if not membership:
            raise PermissionDenied("You are not a member of this project.")

        cycle = get_object_or_404(FeedbackCycle, pk=cycle_pk, project=project)
        card = get_object_or_404(FeedbackCard, pk=card_pk, cycle=cycle)

        anon_ids = request.session.get("anonymous_card_ids", [])
        is_owner = (card.user == request.user) or (card.id in anon_ids)
        if not is_owner:
            raise PermissionDenied("You cannot edit this feedback card.")

        return project, cycle, card

    def get(self, request, slug, cycle_pk, card_pk):
        project, cycle, card = self.get_card_and_verify_owner(request, slug, cycle_pk, card_pk)
        return render(
            request,
            "cycles/partials/card_edit_form.html",
            {"project": project, "cycle": cycle, "card": card},
        )

    def post(self, request, slug, cycle_pk, card_pk):
        project, cycle, card = self.get_card_and_verify_owner(request, slug, cycle_pk, card_pk)

        if cycle.status != FeedbackCycle.Status.COLLECTING:
            return HttpResponseForbidden("Feedback collection is closed.")

        new_text = request.POST.get("text", "").strip()
        if not new_text:
            return render(
                request,
                "cycles/partials/card_edit_form.html",
                {"project": project, "cycle": cycle, "card": card, "error": "Card text cannot be blank."},
                status=422,
            )

        card.text = new_text
        card.save()
        return render(
            request,
            "cycles/partials/card_item.html",
            {"project": project, "cycle": cycle, "card": card},
        )


class CardDetailPartialView(LoginRequiredMixin, View):
    """Renders card item partial when user cancels inline editing."""

    def get(self, request, slug, cycle_pk, card_pk):
        project = get_object_or_404(Project, slug=slug)
        cycle = get_object_or_404(FeedbackCycle, pk=cycle_pk, project=project)
        card = get_object_or_404(FeedbackCard, pk=card_pk, cycle=cycle)
        return render(
            request,
            "cycles/partials/card_item.html",
            {"project": project, "cycle": cycle, "card": card},
        )


class CardDeleteView(LoginRequiredMixin, View):
    """Deletes a card authored by the current user via HTMX."""

    def post(self, request, slug, cycle_pk, card_pk):
        project = get_object_or_404(Project, slug=slug)
        membership = ProjectMember.objects.filter(project=project, user=request.user).first()
        if not membership:
            raise PermissionDenied("You are not a member of this project.")

        cycle = get_object_or_404(FeedbackCycle, pk=cycle_pk, project=project)
        if cycle.status != FeedbackCycle.Status.COLLECTING:
            return HttpResponseForbidden("Feedback collection is closed.")

        card = get_object_or_404(FeedbackCard, pk=card_pk, cycle=cycle)
        anon_ids = request.session.get("anonymous_card_ids", [])
        is_owner = (card.user == request.user) or (card.id in anon_ids)
        if not is_owner:
            raise PermissionDenied("You cannot delete this feedback card.")

        card.delete()
        if card.id in anon_ids:
            anon_ids.remove(card.id)
            request.session["anonymous_card_ids"] = anon_ids
            request.session.modified = True

        return HttpResponse("", status=200)

    def delete(self, request, slug, cycle_pk, card_pk):
        return self.post(request, slug, cycle_pk, card_pk)
