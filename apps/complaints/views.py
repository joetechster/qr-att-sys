from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from apps.accounts.models import User

from .forms import ComplaintForm, ComplaintReviewForm, EscalateComplaintForm
from .models import Complaint


_student_required = role_required(User.Role.STUDENT)
_hod_required = role_required(User.Role.HOD)


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
    escalated_only = request.GET.get("escalated") == "1"
    qs = Complaint.objects.select_related("student", "course", "lecturer")
    if status_filter in dict(Complaint.Status.choices):
        qs = qs.filter(status=status_filter)
    if escalated_only:
        qs = qs.filter(escalated_at__isnull=False)
    return render(
        request,
        "hod/complaints.html",
        {
            "complaints": qs,
            "status_filter": status_filter,
            "escalated_only": escalated_only,
            "status_choices": Complaint.Status.choices,
        },
    )


@_hod_required
def hod_complaint_detail(request, complaint_id: int):
    complaint = get_object_or_404(
        Complaint.objects.select_related(
            "student", "course", "lecturer", "escalated_by"
        ),
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
        {
            "complaint": complaint,
            "form": form,
            "escalate_form": EscalateComplaintForm(instance=complaint),
        },
    )


@_hod_required
@require_POST
def hod_escalate_complaint(request, complaint_id: int):
    """Push a complaint up to the Vice Chancellor.

    Idempotent: re-posting on an already-escalated complaint only rewrites the
    note, so the original escalation's timestamp and author survive.
    """
    complaint = get_object_or_404(Complaint, pk=complaint_id)
    already = complaint.is_escalated
    form = EscalateComplaintForm(request.POST, instance=complaint)
    if form.is_valid():
        updated: Complaint = form.save(commit=False)
        if not already:
            updated.escalated_at = timezone.now()
            updated.escalated_by = request.user
        updated.save()
        messages.success(
            request,
            "Escalation note updated."
            if already
            else "Complaint escalated to the Vice Chancellor.",
        )
    else:
        messages.error(request, "Could not escalate that complaint.")
    return redirect("hod:complaint_detail", complaint_id=complaint.id)
