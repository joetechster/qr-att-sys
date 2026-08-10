from __future__ import annotations

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from apps.accounts.models import User
from apps.courses.models import Course

from .forms import LectureForm
from .models import Lecture
from .services import (
    current_token_for,
    end_lecture_now,
    expire_due_lectures,
    expire_if_due,
    is_past_end,
    user_can_run,
)


# Mirrors User.is_privileged. Anonymous users are handled by the gate itself,
# so these views no longer stack @login_required on top.
privileged_required = role_required(
    User.Role.ADMIN, User.Role.LECTURER, User.Role.COURSE_REP
)


@privileged_required
def lecturer_dashboard(request):
    user = request.user
    if user.role == "admin":
        expire_due_lectures()
        courses = Course.objects.all()
        lectures = Lecture.objects.select_related("course").all()[:50]
    else:
        courses = Course.objects.filter(Q(lecturer=user) | Q(course_rep=user))
        mine = Lecture.objects.filter(
            Q(course__lecturer=user) | Q(course__course_rep=user)
        )
        expire_due_lectures(mine)
        lectures = mine.select_related("course")[:50]
    return render(
        request,
        "lecturer/dashboard.html",
        {"courses": courses, "lectures": lectures},
    )


@privileged_required
def create_lecture(request):
    if request.method == "POST":
        form = LectureForm(request.POST, user=request.user)
        if form.is_valid():
            lecture: Lecture = form.save(commit=False)
            lecture.created_by = request.user
            lecture.save()
            messages.success(request, "Lecture created.")
            return redirect("lecturer:lecture_detail", lecture_id=lecture.pk)
    else:
        form = LectureForm(user=request.user)
    return render(request, "lecturer/lecture_form.html", {"form": form})


@privileged_required
def lecture_detail(request, lecture_id: int):
    lecture = get_object_or_404(
        Lecture.objects.select_related("course", "course__lecturer"), pk=lecture_id
    )
    if not user_can_run(request.user, lecture):
        messages.error(request, "You don't have permission for this lecture.")
        return redirect("lecturer:dashboard")
    expire_if_due(lecture)
    attendance = lecture.attendance_records.select_related("student").order_by("-marked_at")
    return render(
        request,
        "lecturer/lecture_detail.html",
        {"lecture": lecture, "attendance": attendance},
    )


@privileged_required
@require_POST
def start_lecture(request, lecture_id: int):
    lecture = get_object_or_404(Lecture, pk=lecture_id)
    if not user_can_run(request.user, lecture):
        messages.error(request, "You don't have permission for this lecture.")
        return redirect("lecturer:dashboard")
    expire_if_due(lecture)
    if is_past_end(lecture):
        messages.error(
            request,
            "That lecture's scheduled end time has passed, so it can no longer be started.",
        )
        return redirect("lecturer:lecture_detail", lecture_id=lecture.pk)
    if lecture.status != Lecture.Status.ACTIVE:
        lecture.status = Lecture.Status.ACTIVE
        lecture.save(update_fields=("status",))
    current_token_for(lecture)  # ensure first token exists
    return redirect("lecturer:qr_display", lecture_id=lecture.pk)


@privileged_required
@require_POST
def end_lecture(request, lecture_id: int):
    lecture = get_object_or_404(Lecture, pk=lecture_id)
    if not user_can_run(request.user, lecture):
        messages.error(request, "You don't have permission for this lecture.")
        return redirect("lecturer:dashboard")
    end_lecture_now(lecture)
    messages.success(request, "Lecture ended.")
    return redirect("lecturer:lecture_detail", lecture_id=lecture.pk)


@privileged_required
def qr_display(request, lecture_id: int):
    lecture = get_object_or_404(Lecture, pk=lecture_id)
    if not user_can_run(request.user, lecture):
        return redirect("lecturer:dashboard")
    expire_if_due(lecture)
    return render(request, "lecturer/qr_display.html", {"lecture": lecture})
