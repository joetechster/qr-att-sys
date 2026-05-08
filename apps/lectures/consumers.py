from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Lecture
from .services import current_token_for, user_can_run


class QRDisplayConsumer(AsyncJsonWebsocketConsumer):
    """Pushes QR token rotations to a lecturer's display page.

    Group name: ``qr_lecture_<lecture_id>``. The group receives:
      - ``{"type": "token.rotated", "token": <uuid str>}`` after each scan
      - ``{"type": "lecture.ended"}`` when the lecture ends
    """

    async def connect(self):
        self.lecture_id = self.scope["url_route"]["kwargs"]["lecture_id"]
        self.group_name = f"qr_lecture_{self.lecture_id}"

        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        lecture = await self._authorized_lecture(user, self.lecture_id)
        if lecture is None:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial state so a freshly-loaded page renders without waiting.
        if lecture.status == Lecture.Status.ACTIVE:
            token = await self._current_token(lecture)
            await self.send_json({"status": "active", "token": str(token.token)})
        else:
            await self.send_json({"status": lecture.status, "token": None})

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def token_rotated(self, event):
        await self.send_json({"status": "active", "token": event["token"]})

    async def lecture_ended(self, event):
        await self.send_json({"status": "ended", "token": None})

    @database_sync_to_async
    def _authorized_lecture(self, user, lecture_id):
        lecture = (
            Lecture.objects.select_related("course", "course__lecturer", "course__course_rep")
            .filter(pk=lecture_id)
            .first()
        )
        if lecture is None:
            return None
        if not getattr(user, "is_privileged", False):
            return None
        if not user_can_run(user, lecture):
            return None
        return lecture

    @database_sync_to_async
    def _current_token(self, lecture):
        return current_token_for(lecture)
