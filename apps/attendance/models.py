from django.conf import settings
from django.db import models


class AttendanceRecord(models.Model):
    lecture = models.ForeignKey(
        "lectures.Lecture", on_delete=models.CASCADE, related_name="attendance_records"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    qr_token = models.ForeignKey(
        "lectures.QRToken",
        on_delete=models.PROTECT,
        related_name="attendance_record",
        null=True,
        blank=True,
    )
    face_match_distance = models.FloatField()
    marked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("lecture", "student"),)
        ordering = ("-marked_at",)

    def __str__(self) -> str:
        return f"{self.student} present @ {self.lecture}"
