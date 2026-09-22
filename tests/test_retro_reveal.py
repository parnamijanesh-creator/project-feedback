"""Tests for RetrospectiveSession model, RetroBoardView, and RetroRevealView."""
import datetime
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.projects.models import Project, ProjectMember
from apps.cycles.models import FeedbackCycle, FeedbackCard
from apps.retrospectives.models import RetrospectiveSession

User = get_user_model()


@pytest.mark.django_db
class TestRetrospectiveSessionModel:
    def test_create_retrospective_session(self):
        user = User.objects.create_user(username="lead", email="lead@example.com", password="password")
        project = Project.objects.create(name="Alpha", slug="alpha", created_by=user)
        ProjectMember.objects.create(project=project, user=user, role=ProjectMember.Role.FACILITATOR)
        cycle = FeedbackCycle.objects.create(
            project=project,
            facilitator=user,
            week_date=datetime.date(2026, 9, 21),
            status=FeedbackCycle.Status.COLLECTING,
        )

        retro = RetrospectiveSession.objects.create(cycle=cycle)
        assert retro.current_stage == RetrospectiveSession.Stage.REVEAL
        assert retro.cycle == cycle
        assert "Alpha" in str(retro)
        assert "Reveal" in str(retro)


@pytest.mark.django_db
class TestRetroBoardView:
    @pytest.fixture(autouse=True)
    def setup_fixtures(self, client):
        self.client = client
        self.facilitator = User.objects.create_user(
            username="facilitator_bob", email="bob@example.com", password="password123"
        )
        self.member = User.objects.create_user(
            username="member_alice", email="alice@example.com", password="password123"
        )
        self.outsider = User.objects.create_user(
            username="outsider_charlie", email="charlie@example.com", password="password123"
        )

        self.project = Project.objects.create(
            name="Team Pegasus", slug="team-pegasus", created_by=self.facilitator
        )
        ProjectMember.objects.create(
            project=self.project, user=self.facilitator, role=ProjectMember.Role.FACILITATOR
        )
        ProjectMember.objects.create(
            project=self.project, user=self.member, role=ProjectMember.Role.MEMBER
        )

        self.cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.facilitator,
            week_date=datetime.date(2026, 9, 21),
            status=FeedbackCycle.Status.COLLECTING,
        )
        self.board_url = reverse("retro_board", kwargs={"slug": self.project.slug, "pk": self.cycle.pk})
        self.reveal_url = reverse("retro_reveal", kwargs={"slug": self.project.slug, "pk": self.cycle.pk})

    def test_retro_board_requires_login(self):
        response = self.client.get(self.board_url)
        assert response.status_code == 302
        assert "/login" in response.url

    def test_non_member_forbidden(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.board_url)
        assert response.status_code == 403

    def test_pre_reveal_facilitator_sees_reveal_button(self):
        self.client.force_login(self.facilitator)
        response = self.client.get(self.board_url)
        assert response.status_code == 200
        assert "Cards Are Hidden" in response.content.decode()
        assert "Start Retrospective / Reveal Cards" in response.content.decode()

    def test_pre_reveal_member_sees_waiting_state(self):
        self.client.force_login(self.member)
        response = self.client.get(self.board_url)
        assert response.status_code == 200
        assert "Cards Are Hidden" in response.content.decode()
        assert "Waiting for project facilitator to start retrospective" in response.content.decode()
        assert "Start Retrospective / Reveal Cards" not in response.content.decode()

    def test_non_facilitator_cannot_trigger_reveal(self):
        self.client.force_login(self.member)
        response = self.client.post(self.reveal_url)
        assert response.status_code == 403

        # outsider also cannot
        self.client.force_login(self.outsider)
        response = self.client.post(self.reveal_url)
        assert response.status_code == 403

    def test_facilitator_reveal_transitions_cycle_and_creates_retro_session(self):
        self.client.force_login(self.facilitator)
        response = self.client.post(self.reveal_url, follow=True)
        assert response.status_code == 200
        assert response.redirect_chain[0][0] == self.board_url

        self.cycle.refresh_from_db()
        assert self.cycle.status == FeedbackCycle.Status.RETROSPECTIVE

        retro = RetrospectiveSession.objects.filter(cycle=self.cycle).first()
        assert retro is not None
        assert retro.current_stage == RetrospectiveSession.Stage.REVEAL

    def test_post_reveal_cards_displayed_and_anonymity_enforced(self):
        # Create test cards
        anon_card = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.START,
            text="Start daily standups earlier",
            is_anonymous=True,
            user=None,
        )
        non_anon_card = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.STOP,
            text="Stop having unstructured meetings",
            is_anonymous=False,
            user=self.member,
        )

        # Trigger reveal
        self.client.force_login(self.facilitator)
        self.client.post(self.reveal_url)

        # Now regular member visits the board
        self.client.force_login(self.member)
        response = self.client.get(self.board_url)
        assert response.status_code == 200
        content = response.content.decode()

        # Check that cards are visible
        assert "Start daily standups earlier" in content
        assert "Stop having unstructured meetings" in content

        # Check anonymity
        assert "Anonymous" in content
        assert self.member.username in content  # For the non-anonymous card

        # Continue column has no cards, should display empty placeholder cleanly
        assert "No cards submitted" in content
