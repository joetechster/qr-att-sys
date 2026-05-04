from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class StudentRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=64)
    last_name = forms.CharField(max_length=64)
    email = forms.EmailField(required=False)
    matric_number = forms.CharField(max_length=32)
    department = forms.CharField(max_length=128)
    level = forms.CharField(max_length=8, required=False)
    # Hidden field populated by the face-capture JS with a base64 dataURL.
    face_image_data = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")
