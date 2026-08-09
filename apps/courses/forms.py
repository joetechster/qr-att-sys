from django import forms
from django.contrib.auth import get_user_model

from .models import Course


class CourseForm(forms.ModelForm):
    # Declared rather than left to the ModelForm: the model permits 0 so courses
    # that predate the `unit` field stay valid, but anything typed in here has to
    # carry a real credit load. Declaring it is also the only way the bounds
    # actually become validators — assigning min_value after __init__ does not.
    unit = forms.IntegerField(
        min_value=1,
        max_value=12,
        label="Unit",
        help_text="Credit units, 1 to 12.",
        widget=forms.NumberInput(attrs={"min": 1, "max": 12, "step": 1}),
    )

    class Meta:
        model = Course
        fields = ("code", "title", "unit", "department", "lecturer", "course_rep")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        # The HOD owns the catalogue, so the lecturer is assigned here rather
        # than taken from request.user.
        self.fields["lecturer"].queryset = User.objects.filter(role="lecturer")
        self.fields["lecturer"].empty_label = "Select a lecturer"
        self.fields["course_rep"].queryset = User.objects.filter(role="course_rep")
        self.fields["course_rep"].required = False
