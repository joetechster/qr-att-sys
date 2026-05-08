from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CourseForm
from .models import Course


def _lecturer_required(view):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != "lecturer":
            messages.error(
                request,
                "Only lecturers can create courses here. Admins use /admin/.",
            )
            return redirect("course_list")
        return view(request, *args, **kwargs)

    return wrapped


@login_required
def course_list(request):
    courses = Course.objects.select_related("lecturer", "course_rep").all()
    enrolled_ids = set()
    if request.user.role == "student":
        enrolled_ids = set(request.user.enrollments.values_list("course_id", flat=True))
    return render(
        request,
        "courses/list.html",
        {"courses": courses, "enrolled_ids": enrolled_ids},
    )


@login_required
def course_detail(request, course_id: int):
    course = get_object_or_404(
        Course.objects.select_related("lecturer", "course_rep"), pk=course_id
    )
    enrollments = course.enrollments.select_related("student").all()
    lectures = course.lectures.order_by("-scheduled_start")
    return render(
        request,
        "courses/detail.html",
        {"course": course, "enrollments": enrollments, "lectures": lectures},
    )


@login_required
@_lecturer_required
def create_course(request):
    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.lecturer = request.user
            course.save()
            messages.success(request, f"Course {course.code} created.")
            return redirect("course_detail", course_id=course.pk)
    else:
        form = CourseForm()
    return render(request, "courses/form.html", {"form": form})
