"""Tests for Voting Close and Ranked Discussion Agenda."""
import datetime
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cycles.models import FeedbackCard, FeedbackCycle
from apps.projects.models import Project, ProjectMember
from apps.retrospectives.models import (
    ClusterVote,
    DiscussionTopic,
    RetrospectiveSession,
    TopicCluster,
)

User = get_user_model()


@pytest.mark.django_db
class TestDiscussionAgenda:
    @pytest.fixture(autouse=True)
    def setup_fixtures(self, client):
        self.client = client
        self.facilitator = User.objects.create_user(
            username="facilitator_sarah", email="sarah@example.com", password="password123"
        )
        self.member1 = User.objects.create_user(
            username="member_john", email="john@example.com", password="password123"
        )
        self.member2 = User.objects.create_user(
            username="member_lisa", email="lisa@example.com", password="password123"
        )
        self.outsider = User.objects.create_user(
            username="outsider_eve", email="eve@example.com", password="password123"
        )

        self.project = Project.objects.create(name="Delta", slug="delta", created_by=self.facilitator)
        ProjectMember.objects.create(project=self.project, user=self.facilitator, role=ProjectMember.Role.FACILITATOR)
        ProjectMember.objects.create(project=self.project, user=self.member1, role=ProjectMember.Role.MEMBER)
        ProjectMember.objects.create(project=self.project, user=self.member2, role=ProjectMember.Role.MEMBER)

        self.cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.facilitator,
            week_date=datetime.date(2026, 9, 21),
            status=FeedbackCycle.Status.RETROSPECTIVE,
        )
        self.session = RetrospectiveSession.objects.create(
            cycle=self.cycle, current_stage=RetrospectiveSession.Stage.VOTE
        )

        self.close_voting_url = reverse(
            "retro_close_voting", kwargs={"slug": self.project.slug, "pk": self.cycle.pk}
        )
        self.board_url = reverse(
            "retro_board", kwargs={"slug": self.project.slug, "pk": self.cycle.pk}
        )

    def test_discussion_topic_model_structure(self):
        cluster = TopicCluster.objects.create(session=self.session, title="Refactoring Debt")
        topic = DiscussionTopic.objects.create(
            session=self.session,
            cluster=cluster,
            title=cluster.title,
            vote_count=4,
            order=1,
            status=DiscussionTopic.Status.PENDING,
        )
        assert topic.pk is not None
        assert topic.session == self.session
        assert topic.cluster == cluster
        assert topic.title == "Refactoring Debt"
        assert topic.vote_count == 4
        assert topic.order == 1
        assert topic.status == DiscussionTopic.Status.PENDING
        assert str(topic) == "#1 Refactoring Debt (4 votes) - Pending"

    def test_facilitator_only_can_close_voting(self):
        # Anonymous user gets redirected
        anon_response = self.client.post(self.close_voting_url)
        assert anon_response.status_code == 302
        assert "/login" in anon_response.url

        # Non-member gets 403 Forbidden
        self.client.force_login(self.outsider)
        outsider_response = self.client.post(self.close_voting_url)
        assert outsider_response.status_code == 403

        # Regular project member gets 403 Forbidden
        self.client.force_login(self.member1)
        member_response = self.client.post(self.close_voting_url)
        assert member_response.status_code == 403

        # Facilitator succeeds
        self.client.force_login(self.facilitator)
        fac_response = self.client.post(self.close_voting_url)
        assert fac_response.status_code == 302
        self.session.refresh_from_db()
        assert self.session.current_stage == RetrospectiveSession.Stage.DISCUSS

    def test_facilitator_ui_visibility(self):
        # Facilitator sees the Close Voting button in VOTE stage
        self.client.force_login(self.facilitator)
        res = self.client.get(self.board_url)
        assert res.status_code == 200
        assert "Close Voting &amp; Generate Agenda" in res.content.decode() or "Close Voting & Generate Agenda" in res.content.decode()

        # Member does not see the Close Voting button
        self.client.force_login(self.member1)
        res_member = self.client.get(self.board_url)
        assert res_member.status_code == 200
        assert "close-voting-btn" not in res_member.content.decode()

    def test_vote_aggregation_ranking_and_stacked_votes(self):
        # Create 3 clusters
        cluster_high = TopicCluster.objects.create(session=self.session, title="High Priority CI/CD")
        cluster_med = TopicCluster.objects.create(session=self.session, title="Medium Priority Docs")
        cluster_zero = TopicCluster.objects.create(session=self.session, title="Zero Votes Parking Lot")

        # Add cards to clusters
        card1 = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.START,
            text="Add automated tests before merge",
            cluster=cluster_high,
        )
        card2 = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.STOP,
            text="Stop skipping docs",
            cluster=cluster_med,
        )

        # Cast votes:
        # member1 casts 3 stacked votes on cluster_high
        ClusterVote.objects.create(cluster=cluster_high, user=self.member1)
        ClusterVote.objects.create(cluster=cluster_high, user=self.member1)
        ClusterVote.objects.create(cluster=cluster_high, user=self.member1)

        # member2 casts 1 vote on cluster_high, 1 on cluster_med
        ClusterVote.objects.create(cluster=cluster_high, user=self.member2)
        ClusterVote.objects.create(cluster=cluster_med, user=self.member2)

        # facilitator casts 1 vote on cluster_med
        ClusterVote.objects.create(cluster=cluster_med, user=self.facilitator)

        # cluster_high total = 4
        # cluster_med total = 2
        # cluster_zero total = 0

        self.client.force_login(self.facilitator)
        response = self.client.post(self.close_voting_url, follow=True)
        assert response.status_code == 200

        self.session.refresh_from_db()
        assert self.session.current_stage == RetrospectiveSession.Stage.DISCUSS

        topics = list(DiscussionTopic.objects.filter(session=self.session).order_by("order"))
        assert len(topics) == 3

        # Rank 1: cluster_high
        assert topics[0].order == 1
        assert topics[0].cluster == cluster_high
        assert topics[0].title == "High Priority CI/CD"
        assert topics[0].vote_count == 4

        # Rank 2: cluster_med
        assert topics[1].order == 2
        assert topics[1].cluster == cluster_med
        assert topics[1].title == "Medium Priority Docs"
        assert topics[1].vote_count == 2

        # Rank 3: cluster_zero with 0 votes
        assert topics[2].order == 3
        assert topics[2].cluster == cluster_zero
        assert topics[2].title == "Zero Votes Parking Lot"
        assert topics[2].vote_count == 0

        # Verify HTML rendered on discuss board
        content = response.content.decode()
        assert "Ranked Discussion Agenda" in content
        assert "#1" in content
        assert "High Priority CI/CD" in content
        assert "4 votes" in content
        assert "#2" in content
        assert "Medium Priority Docs" in content
        assert "2 votes" in content
        assert "#3" in content
        assert "Zero Votes Parking Lot" in content
        assert "0 votes" in content
        assert "Add automated tests before merge" in content

    def test_deterministic_tie_breaking(self):
        # Create two clusters with different timestamps
        time_early = timezone.now() - datetime.timedelta(minutes=10)
        time_late = timezone.now() - datetime.timedelta(minutes=5)

        cluster_earlier = TopicCluster.objects.create(session=self.session, title="Alpha Topic")
        TopicCluster.objects.filter(pk=cluster_earlier.pk).update(created_at=time_early)
        cluster_earlier.refresh_from_db()

        cluster_later = TopicCluster.objects.create(session=self.session, title="Beta Topic")
        TopicCluster.objects.filter(pk=cluster_later.pk).update(created_at=time_late)
        cluster_later.refresh_from_db()

        # Both get exactly 1 vote
        ClusterVote.objects.create(cluster=cluster_earlier, user=self.member1)
        ClusterVote.objects.create(cluster=cluster_later, user=self.member2)

        self.client.force_login(self.facilitator)
        self.client.post(self.close_voting_url)

        topics = list(DiscussionTopic.objects.filter(session=self.session).order_by("order"))
        assert len(topics) == 2
        # Earlier created cluster wins the tie-breaker
        assert topics[0].cluster == cluster_earlier
        assert topics[0].order == 1
        assert topics[1].cluster == cluster_later
        assert topics[1].order == 2

    def test_empty_session_handles_close_voting_gracefully(self):
        # Session has 0 clusters
        self.client.force_login(self.facilitator)
        response = self.client.post(self.close_voting_url, follow=True)
        assert response.status_code == 200

        self.session.refresh_from_db()
        assert self.session.current_stage == RetrospectiveSession.Stage.DISCUSS
        assert DiscussionTopic.objects.filter(session=self.session).count() == 0

        content = response.content.decode()
        assert "No topics for discussion" in content

    def test_voting_locked_after_close_voting(self):
        cluster = TopicCluster.objects.create(session=self.session, title="Deployment Pipeline")

        # Close voting
        self.client.force_login(self.facilitator)
        self.client.post(self.close_voting_url)
        self.session.refresh_from_db()
        assert self.session.current_stage == RetrospectiveSession.Stage.DISCUSS

        # Casting a vote is now rejected
        vote_url = reverse("cluster_vote_cast", kwargs={"cluster_id": cluster.pk})
        self.client.force_login(self.member1)
        cast_res = self.client.post(vote_url)
        assert cast_res.status_code == 403

        # Retracting a vote is also rejected
        retract_url = reverse("cluster_vote_retract", kwargs={"cluster_id": cluster.pk})
        retract_res = self.client.post(retract_url)
        assert retract_res.status_code == 403
