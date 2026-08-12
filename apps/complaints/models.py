from django.conf import settings
from django.db import models
from django.utils import timezone


class Complaint(models.Model):
    # The four states an HOD works through, in workflow order. `escalated` is a
    # real status rather than a derived label so the review dropdown, the filter
    # tiles and the status pill all read from one vocabulary — they used to
    # disagree, with escalation visible only as a separate timestamp.
    class Status(models.TextChoices):
        UNREVIEWED = "unreviewed", "Unreviewed"
        REVIEWED = "reviewed", "Reviewed"
        ESCALATED = "escalated", "Escalated"
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
        max_length=16, choices=Status.choices, default=Status.UNREVIEWED
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
    # visible above the department. It is stamped once and never cleared: a
    # complaint the HOD later resolves stays on the VC's desk, which is why the
    # status moving off `escalated` does not take it back off.
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

    def mark_escalated(self, by=None) -> bool:
        """Stamp this complaint as escalated. True if this was the first stamp.

        Lives on the model because two views escalate — the button on the list,
        and picking "Escalated" in the review dropdown — and a rule copied into
        both drifts. Not in `save()`: that cannot see `request.user`, so it
        would leave rows the VC reads as "escalated by —".

        `escalated_at` is never rewritten, so a second press does not relabel
        who escalated it. The status only moves on the first stamp, and never
        off RESOLVED — reopening a closed complaint is a decision the HOD makes
        in the review form, not a side effect of attaching a note.
        """
        if self.escalated_at is not None:
            return False
        self.escalated_at = timezone.now()
        self.escalated_by = by
        if self.status != self.Status.RESOLVED:
            self.status = self.Status.ESCALATED
        return True

    @property
    def is_escalated(self) -> bool:
        # `escalated_at` stays the source of truth — it is what the VC console
        # filters on — but the status is checked too, so a row set to ESCALATED
        # in the admin (which cannot stamp a timestamp for you) still reads as
        # escalated in the templates.
        return self.escalated_at is not None or self.status == self.Status.ESCALATED

    @property
    def can_escalate(self) -> bool:
        """Whether the list page should offer an Escalate button on this row.

        Expressed here rather than as a status comparison in the template so the
        markup, `mark_escalated()` and the two views agree on one rule instead
        of three stringly-typed copies.
        """
        return not self.is_escalated and self.status != self.Status.RESOLVED

    def __str__(self) -> str:
        return f"{self.subject} ({self.get_status_display()})"
