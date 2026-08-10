from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        LECTURER = "lecturer", "Lecturer"
        COURSE_REP = "course_rep", "Course Rep"
        STUDENT = "student", "Student"
        HOD = "hod", "Head of Department"
        # 15 characters — the role column is max_length=16, so this fits without
        # widening it.
        VICE_CHANCELLOR = "vice_chancellor", "Vice Chancellor"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STUDENT)
    # Set when an account is provisioned with a temporary password (staff created
    # by the HOD). ForcePasswordChangeMiddleware pins the user to the password
    # change page until they clear it.
    must_change_password = models.BooleanField(default=False)

    @property
    def is_privileged(self) -> bool:
        return self.role in {self.Role.ADMIN, self.Role.LECTURER, self.Role.COURSE_REP}

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    matric_number = models.CharField(max_length=32, unique=True)
    department = models.CharField(max_length=128)
    level = models.CharField(max_length=8, blank=True)
    face_image = models.ImageField(upload_to="faces/")
    # Pickled 128-d numpy float64 vector returned by face_recognition.face_encodings().
    face_encoding = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.matric_number} — {self.user.get_full_name() or self.user.username}"
