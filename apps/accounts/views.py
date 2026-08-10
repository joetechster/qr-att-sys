from __future__ import annotations

import base64
import binascii
import re

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .decorators import role_required
from .face_utils import FaceError, encode_face
from .forms import AppPasswordChangeForm, ProfileForm, StudentRegistrationForm
from .models import StudentProfile, User
from .roles import role_home


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

    # Deliberately NOT redirect_authenticated_user. A browser keeps one session
    # for every tab, so signing in here reassigns any other tab too. Showing the
    # form with a "you're already signed in as X" banner makes that visible;
    # auto-redirecting to the current role's dashboard is what made switching
    # accounts feel like the app was bouncing at random.

    def get_success_url(self):
        return role_home(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context["already_signed_in"] = self.request.user
            context["role_home"] = role_home(self.request.user)
        return context


class AppLogoutView(LogoutView):
    next_page = "/auth/login/"


class AppPasswordChangeView(PasswordChangeView):
    """Also the landing page for staff still holding a temporary password."""

    template_name = "auth/password_change.html"
    form_class = AppPasswordChangeForm
    success_url = reverse_lazy("profile")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["forced"] = user.must_change_password
        # For the client-side similarity check. These fields aren't on this page
        # the way they are on registration, so hand them to the browser directly.
        context["related_terms"] = [
            term for term in (user.username, user.first_name, user.last_name, user.email) if term
        ]
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.user.must_change_password:
            self.request.user.must_change_password = False
            self.request.user.save(update_fields=("must_change_password",))
        messages.success(self.request, "Password updated.")
        return response


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(
        request,
        "auth/profile.html",
        {"form": form, "student_profile": getattr(request.user, "student_profile", None)},
    )


def register_student(request):
    # Signing up while signed in would silently swap the session for a brand-new
    # account, so send existing users to their own dashboard instead.
    if request.user.is_authenticated:
        return redirect(role_home(request.user))

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
            return redirect(role_home(user))
    else:
        form = StudentRegistrationForm()
    return render(request, "auth/register_student.html", {"form": form})


@role_required(User.Role.STUDENT)
def student_dashboard(request):
    from apps.courses.models import Enrollment
    from apps.lectures.models import Lecture
    from apps.lectures.services import expire_due_lectures

    profile = getattr(request.user, "student_profile", None)

    # Close out anything whose window has passed before the counts below are
    # taken: "held" is derived from ENDED lectures, so a finished lecture nobody
    # has revisited would otherwise be missing from the student's denominator.
    expire_due_lectures(
        Lecture.objects.filter(course__enrollments__student=request.user).distinct()
    )

    # "Held" can only be derived: there are no absence rows, a record's mere
    # existence means present. Only ENDED lectures count — an ACTIVE one is
    # still running, and marking a student absent for a class they're walking
    # into would be wrong. Filtering *both* sides to ENDED also means attended
    # is always a subset of held, so a late enrolment can't exceed 100%.
    ended = Lecture.Status.ENDED
    enrollments = (
        Enrollment.objects.filter(student=request.user)
        .select_related("course", "course__lecturer")
        .annotate(
            # distinct=True on both: two Counts over the same multi-valued join
            # otherwise multiply each other's rows.
            held=Count(
                "course__lectures",
                filter=Q(course__lectures__status=ended),
                distinct=True,
            ),
            attended=Count(
                "course__lectures__attendance_records",
                filter=Q(
                    course__lectures__status=ended,
                    course__lectures__attendance_records__student=request.user,
                ),
                distinct=True,
            ),
        )
        .order_by("course__code")
    )

    rows, total_held, total_attended = [], 0, 0
    for enrollment in enrollments:
        rows.append(
            {
                "course": enrollment.course,
                "held": enrollment.held,
                "attended": enrollment.attended,
                "percent": (
                    round(enrollment.attended * 100 / enrollment.held)
                    if enrollment.held
                    else None
                ),
            }
        )
        total_held += enrollment.held
        total_attended += enrollment.attended

    attendance = (
        request.user.attendance_records.select_related("lecture", "lecture__course")
        .order_by("-marked_at")[:50]
    )
    return render(
        request,
        "student/dashboard.html",
        {
            "profile": profile,
            "rows": rows,
            "course_count": len(rows),
            "total_held": total_held,
            "total_attended": total_attended,
            "overall_percent": (
                round(total_attended * 100 / total_held) if total_held else None
            ),
            "attendance": attendance,
        },
    )


@role_required(User.Role.STUDENT)
def enroll(request, course_id: int):
    from apps.courses.models import Course, Enrollment

    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        messages.error(request, "Course not found.")
        return redirect("/student/")
    Enrollment.objects.get_or_create(student=request.user, course=course)
    messages.success(request, f"Enrolled in {course.code}.")
    return redirect("/student/")
