from __future__ import annotations

import base64
import binascii
import re

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from .face_utils import FaceError, encode_face
from .forms import StudentRegistrationForm
from .models import StudentProfile, User


_DATA_URL_RE = re.compile(r"^data:image/(?:png|jpeg|jpg);base64,(?P<data>.+)$")


def _decode_data_url(data_url: str) -> bytes:
    match = _DATA_URL_RE.match(data_url.strip())
    if not match:
        raise ValueError("Face image was not captured. Allow camera access and try again.")
    try:
        return base64.b64decode(match.group("data"))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Captured face image is corrupted. Please retake.") from exc


class AppLoginView(LoginView):
    template_name = "auth/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if user.role == User.Role.STUDENT:
            return "/student/"
        if user.role in {User.Role.LECTURER, User.Role.COURSE_REP}:
            return "/lecturer/"
        if user.role == User.Role.HOD:
            return "/hod/"
        return "/admin/"


class AppLogoutView(LogoutView):
    next_page = "/auth/login/"


def register_student(request):
    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            try:
                image_bytes = _decode_data_url(form.cleaned_data["face_image_data"])
            except ValueError as exc:
                form.add_error(None, str(exc))
                return render(request, "auth/register_student.html", {"form": form})

            try:
                encoding_blob = encode_face(image_bytes)
            except FaceError as exc:
                form.add_error(None, str(exc))
                return render(request, "auth/register_student.html", {"form": form})

            try:
                with transaction.atomic():
                    user: User = form.save(commit=False)
                    user.role = User.Role.STUDENT
                    user.save()
                    profile = StudentProfile(
                        user=user,
                        matric_number=form.cleaned_data["matric_number"],
                        department=form.cleaned_data["department"],
                        level=form.cleaned_data.get("level", ""),
                        face_encoding=encoding_blob,
                    )
                    profile.face_image.save(
                        f"{user.username}.jpg", ContentFile(image_bytes), save=False
                    )
                    profile.save()
            except IntegrityError:
                form.add_error("matric_number", "That matric number is already registered.")
                return render(request, "auth/register_student.html", {"form": form})

            login(request, user)
            messages.success(request, "Registration successful — welcome!")
            return redirect("/student/")
    else:
        form = StudentRegistrationForm()
    return render(request, "auth/register_student.html", {"form": form})


@login_required
def student_dashboard(request):
    if request.user.role != User.Role.STUDENT:
        return redirect("/auth/login/")
    profile = getattr(request.user, "student_profile", None)
    enrollments = (
        profile.user.enrollments.select_related("course", "course__lecturer").all()
        if profile
        else []
    )
    attendance = (
        request.user.attendance_records.select_related("lecture", "lecture__course")
        .order_by("-marked_at")[:50]
    )
    return render(
        request,
        "student/dashboard.html",
        {"profile": profile, "enrollments": enrollments, "attendance": attendance},
    )


@login_required
def enroll(request, course_id: int):
    if request.user.role != User.Role.STUDENT:
        return redirect("/auth/login/")
    from apps.courses.models import Course, Enrollment

    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        messages.error(request, "Course not found.")
        return redirect("/student/")
    Enrollment.objects.get_or_create(student=request.user, course=course)
    messages.success(request, f"Enrolled in {course.code}.")
    return redirect("/student/")
