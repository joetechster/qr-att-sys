"""Helpers for the QR rotation invariant.

The lecture has at most one unused token. `current_token_for(lecture)` returns
that token, creating one if none exists. `rotate_token(lecture, used_token)`
marks the supplied token used and creates a fresh one — both done inside the
caller's transaction so the swap is atomic.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import Lecture, QRToken


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
    return QRToken.objects.create(lecture=lecture)
