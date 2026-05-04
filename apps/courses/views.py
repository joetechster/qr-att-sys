from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Course


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
