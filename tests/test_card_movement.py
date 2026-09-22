"""Tests for Drag-and-Drop Card Clustering and Move Endpoint."""
import datetime
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.projects.models import Project, ProjectMember
from apps.cycles.models import FeedbackCycle, FeedbackCard
from apps.retrospectives.models import RetrospectiveSession, TopicCluster

User = get_user_model()


@pytest.mark.django_db
class TestCardMovement:
    @pytest.fixture(autouse=True)
    def setup_fixtures(self, client):
        self.client = client
        self.facilitator = User.objects.create_user(
            username="facilitator_john", email="john@example.com", password="password123"
        )
        self.member = User.objects.create_user(
            username="member_kate", email="kate@example.com", password="password123"
        )
        self.outsider = User.objects.create_user(
            username="outsider_luke", email="luke@example.com", password="password123"
        )

        self.project = Project.objects.create(name="Zeta", slug="zeta", created_by=self.facilitator)
        ProjectMember.objects.create(project=self.project, user=self.facilitator, role=ProjectMember.Role.FACILITATOR)
        ProjectMember.objects.create(project=self.project, user=self.member, role=ProjectMember.Role.MEMBER)

        self.cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.facilitator,
            week_date=datetime.date(2026, 9, 21),
            status=FeedbackCycle.Status.RETROSPECTIVE,
        )
        self.session = RetrospectiveSession.objects.create(
            cycle=self.cycle, current_stage=RetrospectiveSession.Stage.CLUSTER
        )

        self.cluster_a = TopicCluster.objects.create(session=self.session, title="Frontend Issues")
        self.cluster_b = TopicCluster.objects.create(session=self.session, title="Backend Issues")

        self.card = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.START,
            text="Improve React rendering performance",
            cluster=None,
        )
        self.move_url = reverse("retro_card_move", kwargs={"card_id": self.card.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.move_url, {"cluster_id": self.cluster_a.pk})
        assert response.status_code == 302
        assert "/login" in response.url

    def test_non_member_forbidden(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.move_url, {"cluster_id": self.cluster_a.pk})
        assert response.status_code == 403

    def test_card_to_cluster_persistence(self):
        self.client.force_login(self.member)
        response = self.client.post(self.move_url, {"cluster_id": self.cluster_a.pk})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cluster_id"] == self.cluster_a.pk

        self.card.refresh_from_db()
        assert self.card.cluster == self.cluster_a

    def test_cluster_to_unclustered_persistence(self):
        self.card.cluster = self.cluster_a
        self.card.save()

        self.client.force_login(self.member)
        response = self.client.post(self.move_url, {"cluster_id": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cluster_id"] is None

        self.card.refresh_from_db()
        assert self.card.cluster is None

    def test_cross_cluster_reassignment(self):
        self.card.cluster = self.cluster_a
        self.card.save()

        self.client.force_login(self.member)
        response = self.client.post(self.move_url, {"cluster_id": self.cluster_b.pk})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cluster_id"] == self.cluster_b.pk

        self.card.refresh_from_db()
        assert self.card.cluster == self.cluster_b

    def test_same_container_no_op(self):
        self.card.cluster = self.cluster_a
        self.card.save()

        self.client.force_login(self.member)
        response = self.client.post(self.move_url, {"cluster_id": self.cluster_a.pk})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cluster_id"] == self.cluster_a.pk

        self.card.refresh_from_db()
        assert self.card.cluster == self.cluster_a

    def test_stage_restriction_enforcement(self):
        # Move session stage to REVEAL
        self.session.current_stage = RetrospectiveSession.Stage.REVEAL
        self.session.save()

        self.client.force_login(self.member)
        response = self.client.post(self.move_url, {"cluster_id": self.cluster_a.pk})
        assert response.status_code == 403

        # Also test VOTE stage
        self.session.current_stage = RetrospectiveSession.Stage.VOTE
        self.session.save()
        response = self.client.post(self.move_url, {"cluster_id": self.cluster_a.pk})
        assert response.status_code == 403

    def test_cross_project_and_foreign_cluster_isolation(self):
        # Create another project and cluster
        other_project = Project.objects.create(name="Eta", slug="eta", created_by=self.facilitator)
        ProjectMember.objects.create(project=other_project, user=self.facilitator, role=ProjectMember.Role.FACILITATOR)
        other_cycle = FeedbackCycle.objects.create(
            project=other_project,
            facilitator=self.facilitator,
            week_date=datetime.date(2026, 9, 21),
            status=FeedbackCycle.Status.RETROSPECTIVE,
        )
        other_session = RetrospectiveSession.objects.create(
            cycle=other_cycle, current_stage=RetrospectiveSession.Stage.CLUSTER
        )
        foreign_cluster = TopicCluster.objects.create(session=other_session, title="Foreign Cluster")

        self.client.force_login(self.member)
        # Attempt to move card from project Zeta into cluster from project Eta
        response = self.client.post(self.move_url, {"cluster_id": foreign_cluster.pk})
        assert response.status_code == 400

        # Attempt with non-existent cluster ID
        err_res = self.client.post(self.move_url, {"cluster_id": 999999})
        assert err_res.status_code == 400
