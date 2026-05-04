from django import forms
from django.db.models import Q

from .models import Lecture


class LectureForm(forms.ModelForm):
    class Meta:
        model = Lecture
        fields = ("course", "title", "scheduled_start", "scheduled_end")
        widgets = {
            "scheduled_start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "scheduled_end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and user.role != "admin":
            from apps.courses.models import Course

            self.fields["course"].queryset = Course.objects.filter(
                Q(lecturer=user) | Q(course_rep=user)
            )
