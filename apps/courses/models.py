from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models


class Course(models.Model):
    code = models.CharField(max_length=16, unique=True)
    title = models.CharField(max_length=128)
    # 0 means "not recorded" — it keeps courses that predate this field valid
    # under full_clean() instead of forcing a made-up credit load onto them.
    # Both the form and the CSV importer require 1-12 for anything new.
    unit = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(12)],
        help_text="Credit units.",
    )
    department = models.CharField(max_length=128)
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="courses_taught",
        limit_choices_to={"role": "lecturer"},
    )
    course_rep = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses_repped",
        limit_choices_to={"role": "course_rep"},
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return f"{self.code} — {self.title}"


class Enrollment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("student", "course"),)

    def __str__(self) -> str:
        return f"{self.student} → {self.course.code}"
