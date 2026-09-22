"""Tests for AI-Assisted Thematic Card Clustering Service and Facilitator Trigger."""
import datetime
from unittest.mock import MagicMock, patch
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.projects.models import Project, ProjectMember
from apps.cycles.models import FeedbackCycle, FeedbackCard
from apps.retrospectives.models import RetrospectiveSession, TopicCluster
from apps.ai_insights.services.clustering import (
    AIClusteringService,
    ClusteringResponse,
    ThematicClusterItem,
)

User = get_user_model()


@pytest.mark.django_db
class TestTopicClusterModel:
    def test_topic_cluster_creation_and_card_association(self):
        user = User.objects.create_user(username="lead", email="lead@example.com", password="password")
        project = Project.objects.create(name="Omega", slug="omega", created_by=user)
        ProjectMember.objects.create(project=project, user=user, role=ProjectMember.Role.FACILITATOR)
        cycle = FeedbackCycle.objects.create(
            project=project,
            facilitator=user,
            week_date=datetime.date(2026, 9, 21),
            status=FeedbackCycle.Status.RETROSPECTIVE,
        )
        session = RetrospectiveSession.objects.create(cycle=cycle)

        cluster = TopicCluster.objects.create(
            session=session,
            title="CI/CD Performance",
            description="Speed up test execution",
            is_ai_generated=True,
        )
        assert cluster.session == session
        assert cluster.title == "CI/CD Performance"
        assert cluster.is_ai_generated is True
        assert str(cluster) == "CI/CD Performance"

        card = FeedbackCard.objects.create(
            cycle=cycle,
            category=FeedbackCard.Category.START,
            text="Cache Docker layers in GitHub Actions",
            cluster=cluster,
        )
        assert card.cluster == cluster
        assert cluster.cards.count() == 1
        assert cluster.cards.first() == card


@pytest.mark.django_db
class TestAIClusteringService:
    @pytest.fixture(autouse=True)
    def setup_fixtures(self):
        self.user = User.objects.create_user(username="lead", email="lead@example.com", password="password")
        self.project = Project.objects.create(name="Gamma", slug="gamma", created_by=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role=ProjectMember.Role.FACILITATOR)
        self.cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.user,
            week_date=datetime.date(2026, 9, 21),
            status=FeedbackCycle.Status.RETROSPECTIVE,
        )
        self.session = RetrospectiveSession.objects.create(cycle=self.cycle)

    def test_skips_clustering_when_fewer_than_two_cards(self):
        # 1 card only
        FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.START,
            text="Only one card",
        )
        mock_client = MagicMock()
        service = AIClusteringService(client=mock_client)

        clusters = service.cluster_session(self.session)
        assert clusters == []
        mock_client.beta.chat.completions.parse.assert_not_called()
        assert TopicCluster.objects.filter(session=self.session).count() == 0

    def test_successful_clustering_with_mocked_llm(self):
        c1 = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.START,
            text="Speed up CI test runs",
        )
        c2 = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.STOP,
            text="Stop ignoring flaky unit tests",
        )
        c3 = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.CONTINUE,
            text="Continue pair programming on complex PRs",
        )

        # Mock structured LLM response
        fake_response = ClusteringResponse(
            clusters=[
                ThematicClusterItem(
                    title="CI / Test Pipeline Health",
                    description="Issues relating to test run speed and flaky failures.",
                    card_ids=[c1.pk, c2.pk],
                )
            ]
        )

        mock_client = MagicMock()
        mock_client.beta.chat.completions.parse.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(parsed=fake_response))]
        )

        service = AIClusteringService(client=mock_client)
        clusters = service.cluster_session(self.session)

        assert len(clusters) == 1
        cluster = clusters[0]
        assert cluster.title == "CI / Test Pipeline Health"
        assert cluster.is_ai_generated is True
        assert cluster.session == self.session

        # Verify DB mapping
        c1.refresh_from_db()
        c2.refresh_from_db()
        c3.refresh_from_db()
        assert c1.cluster == cluster
        assert c2.cluster == cluster
        # Omitted card remains unassigned
        assert c3.cluster is None

        # Verify stage transition to CLUSTER
        self.session.refresh_from_db()
        assert self.session.current_stage == RetrospectiveSession.Stage.CLUSTER

    def test_sanitizes_unknown_and_foreign_card_ids(self):
        c1 = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.START,
            text="Valid card in active cycle",
        )
        c2 = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.CONTINUE,
            text="Another valid card",
        )

        # Separate foreign cycle and card
        foreign_cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.user,
            week_date=datetime.date(2026, 9, 14),
            status=FeedbackCycle.Status.COMPLETED,
        )
        foreign_card = FeedbackCard.objects.create(
            cycle=foreign_cycle,
            category=FeedbackCard.Category.START,
            text="Card from different cycle",
        )

        fake_response = ClusteringResponse(
            clusters=[
                ThematicClusterItem(
                    title="Valid Cluster with Injected Foreign IDs",
                    description="Group with non-existent and foreign IDs",
                    card_ids=[c1.pk, foreign_card.pk, 999999],
                ),
                ThematicClusterItem(
                    title="Completely Bogus Cluster",
                    description="Contains only non-existent IDs",
                    card_ids=[888888, 777777],
                ),
            ]
        )

        mock_client = MagicMock()
        mock_client.beta.chat.completions.parse.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(parsed=fake_response))]
        )

        service = AIClusteringService(client=mock_client)
        clusters = service.cluster_session(self.session)

        # Only the cluster with at least 1 valid card is created
        assert len(clusters) == 1
        valid_cluster = clusters[0]
        assert valid_cluster.title == "Valid Cluster with Injected Foreign IDs"

        c1.refresh_from_db()
        foreign_card.refresh_from_db()
        assert c1.cluster == valid_cluster
        # Foreign card was NOT modified
        assert foreign_card.cluster is None

    def test_graceful_degradation_on_llm_exception(self):
        FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.START,
            text="Card 1",
        )
        FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.STOP,
            text="Card 2",
        )

        mock_client = MagicMock()
        mock_client.beta.chat.completions.parse.side_effect = RuntimeError("OpenAI API rate limit exceeded")

        service = AIClusteringService(client=mock_client)

        with patch("apps.ai_insights.services.clustering.logger.error") as mock_log:
            clusters = service.cluster_session(self.session)
            assert clusters == []
            mock_log.assert_called_once()

        # No clusters created, cards unaffected
        assert TopicCluster.objects.filter(session=self.session).count() == 0


