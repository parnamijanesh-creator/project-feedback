"""Tests for manual cluster organization, CRUD operations, and unclustered cards pool."""
import datetime
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.projects.models import Project, ProjectMember
from apps.cycles.models import FeedbackCycle, FeedbackCard
from apps.retrospectives.models import RetrospectiveSession, TopicCluster

User = get_user_model()


@pytest.mark.django_db
class TestClusterCRUD:
    @pytest.fixture(autouse=True)
    def setup_fixtures(self, client):
        self.client = client
        self.facilitator = User.objects.create_user(
            username="facilitator_sam", email="sam@example.com", password="password123"
        )
        self.member = User.objects.create_user(
            username="member_tina", email="tina@example.com", password="password123"
        )
        self.outsider = User.objects.create_user(
            username="outsider_uma", email="uma@example.com", password="password123"
        )

        self.project = Project.objects.create(name="Epsilon", slug="epsilon", created_by=self.facilitator)
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

        self.board_url = reverse("retro_board", kwargs={"slug": self.project.slug, "pk": self.cycle.pk})
        self.create_url = reverse("cluster_create", kwargs={"slug": self.project.slug, "pk": self.cycle.pk})

    def test_board_in_cluster_stage_displays_clusters_and_unclustered_pool(self):
        # Create one cluster with a card, and one unclustered card
        cluster = TopicCluster.objects.create(session=self.session, title="DevOps Friction")
        clustered_card = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.START,
            text="Improve deployment script",
            cluster=cluster,
        )
        unclustered_card = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.STOP,
            text="Stop deploying on Friday afternoons",
            cluster=None,
        )

        self.client.force_login(self.member)
        response = self.client.get(self.board_url)
        assert response.status_code == 200
        content = response.content.decode()

        # Both cluster container and unclustered pool are rendered
        assert "DevOps Friction" in content
        assert "Improve deployment script" in content
        assert "Unclustered Cards Pool" in content
        assert "Stop deploying on Friday afternoons" in content

    def test_cluster_creation_success_htmx(self):
        self.client.force_login(self.member)
        response = self.client.post(
            self.create_url,
            {"title": "Team Communication"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        content = response.content.decode()

        # Returns cluster item partial with title
        assert "Team Communication" in content
        assert "cluster-" in content

        # Check DB
        cluster = TopicCluster.objects.filter(session=self.session, title="Team Communication").first()
        assert cluster is not None
        assert cluster.is_ai_generated is False

    def test_cluster_creation_blank_title_validation_error(self):
        self.client.force_login(self.member)
        response = self.client.post(
            self.create_url,
            {"title": "   "},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 422
        content = response.content.decode()
        assert "Cluster title cannot be blank" in content
        assert TopicCluster.objects.filter(session=self.session).count() == 0

    def test_cluster_inline_update(self):
        cluster = TopicCluster.objects.create(session=self.session, title="Old Title")
        update_url = reverse(
            "cluster_update",
            kwargs={"slug": self.project.slug, "pk": self.cycle.pk, "cluster_id": cluster.pk},
        )

        self.client.force_login(self.member)

        # GET returns inline form
        get_res = self.client.get(update_url)
        assert get_res.status_code == 200
        assert "Old Title" in get_res.content.decode()
        assert "<form" in get_res.content.decode()

        # POST with empty title returns validation error
        err_res = self.client.post(update_url, {"title": "  "})
        assert err_res.status_code == 422
        assert "Title cannot be blank" in err_res.content.decode()

        # POST with valid title updates database
        post_res = self.client.post(update_url, {"title": "Updated Brand New Title"})
        assert post_res.status_code == 200
        assert "Updated Brand New Title" in post_res.content.decode()

        cluster.refresh_from_db()
        assert cluster.title == "Updated Brand New Title"

    def test_cluster_title_cancel_view(self):
        cluster = TopicCluster.objects.create(session=self.session, title="Preserved Title")
        title_url = reverse(
            "cluster_title",
            kwargs={"slug": self.project.slug, "pk": self.cycle.pk, "cluster_id": cluster.pk},
        )
        self.client.force_login(self.member)
        response = self.client.get(title_url)
        assert response.status_code == 200
        assert "Preserved Title" in response.content.decode()

    def test_cluster_deletion_reassigns_cards_to_unclustered_pool(self):
        cluster = TopicCluster.objects.create(session=self.session, title="To Be Deleted")
        card1 = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.START,
            text="Card to be dislodged",
            cluster=cluster,
        )
        card2 = FeedbackCard.objects.create(
            cycle=self.cycle,
            category=FeedbackCard.Category.STOP,
            text="Second card to be dislodged",
            cluster=cluster,
        )

        delete_url = reverse(
            "cluster_delete",
            kwargs={"slug": self.project.slug, "pk": self.cycle.pk, "cluster_id": cluster.pk},
        )

        self.client.force_login(self.member)
        response = self.client.post(delete_url, headers={"HX-Request": "true"})
        assert response.status_code == 200

        # Cluster row is deleted
        assert TopicCluster.objects.filter(pk=cluster.pk).count() == 0

        # Cards are NOT deleted; cluster is set to None
        card1.refresh_from_db()
        card2.refresh_from_db()
        assert card1.cluster is None
        assert card2.cluster is None

        # OOB swap contains dislodged cards in the unclustered pool
        content = response.content.decode()
        assert 'id="unclustered-pool"' in content
        assert "Card to be dislodged" in content
        assert "Second card to be dislodged" in content

    def test_non_member_forbidden_on_all_cluster_operations(self):
        cluster = TopicCluster.objects.create(session=self.session, title="Protected Cluster")
        update_url = reverse(
            "cluster_update",
            kwargs={"slug": self.project.slug, "pk": self.cycle.pk, "cluster_id": cluster.pk},
        )
        delete_url = reverse(
            "cluster_delete",
            kwargs={"slug": self.project.slug, "pk": self.cycle.pk, "cluster_id": cluster.pk},
        )

        self.client.force_login(self.outsider)

        # Create
        assert self.client.post(self.create_url, {"title": "Hack"}).status_code == 403
        # Update
        assert self.client.post(update_url, {"title": "Hack"}).status_code == 403
        # Delete
        assert self.client.post(delete_url).status_code == 403

    def test_completed_cycle_blocks_cluster_mutations(self):
        self.cycle.status = FeedbackCycle.Status.COMPLETED
        self.cycle.save()

        cluster = TopicCluster.objects.create(session=self.session, title="Locked Cluster")
        update_url = reverse(
            "cluster_update",
            kwargs={"slug": self.project.slug, "pk": self.cycle.pk, "cluster_id": cluster.pk},
        )
        delete_url = reverse(
            "cluster_delete",
            kwargs={"slug": self.project.slug, "pk": self.cycle.pk, "cluster_id": cluster.pk},
        )

        self.client.force_login(self.facilitator)

        # Attempting create, update, or delete on COMPLETED cycle returns 403 Forbidden
        assert self.client.post(self.create_url, {"title": "New"}).status_code == 403
        assert self.client.post(update_url, {"title": "New"}).status_code == 403
        assert self.client.post(delete_url).status_code == 403

    def test_facilitator_stage_transition(self):
        stage_url = reverse(
            "retro_stage_transition",
            kwargs={"slug": self.project.slug, "pk": self.cycle.pk},
        )

        # Non-facilitator receives 403
        self.client.force_login(self.member)
        assert self.client.post(stage_url, {"stage": "VOTE"}).status_code == 403

        # Facilitator can transition
        self.client.force_login(self.facilitator)
        res = self.client.post(stage_url, {"stage": "VOTE"}, follow=True)
        assert res.status_code == 200

        self.session.refresh_from_db()
        assert self.session.current_stage == RetrospectiveSession.Stage.VOTE
