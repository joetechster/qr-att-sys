from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import User

from .forms import ComplaintForm, ComplaintReviewForm
from .models import Complaint


def _student_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != User.Role.STUDENT:
            return redirect("/auth/login/")
        return view(request, *args, **kwargs)

    return wrapped


def _hod_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != User.Role.HOD:
            return redirect("/auth/login/")
        return view(request, *args, **kwargs)

    return wrapped


@_student_required
def submit_complaint(request):
    if request.method == "POST":
        form = ComplaintForm(request.POST, user=request.user)
        if form.is_valid():
            complaint: Complaint = form.save(commit=False)
            complaint.student = request.user
            complaint.save()
            messages.success(request, "Your complaint has been submitted.")
            return redirect("complaints:my_complaints")
    else:
        form = ComplaintForm(user=request.user)
    return render(request, "complaints/submit.html", {"form": form})


@_student_required
def my_complaints(request):
    complaints = Complaint.objects.filter(student=request.user).select_related(
        "course", "lecturer", "responded_by"
    )
    return render(request, "complaints/my_list.html", {"complaints": complaints})


@_hod_required
def hod_complaint_list(request):
    status_filter = request.GET.get("status", "").strip()
    qs = Complaint.objects.select_related("student", "course", "lecturer")
    if status_filter in dict(Complaint.Status.choices):
        qs = qs.filter(status=status_filter)
    return render(
        request,
        "hod/dashboard.html",
        {
            "complaints": qs,
            "status_filter": status_filter,
            "status_choices": Complaint.Status.choices,
        },
    )


@_hod_required
def hod_complaint_detail(request, complaint_id: int):
    complaint = get_object_or_404(
        Complaint.objects.select_related("student", "course", "lecturer"),
        pk=complaint_id,
    )
    if request.method == "POST":
        form = ComplaintReviewForm(request.POST, instance=complaint)
        if form.is_valid():
            updated: Complaint = form.save(commit=False)
            updated.responded_by = request.user
            updated.save()
            messages.success(request, "Complaint updated.")
            return redirect("hod:complaint_detail", complaint_id=complaint.id)
    else:
        form = ComplaintReviewForm(instance=complaint)
    return render(
        request,
        "hod/complaint_detail.html",
        {"complaint": complaint, "form": form},
    )