@pytest.mark.django_db
class TestRetroRunClusteringView:
    @pytest.fixture(autouse=True)
    def setup_fixtures(self, client):
        self.client = client
        self.facilitator = User.objects.create_user(
            username="facilitator_dan", email="dan@example.com", password="password123"
        )
        self.member = User.objects.create_user(
            username="member_eva", email="eva@example.com", password="password123"
        )
        self.outsider = User.objects.create_user(
            username="outsider_frank", email="frank@example.com", password="password123"
        )

        self.project = Project.objects.create(name="Delta", slug="delta", created_by=self.facilitator)
        ProjectMember.objects.create(project=self.project, user=self.facilitator, role=ProjectMember.Role.FACILITATOR)
        ProjectMember.objects.create(project=self.project, user=self.member, role=ProjectMember.Role.MEMBER)

        self.cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.facilitator,
            week_date=datetime.date(2026, 9, 21),
            status=FeedbackCycle.Status.RETROSPECTIVE,
        )
        self.session = RetrospectiveSession.objects.create(cycle=self.cycle)

        self.cluster_url = reverse("retro_run_clustering", kwargs={"slug": self.project.slug, "pk": self.cycle.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.cluster_url)
        assert response.status_code == 302
        assert "/login" in response.url

    def test_non_member_forbidden(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.cluster_url)
        assert response.status_code == 403

    def test_member_forbidden(self):
        self.client.force_login(self.member)
        response = self.client.post(self.cluster_url)
        assert response.status_code == 403

    def test_facilitator_can_trigger_clustering(self):
        FeedbackCard.objects.create(cycle=self.cycle, category=FeedbackCard.Category.START, text="Card A")
        FeedbackCard.objects.create(cycle=self.cycle, category=FeedbackCard.Category.STOP, text="Card B")

        with patch.object(AIClusteringService, "cluster_session") as mock_cluster:
            cluster_mock = TopicCluster(
                session=self.session,
                title="Engineering Workflow",
                is_ai_generated=True,
            )
            mock_cluster.return_value = [cluster_mock]

            self.client.force_login(self.facilitator)
            response = self.client.post(self.cluster_url, follow=True)

            assert response.status_code == 200
            mock_cluster.assert_called_once_with(self.session)
            messages = [m.message for m in response.context["messages"]]
            assert any("Generated 1 AI thematic cluster" in m for m in messages)
