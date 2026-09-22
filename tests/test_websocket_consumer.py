"""Tests for Retrospective WebSocket Consumer and Channels Configuration."""
import datetime
import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from apps.cycles.models import FeedbackCycle
from apps.projects.models import Project, ProjectMember
from apps.retrospectives.models import RetrospectiveSession
from config.asgi import application

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestRetrospectiveConsumer:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.facilitator = User.objects.create_user(
            username="ws_facilitator", email="ws_fac@example.com", password="password123"
        )
        self.member = User.objects.create_user(
            username="ws_member", email="ws_mem@example.com", password="password123"
        )
        self.outsider = User.objects.create_user(
            username="ws_outsider", email="ws_out@example.com", password="password123"
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
            cycle=self.cycle, current_stage=RetrospectiveSession.Stage.REVEAL
        )

    def test_successful_connection_and_broadcast_reception(self):
        async def run():
            communicator = WebsocketCommunicator(application, f"/ws/retro/{self.cycle.id}/")
            communicator.scope["user"] = self.member

            connected, _ = await communicator.connect()
            assert connected is True

            # Send broadcast to the Redis room group
            channel_layer = get_channel_layer()
            event_payload = {
                "type": "board_event",
                "action": "stage_transition",
                "new_stage": "CLUSTER",
            }
            await channel_layer.group_send(f"retro_{self.cycle.id}", event_payload)

            # Receive JSON message on client
            received = await communicator.receive_json_from(timeout=3)
            assert received["type"] == "board_event"
            assert received["action"] == "stage_transition"
            assert received["new_stage"] == "CLUSTER"

            await communicator.disconnect()

        async_to_sync(run)()

    def test_unauthenticated_connection_rejected(self):
        async def run():
            communicator = WebsocketCommunicator(application, f"/ws/retro/{self.cycle.id}/")
            communicator.scope["user"] = AnonymousUser()

            connected, _ = await communicator.connect()
            assert connected is False

            await communicator.disconnect()

        async_to_sync(run)()

    def test_non_member_connection_rejected(self):
        async def run():
            communicator = WebsocketCommunicator(application, f"/ws/retro/{self.cycle.id}/")
            communicator.scope["user"] = self.outsider

            connected, _ = await communicator.connect()
            assert connected is False

            await communicator.disconnect()

        async_to_sync(run)()

    def test_non_existent_cycle_id_closed_cleanly(self):
        async def run():
            communicator = WebsocketCommunicator(application, "/ws/retro/999999/")
            communicator.scope["user"] = self.member

            connected, _ = await communicator.connect()
            assert connected is False

            await communicator.disconnect()

        async_to_sync(run)()

    def test_invalid_cycle_id_string_closed_cleanly(self):
        async def run():
            communicator = WebsocketCommunicator(application, "/ws/retro/invalid-cycle-id/")
            communicator.scope["user"] = self.member

            connected, _ = await communicator.connect()
            assert connected is False

            await communicator.disconnect()

        async_to_sync(run)()
