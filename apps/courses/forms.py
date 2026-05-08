from django import forms
from django.contrib.auth import get_user_model

from .models import Course


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ("code", "title", "department", "course_rep")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields["course_rep"].queryset = User.objects.filter(role="course_rep")
        self.fields["course_rep"].required = False
