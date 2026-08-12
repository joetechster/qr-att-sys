from django import forms
from django.contrib.auth import get_user_model

from .departments import DEPARTMENT_CHOICES, DEPARTMENT_NAMES
from .models import Course


# Without an empty first option the browser preselects the first real
# department, and a distracted HOD files every new course under Cybersecurity.
# Mirrors the `empty_label` set on the two model choice fields below.
_BLANK_DEPARTMENT = (("", "Select a department"),)


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
    # Declared for the same reason as `unit`: the model column stays a plain
    # CharField so legacy values remain storable, and the vocabulary is enforced
    # here, where the escape hatch in `_department_choices` can reach it.
    department = forms.ChoiceField(label="Department", choices=DEPARTMENT_CHOICES)

    class Meta:
        model = Course
        fields = ("code", "title", "unit", "department", "lecturer", "course_rep")

    def _department_choices(self) -> tuple:
        """Keep the edit form usable for a course filed under a department that
        predates this list.

        Courses seeded before the vocabulary existed hold values like
        "Mathematics" or "General Studies". A strict ChoiceField would refuse to
        save such a course even when the HOD only came here to reassign its
        lecturer, so the stored value is offered back in a group of its own —
        visibly apart from the real faculties, so picking a proper department is
        the obvious move.
        """
        current = getattr(self.instance, "department", "") or ""
        if current and current not in DEPARTMENT_NAMES:
            return (("Currently set", ((current, current),)),) + DEPARTMENT_CHOICES
        return DEPARTMENT_CHOICES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        # Set here rather than on the field above because the escape hatch has
        # to see `self.instance`. On a bound POST the instance still holds the
        # stored value at this point — it is not overwritten until _post_clean.
        self.fields["department"].choices = (
            _BLANK_DEPARTMENT + self._department_choices()
        )
        # The HOD owns the catalogue, so the lecturer is assigned here rather
        # than taken from request.user.
        self.fields["lecturer"].queryset = User.objects.filter(role="lecturer")
        self.fields["lecturer"].empty_label = "Select a lecturer"
        self.fields["course_rep"].queryset = User.objects.filter(role="course_rep")
        self.fields["course_rep"].required = False
