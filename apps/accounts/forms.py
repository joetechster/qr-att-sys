from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.core.exceptions import ValidationError

from .models import User


LEVEL_CHOICES = (
    ("", "Select level"),
    ("100", "100 Level"),
    ("200", "200 Level"),
    ("300", "300 Level"),
    ("400", "400 Level"),
    ("500", "500 Level"),
    ("600", "600 Level"),
)

# The registration form is validated live in the browser by form_validate.js, which
# leans on native constraint attributes so the rules live here and only here. Keep
# every attribute at least as strict as the matching Django validator: a rule that is
# looser would hand out a green checkmark the server then rejects.
USERNAME_PATTERN = r"[A-Za-z0-9_.@+\-]+"


class StudentRegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=64,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Ada",
                "autocomplete": "given-name",
                "autofocus": True,
                "required": True,
                "maxlength": 64,
            }
        ),
    )
    last_name = forms.CharField(
        max_length=64,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Okafor",
                "autocomplete": "family-name",
                "required": True,
                "maxlength": 64,
            }
        ),
    )
    email = forms.EmailField(
        required=False,
        label="Email (optional)",
        widget=forms.EmailInput(
            attrs={"placeholder": "you@pcu.edu.ng", "autocomplete": "email"}
        ),
    )
    matric_number = forms.CharField(
        max_length=32,
        help_text="Exactly as printed on your ID card.",
        widget=forms.TextInput(
            attrs={
                "placeholder": "PCU/CSC/21/0001",
                "autocomplete": "off",
                "required": True,
                "maxlength": 32,
            }
        ),
    )
    department = forms.CharField(
        max_length=128,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Computer Science",
                "autocomplete": "organization",
                "required": True,
                "maxlength": 128,
            }
        ),
    )
    level = forms.ChoiceField(choices=LEVEL_CHOICES, required=False)
    # Hidden field populated by the face-capture JS with a base64 dataURL. Optional at
    # the field level so the friendlier message in clean_face_image_data is what the
    # student actually sees — "This field is required." would render against a hidden
    # input and be invisible.
    face_image_data = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Letters, digits and . @ + - _ only."
        self.fields["username"].widget.attrs.update(
            {
                "placeholder": "ada.okafor",
                "autocomplete": "username",
                "required": True,
                "maxlength": 150,
                "pattern": USERNAME_PATTERN,
                "title": "Letters, digits and . @ + - _ only.",
            }
        )
        # UserCreationForm autofocuses the username; first name is what the student
        # sees first, and two autofocused inputs on one page is a bug either way.
        self.fields["username"].widget.attrs.pop("autofocus", None)

        self.fields["password1"].help_text = "At least 8 characters, not all digits."
        self.fields["password2"].label = "Confirm password"
        # The browser checks the match live, so Django's "enter the same password as
        # before" note is just noise under the field.
        self.fields["password2"].help_text = ""
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.update(
                {
                    "placeholder": "••••••••",
                    "autocomplete": "new-password",
                    "required": True,
                    "minlength": 8,
                }
            )

    def _post_clean(self):
        # UserCreationForm reports password-strength failures against password2, and
        # skips them entirely when the two passwords differ. Both are wrong for this
        # page: the complaint is about the password itself — the field the browser's
        # live check flags — and a student with a weak *and* mistyped password should
        # see both problems in one pass.
        super(UserCreationForm, self)._post_clean()
        password = self.cleaned_data.get("password1")
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except ValidationError as error:
                self.add_error("password1", error)

    def clean_face_image_data(self):
        data = (self.cleaned_data.get("face_image_data") or "").strip()
        if not data:
            raise forms.ValidationError(
                "Take a photo of yourself before creating your account."
            )
        return data


class AppPasswordChangeForm(PasswordChangeForm):
    """Stock behaviour, but with the attributes the live checker needs.

    Django's own form ships bare widgets, so the password-change page had no
    placeholders, no autocomplete hints and no `minlength` for form_validate.js
    to read. Its default help_text is also the full four-bullet validator dump,
    which the criteria checklist now says better.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Current password"
        self.fields["old_password"].widget.attrs.update(
            {"placeholder": "••••••••", "autocomplete": "current-password", "required": True}
        )
        self.fields["new_password1"].label = "New password"
        self.fields["new_password1"].help_text = "At least 8 characters, not all digits."
        self.fields["new_password2"].label = "Confirm new password"
        self.fields["new_password2"].help_text = ""
        for name in ("new_password1", "new_password2"):
            self.fields[name].widget.attrs.update(
                {
                    "placeholder": "••••••••",
                    "autocomplete": "new-password",
                    "required": True,
                    "minlength": 8,
                }
            )


class ProfileForm(forms.ModelForm):
    """The bits of a user record anyone is allowed to edit about themselves."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
