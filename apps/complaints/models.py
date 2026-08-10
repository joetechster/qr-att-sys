from django.conf import settings
from django.db import models


class Complaint(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"
        RESOLVED = "resolved", "Resolved"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="complaints_filed",
        limit_choices_to={"role": "student"},
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints",
    )
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints_against",
        limit_choices_to={"role": "lecturer"},
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    is_anonymous = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUBMITTED
    )
    hod_response = models.TextField(blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints_handled",
        limit_choices_to={"role": "hod"},
    )
    # Set when the HOD pushes a complaint up to the Vice Chancellor. The VC's
    # console shows nothing else, so `escalated_at` is what makes a complaint
    # visible above the department.
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints_escalated",
        limit_choices_to={"role": "hod"},
    )
    escalation_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_escalated(self) -> bool:
        return self.escalated_at is not None

    def __str__(self) -> str:
        return f"{self.subject} ({self.get_status_display()})"
