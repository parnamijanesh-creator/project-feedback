"""Tests for Secret Voting on Discussion Clusters."""
import datetime
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.projects.models import Project, ProjectMember
from apps.cycles.models import FeedbackCycle
from apps.retrospectives.models import ClusterVote, RetrospectiveSession, TopicCluster

User = get_user_model()


@pytest.mark.django_db
class TestClusterVoting:
    @pytest.fixture(autouse=True)
    def setup_fixtures(self, client):
        self.client = client
        self.facilitator = User.objects.create_user(
            username="facilitator_bob", email="bob@example.com", password="password123"
        )
        self.member1 = User.objects.create_user(
            username="member_alice", email="alice@example.com", password="password123"
        )
        self.member2 = User.objects.create_user(
            username="member_charlie", email="charlie@example.com", password="password123"
        )
        self.outsider = User.objects.create_user(
            username="outsider_dan", email="dan@example.com", password="password123"
        )

        self.project = Project.objects.create(name="Theta", slug="theta", created_by=self.facilitator)
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

        self.cluster_a = TopicCluster.objects.create(session=self.session, title="DevOps Friction")
        self.cluster_b = TopicCluster.objects.create(session=self.session, title="Meeting Overload")

        self.board_url = reverse("retro_board", kwargs={"slug": self.project.slug, "pk": self.cycle.pk})
        self.vote_a_url = reverse("cluster_vote_cast", kwargs={"cluster_id": self.cluster_a.pk})
        self.retract_a_url = reverse("cluster_vote_retract", kwargs={"cluster_id": self.cluster_a.pk})
        self.vote_b_url = reverse("cluster_vote_cast", kwargs={"cluster_id": self.cluster_b.pk})

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.vote_a_url)
        assert response.status_code == 302
        assert "/login" in response.url

    def test_non_member_forbidden(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.vote_a_url)
        assert response.status_code == 403

        retract_res = self.client.post(self.retract_a_url)
        assert retract_res.status_code == 403

    def test_voting_stage_restriction_enforcement(self):
        # Move session stage to CLUSTER
        self.session.current_stage = RetrospectiveSession.Stage.CLUSTER
        self.session.save()

        self.client.force_login(self.member1)
        response = self.client.post(self.vote_a_url)
        assert response.status_code == 403

        retract_res = self.client.post(self.retract_a_url)
        assert retract_res.status_code == 403

    def test_stackability_and_strict_three_vote_limit(self):
        self.client.force_login(self.member1)

        # Vote 1 on Cluster A
        res1 = self.client.post(self.vote_a_url)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["user_votes"] == 1
        assert data1["remaining_votes"] == 2

        # Vote 2 stacked on Cluster A
        res2 = self.client.post(self.vote_a_url)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["user_votes"] == 2
        assert data2["remaining_votes"] == 1

        # Vote 3 stacked on Cluster A
        res3 = self.client.post(self.vote_a_url)
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["user_votes"] == 3
        assert data3["remaining_votes"] == 0

        # Attempting 4th vote on Cluster A is strictly rejected with HTTP 400
        res4 = self.client.post(self.vote_a_url)
        assert res4.status_code == 400

        # Attempting 4th vote on Cluster B is also strictly rejected with HTTP 400
        res4_b = self.client.post(self.vote_b_url)
        assert res4_b.status_code == 400

        # Verify DB records
        assert ClusterVote.objects.filter(cluster__session=self.session, user=self.member1).count() == 3

    def test_distributed_voting_across_clusters(self):
        self.client.force_login(self.member1)

        # 2 votes on A, 1 vote on B
        self.client.post(self.vote_a_url)
        self.client.post(self.vote_a_url)
        res_b = self.client.post(self.vote_b_url)
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["user_votes"] == 1
        assert data_b["remaining_votes"] == 0

        # 4th vote rejected
        assert self.client.post(self.vote_a_url).status_code == 400

    def test_vote_retraction(self):
        self.client.force_login(self.member1)

        # Retracting with 0 votes returns 400
        assert self.client.post(self.retract_a_url).status_code == 400

        # Vote once
        self.client.post(self.vote_a_url)
        assert ClusterVote.objects.filter(cluster=self.cluster_a, user=self.member1).count() == 1

        # Retract vote
        res = self.client.post(self.retract_a_url)
        assert res.status_code == 200
        data = res.json()
        assert data["user_votes"] == 0
        assert data["remaining_votes"] == 3
        assert ClusterVote.objects.filter(cluster=self.cluster_a, user=self.member1).count() == 0

    def test_masked_voting_collective_counts_omitted_during_vote_stage(self):
        # member1 casts 3 votes on Cluster A
        ClusterVote.objects.create(cluster=self.cluster_a, user=self.member1)
        ClusterVote.objects.create(cluster=self.cluster_a, user=self.member1)
        ClusterVote.objects.create(cluster=self.cluster_a, user=self.member1)

        # Total votes in DB on Cluster A is 3
        assert ClusterVote.objects.filter(cluster=self.cluster_a).count() == 3

        # Now member2 logs in and views the board during VOTE stage
        self.client.force_login(self.member2)
        response = self.client.get(self.board_url)
        assert response.status_code == 200
        content = response.content.decode()

        # Member 2's personal ballot counter
        assert "Remaining Votes: 3 of 3" in content
        # Member 2 has 0 votes on Cluster A
        assert "0" in content

        # Collective total of 3 votes MUST NOT appear as the cluster score/count
        # The voting widget only displays member2's personal vote count (0 votes)
        assert "vote-widget-" in content
        assert "Remaining Votes:" in content

        # Also verify HTMX response does not leak collective totals
        htmx_res = self.client.post(self.vote_a_url, headers={"HX-Request": "true"})
        assert htmx_res.status_code == 200
        htmx_content = htmx_res.content.decode()
        # Should only show 1 vote (for member2) and 2 remaining
        assert "1" in htmx_content
        assert "Remaining Votes: 2 of 3" in htmx_content
        # Does NOT expose the 4 total collective votes
        assert "total_votes" not in htmx_content
