from django import forms
from django.db.models import Q

from .models import Lecture


class LectureForm(forms.ModelForm):
    class Meta:
        model = Lecture
        fields = ("course", "title", "scheduled_start", "scheduled_end")
        # "Topic", not "Title": the course picker right above renders each
        # course's own title, and two fields reading "Title" on one form is what
        # made this page confusing. The model field keeps its name.
        labels = {"title": "Topic"}
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Binary search trees"}),
            "scheduled_start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "scheduled_end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.courses.models import Course

        # Courses are created by the HOD; a lecturer may only schedule against
        # the ones they've been assigned to.
        if user is not None and user.role != "admin":
            self.fields["course"].queryset = Course.objects.filter(
                Q(lecturer=user) | Q(course_rep=user)
            )
        self.fields["course"].empty_label = "Select a course"

    def has_courses(self) -> bool:
        """Whether there is anything to schedule against at all."""
        return self.fields["course"].queryset.exists()
