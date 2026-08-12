from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from apps.accounts.models import User

from .forms import ComplaintForm, ComplaintReviewForm, EscalateComplaintForm
from .models import Complaint


_student_required = role_required(User.Role.STUDENT)
_hod_required = role_required(User.Role.HOD)


def _safe_next(request, fallback: str) -> str:
    """Where to send the HOD after a POST that two different pages can fire.

    Validated rather than trusted: an unchecked `next` is an open redirect, and
    this one is rendered into a form on a page every HOD can reach.
    """
    candidate = request.POST.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


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


def _status_tiles(status_filter: str) -> list[dict]:
    """The filter strip: Total plus one tile per status, each with a live count.

    Counted over the unfiltered manager on purpose — clicking "Reviewed" must
    not rewrite the other four tiles to zero, since the whole point of the strip
    is to show what else is waiting.

    One `aggregate` rather than `values("status").annotate(...)`: that form
    returns a row only for statuses that actually exist, so "Escalated 0" would
    silently vanish from the strip instead of rendering as a zero.
    """
    counts = Complaint.objects.aggregate(
        total=Count("pk"),
        **{
            f"n_{value}": Count("pk", filter=Q(status=value))
            for value, _ in Complaint.Status.choices
        },
    )
    tiles = [
        {
            "label": "Total",
            "value": "",
            "count": counts["total"],
            "query": "",
            "is_active": not status_filter,
        }
    ]
    tiles += [
        {
            "label": label,
            "value": value,
            "count": counts[f"n_{value}"],
            "query": f"?status={value}",
            "is_active": status_filter == value,
        }
        for value, label in Complaint.Status.choices
    ]
    return tiles


@_hod_required
def hod_complaint_list(request):
    status_filter = request.GET.get("status", "").strip()
    if status_filter not in dict(Complaint.Status.choices):
        # An unrecognised ?status= means "no filter", not "no results": a stale
        # bookmark lands on a usable page with the Total tile lit up, rather
        # than an empty table and no tile selected.
        status_filter = ""
    qs = Complaint.objects.select_related("student", "course", "lecturer")
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(
        request,
        "hod/complaints.html",
        {
            "complaints": qs,
            "status_filter": status_filter,
            "status_tiles": _status_tiles(status_filter),
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
            # Picking "Escalated" here has to do what the Escalate button does.
            # The VC console filters on `escalated_at`, not on status, so a
            # status change alone would leave the complaint invisible to the
            # office it was just escalated to.
            if updated.status == Complaint.Status.ESCALATED:
                updated.mark_escalated(by=request.user)
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

    Fired from two places: the note form on the detail page, and the per-row
    button on the list. Idempotent — re-posting on an already-escalated
    complaint only rewrites the note, so the original escalation's timestamp and
    author survive. `mark_escalated` also refuses to reopen a resolved
    complaint, so a late note never drags a closed case back into the queue.
    """
    complaint = get_object_or_404(Complaint, pk=complaint_id)
    fallback = reverse("hod:complaint_detail", kwargs={"complaint_id": complaint.id})
    form = EscalateComplaintForm(request.POST, instance=complaint)
    if form.is_valid():
        updated: Complaint = form.save(commit=False)
        first_stamp = updated.mark_escalated(by=request.user)
        updated.save()
        messages.success(
            request,
            "Complaint escalated to the Vice Chancellor."
            if first_stamp
            else "Escalation note updated.",
        )
    else:
        messages.error(request, "Could not escalate that complaint.")
    return redirect(_safe_next(request, fallback))
