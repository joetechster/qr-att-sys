from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Lecture


class LectureForm(forms.ModelForm):
    MODE_EXISTING = "existing"
    MODE_NEW = "new"

    course_mode = forms.ChoiceField(
        choices=[
            (MODE_EXISTING, "Use an existing course"),
            (MODE_NEW, "Create a new course"),
        ],
        widget=forms.RadioSelect,
        initial=MODE_EXISTING,
    )
    new_course_code = forms.CharField(max_length=16, required=False)
    new_course_title = forms.CharField(max_length=128, required=False)
    new_course_department = forms.CharField(max_length=128, required=False)
    new_course_rep = forms.ModelChoiceField(queryset=None, required=False)

    class Meta:
        model = Lecture
        fields = ("course", "title", "scheduled_start", "scheduled_end")
        widgets = {
            "scheduled_start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "scheduled_end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.courses.models import Course

        User = get_user_model()
        self._user = user
        self.fields["new_course_rep"].queryset = User.objects.filter(role="course_rep")
        self.fields["course"].required = False
        if user is not None and user.role != "admin":
            self.fields["course"].queryset = Course.objects.filter(
                Q(lecturer=user) | Q(course_rep=user)
            )
        if user is not None and user.role != "lecturer":
            self.fields["course_mode"].choices = [
                (self.MODE_EXISTING, "Use an existing course")
            ]

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("course_mode") or self.MODE_EXISTING
        if mode == self.MODE_EXISTING:
            if not cleaned.get("course"):
                self.add_error("course", "Pick a course.")
            return cleaned

        if self._user is None or self._user.role != "lecturer":
            raise forms.ValidationError(
                "Only lecturers can create new courses inline."
            )

        from apps.courses.models import Course

        code = (cleaned.get("new_course_code") or "").strip()
        title = (cleaned.get("new_course_title") or "").strip()
        dept = (cleaned.get("new_course_department") or "").strip()
        if not (code and title and dept):
            raise forms.ValidationError(
                "Provide code, title, and department for the new course."
            )
        if Course.objects.filter(code=code).exists():
            self.add_error(
                "new_course_code", "A course with this code already exists."
            )
        return cleaned
