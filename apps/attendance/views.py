from __future__ import annotations

import base64
import binascii
import re
import uuid

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from apps.accounts.face_utils import FaceError, compare_to_encoding
from apps.accounts.models import StudentProfile, User
from apps.courses.models import Enrollment
from apps.lectures.models import Lecture, QRToken
from apps.lectures.services import rotate_token

from .models import AttendanceRecord


_DATA_URL_RE = re.compile(r"^data:image/(?:png|jpeg|jpg);base64,(?P<data>.+)$")


def _decode_data_url(data_url: str) -> bytes:
    match = _DATA_URL_RE.match(data_url.strip())
    if not match:
        raise ValueError("Face capture missing or unreadable.")
    try:
        return base64.b64decode(match.group("data"))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Captured image is corrupted.") from exc


@role_required(User.Role.STUDENT)
def scan_page(request):
    """Render the scanner page. The token may be prefilled from QR deep-link."""
    return render(request, "student/scan.html", {"prefilled_token": request.GET.get("t", "")})


# json=True: the scanner fetches this, so a refusal has to stay JSON. An HTML
# login redirect here would surface to the student as an unreadable parse error.
@role_required(User.Role.STUDENT, json=True, message="Only students can mark attendance.")
@require_POST
def verify(request):
    raw_token = (request.POST.get("token") or "").strip()
    image_data = request.POST.get("image", "")

    try:
        token_uuid = uuid.UUID(raw_token)
    except (ValueError, AttributeError):
        return JsonResponse({"ok": False, "error": "Invalid QR code."}, status=400)

    try:
        image_bytes = _decode_data_url(image_data)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    profile: StudentProfile | None = getattr(request.user, "student_profile", None)
    if profile is None:
        return JsonResponse(
            {"ok": False, "error": "No face on file. Re-register your face."}, status=400
        )

    try:
        with transaction.atomic():
            try:
                token = QRToken.objects.select_for_update().select_related(
                    "lecture", "lecture__course"
                ).get(token=token_uuid)
            except QRToken.DoesNotExist:
                return JsonResponse({"ok": False, "error": "Unknown QR code."}, status=404)

            if token.is_used:
                return JsonResponse(
                    {"ok": False, "error": "This QR code has expired. Scan the new one."},
                    status=409,
                )
            if token.lecture.status != Lecture.Status.ACTIVE:
                return JsonResponse(
                    {"ok": False, "error": "Lecture is not active."}, status=409
                )

            if not Enrollment.objects.filter(
                student=request.user, course=token.lecture.course
            ).exists():
                return JsonResponse(
                    {"ok": False, "error": "You are not enrolled in this course."}, status=403
                )

            if AttendanceRecord.objects.filter(
                lecture=token.lecture, student=request.user
            ).exists():
                return JsonResponse(
                    {"ok": False, "error": "You're already marked present for this lecture."},
                    status=409,
                )

            try:
                distance = compare_to_encoding(image_bytes, bytes(profile.face_encoding))
            except FaceError as exc:
                return JsonResponse({"ok": False, "error": str(exc)}, status=400)

            if distance is None:
                return JsonResponse(
                    {"ok": False, "error": "No face detected. Re-take the photo."}, status=400
                )

            threshold = getattr(settings, "FACE_MATCH_THRESHOLD", 0.6)
            if distance >= threshold:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "Face does not match the registered student.",
                        "distance": distance,
                    },
                    status=401,
                )

            try:
                AttendanceRecord.objects.create(
                    lecture=token.lecture,
                    student=request.user,
                    qr_token=token,
                    face_match_distance=distance,
                )
            except IntegrityError:
                return JsonResponse(
                    {"ok": False, "error": "You're already marked present for this lecture."},
                    status=409,
                )

            rotate_token(token.lecture, token, request.user)
    except Exception as exc:  # last-resort guard
        return JsonResponse({"ok": False, "error": f"Server error: {exc}"}, status=500)

    # Queued here rather than rendered inline: the scanner redirects to the
    # dashboard, which renders it through the shared messages block.
    messages.success(
        request,
        f"Attendance marked for {token.lecture.course.code} — {token.lecture.title}.",
    )
    return JsonResponse(
        {
            "ok": True,
            "message": "Attendance marked.",
            "lecture": token.lecture.title,
            "course": token.lecture.course.code,
            "distance": distance,
            "redirect_url": reverse("student:dashboard"),
        }
    )
