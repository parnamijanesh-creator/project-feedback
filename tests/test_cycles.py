"""Automated tests for Feedback Cycle Creation and Facilitator Controls (Issue #5)."""
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.cycles.models import FeedbackCycle, get_current_week_start
from apps.projects.models import Project, ProjectMember

User = get_user_model()


class FeedbackCycleTests(TestCase):
    """Test suite for FeedbackCycle creation, permissions, safeguards, and status transitions."""

    def setUp(self):
        self.client = Client()
        self.facilitator = User.objects.create_user(
            username="cycle_lead", email="lead@example.com", password="Password123!"
        )
        self.member = User.objects.create_user(
            username="team_member", email="member@example.com", password="Password123!"
        )
        self.outsider = User.objects.create_user(
            username="outsider", email="outsider@example.com", password="Password123!"
        )

        self.project = Project.objects.create(
            name="Platform Engineering",
            description="Core infrastructure team",
            created_by=self.facilitator,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.facilitator,
            role=ProjectMember.Role.FACILITATOR,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMember.Role.MEMBER,
        )

        self.project_detail_url = reverse("project_detail", kwargs={"slug": self.project.slug})
        self.cycle_create_url = reverse("cycle_create", kwargs={"slug": self.project.slug})

    def test_feedback_cycle_model_fields_and_defaults(self):
        """Verify model fields, default status=COLLECTING, and current week calculation."""
        cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.facilitator,
        )
        self.assertEqual(cycle.status, FeedbackCycle.Status.COLLECTING)
        self.assertEqual(cycle.week_date, get_current_week_start())
        self.assertEqual(cycle.project, self.project)
        self.assertEqual(cycle.facilitator, self.facilitator)
        self.assertIsNotNone(cycle.created_at)

    def test_project_dashboard_lists_cycles(self):
        """Project dashboard renders list of cycles with target week and status badge."""
        cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.facilitator,
            week_date=date(2026, 9, 21),
            status=FeedbackCycle.Status.COLLECTING,
        )
        self.client.login(username="team_member", password="Password123!")
        response = self.client.get(self.project_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feedback Cycles")
        self.assertContains(response, "Week of Sep 21, 2026")
        self.assertContains(response, "Collecting Feedback")
        # Regular member does NOT see Start New Feedback Cycle button
        self.assertNotContains(response, "+ Start New Feedback Cycle")

    def test_facilitator_sees_start_cycle_button(self):
        """Facilitator sees '+ Start New Feedback Cycle' button on project dashboard."""
        self.client.login(username="cycle_lead", password="Password123!")
        response = self.client.get(self.project_detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "+ Start New Feedback Cycle")

    def test_facilitator_can_create_cycle(self):
        """Facilitator submits cycle form, creating a COLLECTING cycle and redirecting to cycle detail."""
        self.client.login(username="cycle_lead", password="Password123!")
        target_week = date(2026, 10, 5)
        post_data = {"week_date": target_week.isoformat()}
        response = self.client.post(self.cycle_create_url, data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        cycle = FeedbackCycle.objects.filter(project=self.project, week_date=target_week).first()
        self.assertIsNotNone(cycle)
        self.assertEqual(cycle.status, FeedbackCycle.Status.COLLECTING)
        self.assertEqual(cycle.facilitator, self.facilitator)
        self.assertRedirects(
            response,
            reverse("cycle_detail", kwargs={"slug": self.project.slug, "pk": cycle.pk}),
        )

    def test_cycle_creation_defaults_to_current_week(self):
        """Submitting cycle form without explicit date defaults to current week start."""
        self.client.login(username="cycle_lead", password="Password123!")
        response = self.client.post(self.cycle_create_url, data={}, follow=True)
        self.assertEqual(response.status_code, 200)

        cycle = FeedbackCycle.objects.filter(project=self.project).first()
        self.assertIsNotNone(cycle)
        self.assertEqual(cycle.week_date, get_current_week_start())

    def test_non_facilitator_cannot_create_cycle(self):
        """Non-facilitator members attempting to POST to cycle create receive HTTP 403 Forbidden."""
        self.client.login(username="team_member", password="Password123!")
        response = self.client.post(self.cycle_create_url, data={"week_date": "2026-10-12"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(FeedbackCycle.objects.count(), 0)

    def test_concurrent_active_cycle_safeguard(self):
        """Creating another cycle while one is COLLECTING triggers error unless confirmed."""
        FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.facilitator,
            status=FeedbackCycle.Status.COLLECTING,
        )
        self.client.login(username="cycle_lead", password="Password123!")

        # Attempt to start second active cycle without override
        next_week = get_current_week_start() + timedelta(days=7)
        response = self.client.post(
            self.cycle_create_url, data={"week_date": next_week.isoformat()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An active feedback cycle is currently collecting submissions")
        self.assertEqual(FeedbackCycle.objects.count(), 1)

        # Force with allow_concurrent=True
        force_response = self.client.post(
            self.cycle_create_url,
            data={"week_date": next_week.isoformat(), "allow_concurrent": "on"},
            follow=True,
        )
        self.assertEqual(force_response.status_code, 200)
        self.assertEqual(FeedbackCycle.objects.count(), 2)

    def test_cycle_detail_view_permissions(self):
        """Members can view cycle detail; non-members receive HTTP 403 Forbidden."""
        cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.facilitator,
            week_date=date(2026, 9, 28),
        )
        cycle_url = reverse("cycle_detail", kwargs={"slug": self.project.slug, "pk": cycle.pk})

        # Member access
        self.client.login(username="team_member", password="Password123!")
        member_resp = self.client.get(cycle_url)
        self.assertEqual(member_resp.status_code, 200)
        self.assertContains(member_resp, "Feedback Cycle: Week of Sep 28, 2026")
        # Regular member cannot see status transition form
        self.assertNotContains(member_resp, "Transition Phase:")

        # Outsider access
        self.client.login(username="outsider", password="Password123!")
        outsider_resp = self.client.get(cycle_url)
        self.assertEqual(outsider_resp.status_code, 403)

    def test_facilitator_can_transition_cycle_status(self):
        """Facilitator can transition cycle status to RETROSPECTIVE and COMPLETED."""
        cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.facilitator,
            status=FeedbackCycle.Status.COLLECTING,
        )
        transition_url = reverse(
            "cycle_status_transition", kwargs={"slug": self.project.slug, "pk": cycle.pk}
        )

        # Facilitator transitions to RETROSPECTIVE
        self.client.login(username="cycle_lead", password="Password123!")
        resp1 = self.client.post(
            transition_url, data={"status": FeedbackCycle.Status.RETROSPECTIVE}, follow=True
        )
        self.assertEqual(resp1.status_code, 200)
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, FeedbackCycle.Status.RETROSPECTIVE)
        self.assertContains(resp1, "Retrospective In Session")

        # Facilitator transitions to COMPLETED
        resp2 = self.client.post(
            transition_url, data={"status": FeedbackCycle.Status.COMPLETED}, follow=True
        )
        self.assertEqual(resp2.status_code, 200)
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, FeedbackCycle.Status.COMPLETED)
        self.assertContains(resp2, "Cycle Completed")

    def test_non_facilitator_cannot_transition_cycle_status(self):
        """Non-facilitator member attempting to transition status receives HTTP 403."""
        cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.facilitator,
            status=FeedbackCycle.Status.COLLECTING,
        )
        transition_url = reverse(
            "cycle_status_transition", kwargs={"slug": self.project.slug, "pk": cycle.pk}
        )
        self.client.login(username="team_member", password="Password123!")
        response = self.client.post(
            transition_url, data={"status": FeedbackCycle.Status.RETROSPECTIVE}
        )
        self.assertEqual(response.status_code, 403)
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, FeedbackCycle.Status.COLLECTING)
