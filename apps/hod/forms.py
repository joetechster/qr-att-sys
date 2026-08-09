from django import forms

from apps.accounts.models import User


MAX_CSV_BYTES = 2 * 1024 * 1024


class LecturerCreateForm(forms.ModelForm):
    """Provision a single lecturer account.

    No password field: the view generates a temporary one and shows it to the
    HOD once, since there is no mail backend configured.
    """

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].required = False

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username


class CsvUploadForm(forms.Form):
    file = forms.FileField(label="CSV file")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a .csv file.")
        if upload.size > MAX_CSV_BYTES:
            raise forms.ValidationError("File is too large (2 MB maximum).")
        return upload
