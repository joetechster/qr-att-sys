"""Vice Chancellor console.

Read-only by design: the VC oversees what the HOD escalates but never responds
or changes a status, so there is no form anywhere in this app. A complaint
becomes visible here the moment `escalated_at` is set.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404, render

from apps.accounts.decorators import role_required
from apps.accounts.models import User
from apps.complaints.models import Complaint


vc_required = role_required(User.Role.VICE_CHANCELLOR)


def _escalated():
    return Complaint.objects.filter(escalated_at__isnull=False).select_related(
        "student", "course", "lecturer", "escalated_by", "responded_by"
    )


@vc_required
def dashboard(request):
    escalated = _escalated()
    return render(
        request,
        "vc/dashboard.html",
        {
            "escalated_count": escalated.count(),
            # "Unresolved", not "open": the row actions on this page are already
            # labelled Open, meaning "open this record", and the two readings of
            # the word sat side by side on the same card.
            "unresolved_count": escalated.exclude(
                status=Complaint.Status.RESOLVED
            ).count(),
            "resolved_count": escalated.filter(status=Complaint.Status.RESOLVED).count(),
            "recent": escalated.order_by("-escalated_at")[:8],
        },
    )


@vc_required
def complaint_list(request):
    status_filter = request.GET.get("status", "").strip()
    qs = _escalated().order_by("-escalated_at")
    # Deliberately the same four-value vocabulary the HOD works in. "Unreviewed"
    # will effectively always be empty here — escalating sets the status — but a
    # chip that honestly returns nothing beats a second, divergent list.
    if status_filter in dict(Complaint.Status.choices):
        qs = qs.filter(status=status_filter)
    return render(
        request,
        "vc/complaints.html",
        {
            "complaints": qs,
            "status_filter": status_filter,
            "status_choices": Complaint.Status.choices,
        },
    )


@vc_required
def complaint_detail(request, complaint_id: int):
    # Scoped to `_escalated()` rather than all complaints: a complaint the HOD
    # has not escalated is a 404 here even if the VC guesses its id.
    complaint = get_object_or_404(_escalated(), pk=complaint_id)
    return render(request, "vc/complaint_detail.html", {"complaint": complaint})
