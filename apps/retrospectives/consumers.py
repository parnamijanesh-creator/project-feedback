"""WebSocket consumers for real-time retrospective board collaboration."""
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.cycles.models import FeedbackCycle
from apps.projects.models import ProjectMember


class RetrospectiveConsumer(AsyncJsonWebsocketConsumer):
    """Consumer handling live room subscriptions and broadcasts for a feedback cycle's retro."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.cycle_id = self.scope["url_route"]["kwargs"].get("cycle_id")
        cycle, is_member = await self._validate_access(self.cycle_id, user)

        if not cycle or not is_member:
            await self.close(code=4403)
            return

        self.room_group_name = f"retro_{self.cycle_id}"
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name") and self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        """Handle incoming messages from WebSocket client if needed."""
        pass

    async def board_event(self, event):
        """Typed broadcast handler forwarding board events to connected WebSocket clients."""
        await self.send_json(event)

    @database_sync_to_async
    def _validate_access(self, cycle_id, user):
        try:
            cid = int(cycle_id)
        except (ValueError, TypeError):
            return None, False

        try:
            cycle = FeedbackCycle.objects.select_related("project").get(pk=cid)
        except FeedbackCycle.DoesNotExist:
            return None, False

        is_member = ProjectMember.objects.filter(project=cycle.project, user=user).exists()
        return cycle, is_member
