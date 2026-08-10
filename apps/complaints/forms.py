from django import forms
from django.contrib.auth import get_user_model

from apps.courses.models import Course

from .models import Complaint


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ("course", "lecturer", "subject", "body", "is_anonymous")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        if user is not None:
            enrolled_course_ids = user.enrollments.values_list("course_id", flat=True)
            self.fields["course"].queryset = Course.objects.filter(
                id__in=list(enrolled_course_ids)
            )
            self.fields["lecturer"].queryset = (
                User.objects.filter(
                    role="lecturer", courses_taught__id__in=list(enrolled_course_ids)
                ).distinct()
            )
        else:
            self.fields["course"].queryset = Course.objects.none()
            self.fields["lecturer"].queryset = User.objects.none()

        self.fields["course"].required = False
        self.fields["lecturer"].required = False
        self.fields["course"].empty_label = "— (not about a course) —"
        self.fields["lecturer"].empty_label = "— (not about a lecturer) —"

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("subject") and cleaned.get("body")):
            raise forms.ValidationError("Please provide both a subject and a description.")
        return cleaned


class ComplaintReviewForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ("status", "hod_response")
        widgets = {
            "hod_response": forms.Textarea(attrs={"rows": 5}),
        }


class EscalateComplaintForm(forms.ModelForm):
    """The HOD's note to the Vice Chancellor when pushing a complaint up."""

    class Meta:
        model = Complaint
        fields = ("escalation_note",)
        widgets = {
            "escalation_note": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Why does this need the VC's attention?"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["escalation_note"].required = False
