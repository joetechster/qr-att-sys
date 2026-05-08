"""Helpers for the QR rotation invariant.

The lecture has at most one unused token. `current_token_for(lecture)` returns
that token, creating one if none exists. `rotate_token(lecture, used_token)`
marks the supplied token used and creates a fresh one — both done inside the
caller's transaction so the swap is atomic. After commit, the new token is
broadcast to the lecture's WebSocket group so any open displays rotate
immediately.
"""
from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from .models import Lecture, QRToken


def qr_group_name(lecture_id: int) -> str:
    return f"qr_lecture_{lecture_id}"


def user_can_run(user, lecture: Lecture) -> bool:
    """Whether `user` is allowed to drive this lecture (admin, lecturer, or rep)."""
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "role", None) == "admin":
        return True
    return user == lecture.course.lecturer or user == lecture.course.course_rep


def _broadcast(group: str, message: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(group, message)


def current_token_for(lecture: Lecture) -> QRToken:
    """Return the lecture's current unused token, creating one if needed."""
    token = (
        QRToken.objects.filter(lecture=lecture, is_used=False)
        .order_by("-created_at")
        .first()
    )
    if token is None:
        token = QRToken.objects.create(lecture=lecture)
    return token


@transaction.atomic
def rotate_token(lecture: Lecture, used_token: QRToken, used_by) -> QRToken:
    """Mark the supplied token used and return a freshly created replacement."""
    used_token.is_used = True
    used_token.used_by = used_by
    used_token.used_at = timezone.now()
    used_token.save(update_fields=("is_used", "used_by", "used_at"))
    # Defensive: invalidate any other lingering unused tokens for this lecture.
    QRToken.objects.filter(lecture=lecture, is_used=False).update(
        is_used=True, used_at=timezone.now()
    )
    new_token = QRToken.objects.create(lecture=lecture)

    # Push only after the surrounding transaction commits, so a rolled-back
    # scan doesn't leak a phantom rotation to the lecturer's screen.
    group = qr_group_name(lecture.id)
    new_token_value = str(new_token.token)
    transaction.on_commit(
        lambda: _broadcast(group, {"type": "token.rotated", "token": new_token_value})
    )
    return new_token


def broadcast_lecture_ended(lecture: Lecture) -> None:
    """Tell open QR displays that the lecture is over."""
    _broadcast(qr_group_name(lecture.id), {"type": "lecture.ended"})
