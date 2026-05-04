import uuid

from django.conf import settings
from django.db import models


class Lecture(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="lectures"
    )
    title = models.CharField(max_length=128)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lectures_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-scheduled_start",)

    def __str__(self) -> str:
        return f"{self.course.code} — {self.title}"


class QRToken(models.Model):
    """Per-lecture rotating one-shot token.

    Invariant: at most one row per lecture has is_used=False at any time
    (the "current" QR). Concurrent scans contend on this row via
    select_for_update() in the scan/verify view.
    """

    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name="qr_tokens")
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    is_used = models.BooleanField(default=False)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consumed_qr_tokens",
    )
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("lecture", "is_used"))]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.token} (used={self.is_used})"
