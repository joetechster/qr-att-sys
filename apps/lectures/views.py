from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.courses.models import Course

from .forms import LectureForm
from .models import Lecture
from .services import current_token_for


def _user_can_run(user, lecture: Lecture) -> bool:
    if user.role == "admin":
        return True
    return user == lecture.course.lecturer or user == lecture.course.course_rep


def _privileged_required(view):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/auth/login/")
        if not request.user.is_privileged:
            return redirect("/auth/login/")
        return view(request, *args, **kwargs)

    return wrapped


@login_required
@_privileged_required
def lecturer_dashboard(request):
    user = request.user
    if user.role == "admin":
        courses = Course.objects.all()
        lectures = Lecture.objects.select_related("course").all()[:50]
    else:
        courses = Course.objects.filter(Q(lecturer=user) | Q(course_rep=user))
        lectures = Lecture.objects.filter(
            Q(course__lecturer=user) | Q(course__course_rep=user)
        ).select_related("course")[:50]
    return render(
        request,
        "lecturer/dashboard.html",
        {"courses": courses, "lectures": lectures},
    )


@login_required
@_privileged_required
def create_lecture(request):
    if request.method == "POST":
        form = LectureForm(request.POST, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data
            if cd.get("course_mode") == LectureForm.MODE_NEW:
                course = Course.objects.create(
                    code=cd["new_course_code"].strip(),
                    title=cd["new_course_title"].strip(),
                    department=cd["new_course_department"].strip(),
                    lecturer=request.user,
                    course_rep=cd.get("new_course_rep"),
                )
            else:
                course = cd["course"]
            lecture: Lecture = form.save(commit=False)
            lecture.course = course
            lecture.created_by = request.user
            lecture.save()
            messages.success(request, "Lecture created.")
            return redirect("lecturer:lecture_detail", lecture_id=lecture.pk)
    else:
        form = LectureForm(user=request.user)
    return render(request, "lecturer/lecture_form.html", {"form": form})


@login_required
@_privileged_required
def lecture_detail(request, lecture_id: int):
    lecture = get_object_or_404(
        Lecture.objects.select_related("course", "course__lecturer"), pk=lecture_id
    )
    if not _user_can_run(request.user, lecture):
        messages.error(request, "You don't have permission for this lecture.")
        return redirect("lecturer:dashboard")
    attendance = lecture.attendance_records.select_related("student").order_by("-marked_at")
    return render(
        request,
        "lecturer/lecture_detail.html",
        {"lecture": lecture, "attendance": attendance},
    )


@login_required
@_privileged_required
@require_POST
def start_lecture(request, lecture_id: int):
    lecture = get_object_or_404(Lecture, pk=lecture_id)
    if not _user_can_run(request.user, lecture):
        messages.error(request, "You don't have permission for this lecture.")
        return redirect("lecturer:dashboard")
    if lecture.status != Lecture.Status.ACTIVE:
        lecture.status = Lecture.Status.ACTIVE
        lecture.save(update_fields=("status",))
    current_token_for(lecture)  # ensure first token exists
    return redirect("lecturer:qr_display", lecture_id=lecture.pk)


@login_required
@_privileged_required
@require_POST
def end_lecture(request, lecture_id: int):
    from .models import QRToken

    lecture = get_object_or_404(Lecture, pk=lecture_id)
    if not _user_can_run(request.user, lecture):
        messages.error(request, "You don't have permission for this lecture.")
        return redirect("lecturer:dashboard")
    lecture.status = Lecture.Status.ENDED
    lecture.save(update_fields=("status",))
    QRToken.objects.filter(lecture=lecture, is_used=False).update(is_used=True)
    messages.success(request, "Lecture ended.")
    return redirect("lecturer:lecture_detail", lecture_id=lecture.pk)


@login_required
@_privileged_required
def qr_display(request, lecture_id: int):
    lecture = get_object_or_404(Lecture, pk=lecture_id)
    if not _user_can_run(request.user, lecture):
        return redirect("lecturer:dashboard")
    return render(request, "lecturer/qr_display.html", {"lecture": lecture})


@login_required
@_privileged_required
def current_token(request, lecture_id: int):
    lecture = get_object_or_404(Lecture, pk=lecture_id)
    if not _user_can_run(request.user, lecture):
        return JsonResponse({"error": "forbidden"}, status=403)
    if lecture.status != Lecture.Status.ACTIVE:
        return JsonResponse({"status": lecture.status, "token": None})
    token = current_token_for(lecture)
    scan_url = request.build_absolute_uri(f"/scan/?t={token.token}")
    return JsonResponse(
        {"status": lecture.status, "token": str(token.token), "scan_url": scan_url}
    )
