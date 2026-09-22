"""Tests for Interactive Discussion Management and In-Meeting Notes."""
import datetime
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cycles.models import FeedbackCycle
from apps.projects.models import Project, ProjectMember
from apps.retrospectives.models import (
    DiscussionTopic,
    RetrospectiveSession,
    TopicCluster,
    TopicNote,
)

User = get_user_model()


@pytest.mark.django_db
class TestDiscussionManagement:
    @pytest.fixture(autouse=True)
    def setup_fixtures(self, client):
        self.client = client
        self.facilitator = User.objects.create_user(
            username="facilitator_emma", email="emma@example.com", password="password123"
        )
        self.member1 = User.objects.create_user(
            username="member_david", email="david@example.com", password="password123"
        )
        self.member2 = User.objects.create_user(
            username="member_grace", email="grace@example.com", password="password123"
        )
        self.outsider = User.objects.create_user(
            username="outsider_oscar", email="oscar@example.com", password="password123"
        )

        self.project = Project.objects.create(name="Epsilon", slug="epsilon", created_by=self.facilitator)
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
            cycle=self.cycle, current_stage=RetrospectiveSession.Stage.DISCUSS
        )

        self.cluster = TopicCluster.objects.create(session=self.session, title="Sprint Velocity Drop")
        self.topic = DiscussionTopic.objects.create(
            session=self.session,
            cluster=self.cluster,
            title=self.cluster.title,
            vote_count=5,
            order=1,
            status=DiscussionTopic.Status.PENDING,
        )

        self.board_url = reverse("retro_board", kwargs={"slug": self.project.slug, "pk": self.cycle.pk})
        self.status_url = reverse("topic_status_update", kwargs={"topic_id": self.topic.pk})
        self.note_create_url = reverse("topic_note_create", kwargs={"topic_id": self.topic.pk})

    def test_topic_note_model(self):
        note = TopicNote.objects.create(
            topic=self.topic,
            author=self.member1,
            text="Team agreed to break user stories into smaller 2-day chunks.",
        )
        assert note.pk is not None
        assert note.topic == self.topic
        assert note.author == self.member1
        assert note.text == "Team agreed to break user stories into smaller 2-day chunks."
        assert str(note) == f"Note by {self.member1.username} on Topic #{self.topic.order}"

    def test_facilitator_status_transition_via_htmx(self):
        self.client.force_login(self.facilitator)

        # Transition to DISCUSSED
        res = self.client.post(
            self.status_url,
            {"status": DiscussionTopic.Status.DISCUSSED},
            headers={"HX-Request": "true"},
        )
        assert res.status_code == 200
        content = res.content.decode()
        assert "Discussed" in content
        assert "bg-emerald-50" in content or "bg-emerald-600" in content

        self.topic.refresh_from_db()
        assert self.topic.status == DiscussionTopic.Status.DISCUSSED

        # Transition to SKIPPED
        res_skip = self.client.post(
            self.status_url,
            {"status": DiscussionTopic.Status.SKIPPED},
            headers={"HX-Request": "true"},
        )
        assert res_skip.status_code == 200
        self.topic.refresh_from_db()
        assert self.topic.status == DiscussionTopic.Status.SKIPPED

        # Transition to DEFERRED
        res_def = self.client.post(
            self.status_url,
            {"status": DiscussionTopic.Status.DEFERRED},
            headers={"HX-Request": "true"},
        )
        assert res_def.status_code == 200
        self.topic.refresh_from_db()
        assert self.topic.status == DiscussionTopic.Status.DEFERRED

    def test_non_facilitator_status_update_forbidden(self):
        # Regular project member gets 403
        self.client.force_login(self.member1)
        res_member = self.client.post(
            self.status_url,
            {"status": DiscussionTopic.Status.DISCUSSED},
            headers={"HX-Request": "true"},
        )
        assert res_member.status_code == 403

        # Non-project member gets 403
        self.client.force_login(self.outsider)
        res_outsider = self.client.post(
            self.status_url,
            {"status": DiscussionTopic.Status.DISCUSSED},
        )
        assert res_outsider.status_code == 403

        self.topic.refresh_from_db()
        assert self.topic.status == DiscussionTopic.Status.PENDING

    def test_status_controls_visibility_on_discuss_stage(self):
        # Facilitator sees status buttons
        self.client.force_login(self.facilitator)
        res_fac = self.client.get(self.board_url)
        assert res_fac.status_code == 200
        content_fac = res_fac.content.decode()
        assert "Mark as:" in content_fac
        assert "Discussed" in content_fac

        # Member does not see status action buttons
        self.client.force_login(self.member1)
        res_mem = self.client.get(self.board_url)
        assert res_mem.status_code == 200
        content_mem = res_mem.content.decode()
        assert "Mark as:" not in content_mem

    def test_member_can_create_in_meeting_note(self):
        self.client.force_login(self.member1)
        note_text = "Action item: Tech lead will schedule refinement sessions twice a week."

        res = self.client.post(
            self.note_create_url,
            {"text": note_text},
            headers={"HX-Request": "true"},
        )
        assert res.status_code == 200
        content = res.content.decode()

        assert note_text in content
        assert self.member1.username in content

        # Check DB
        note = TopicNote.objects.filter(topic=self.topic).first()
        assert note is not None
        assert note.author == self.member1
        assert note.text == note_text

    def test_empty_note_rejected_with_inline_error(self):
        self.client.force_login(self.member1)

        res = self.client.post(
            self.note_create_url,
            {"text": "   "},
            headers={"HX-Request": "true"},
        )
        assert res.status_code == 422
        content = res.content.decode()
        assert "Note cannot be blank" in content
        assert TopicNote.objects.filter(topic=self.topic).count() == 0

    def test_note_deletion_authorization(self):
        note = TopicNote.objects.create(
            topic=self.topic,
            author=self.member1,
            text="Initial note to be deleted.",
        )
        delete_url = reverse("topic_note_delete", kwargs={"note_id": note.pk})

        # Another member cannot delete member1's note
        self.client.force_login(self.member2)
        res_mem2 = self.client.post(delete_url, headers={"HX-Request": "true"})
        assert res_mem2.status_code == 403
        assert TopicNote.objects.filter(pk=note.pk).exists()

        # Facilitator CAN delete any note
        self.client.force_login(self.facilitator)
        res_fac = self.client.post(delete_url, headers={"HX-Request": "true"})
        assert res_fac.status_code == 200
        assert not TopicNote.objects.filter(pk=note.pk).exists()

        # Author can delete their own note
        note2 = TopicNote.objects.create(
            topic=self.topic,
            author=self.member1,
            text="Author deletion test note.",
        )
        delete_url2 = reverse("topic_note_delete", kwargs={"note_id": note2.pk})
        self.client.force_login(self.member1)
        res_author = self.client.post(delete_url2, headers={"HX-Request": "true"})
        assert res_author.status_code == 200
        assert not TopicNote.objects.filter(pk=note2.pk).exists()

    def test_locking_in_summary_and_completed_stages(self):
        # Move session stage to SUMMARY
        self.session.current_stage = RetrospectiveSession.Stage.SUMMARY
        self.session.save()

        self.client.force_login(self.facilitator)

        # Status update rejected
        status_res = self.client.post(
            self.status_url,
            {"status": DiscussionTopic.Status.DISCUSSED},
            headers={"HX-Request": "true"},
        )
        assert status_res.status_code == 403

        # Note creation rejected
        note_res = self.client.post(
            self.note_create_url,
            {"text": "Late note attempt"},
            headers={"HX-Request": "true"},
        )
        assert note_res.status_code == 403

        # Test locked UI rendering
        board_res = self.client.get(self.board_url + "?stage=DISCUSS")
        assert board_res.status_code == 200
        board_content = board_res.content.decode()
        assert "Session is completed or locked" in board_content
        assert "Mark as:" not in board_content
