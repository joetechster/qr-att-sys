from __future__ import annotations

import csv
import io

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import get_random_string

from apps.accounts.decorators import role_required
from apps.accounts.models import User
from apps.complaints.models import Complaint
from apps.courses.forms import CourseForm
from apps.courses.models import Course
from apps.lectures.models import Lecture

from .forms import CsvUploadForm, LecturerCreateForm


hod_required = role_required(User.Role.HOD)

# Excluded from generated passwords: 0/O and 1/l/I are misread when a password
# is copied off a screen onto paper, which is exactly how these get delivered.
_PASSWORD_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# Single source of truth for what the importers accept — the upload templates
# render these rather than repeating the list in prose, which is how the two
# drifted apart before.
LECTURER_REQUIRED_COLUMNS = ("username", "first_name", "last_name")
LECTURER_OPTIONAL_COLUMNS = ("email", "password")
COURSE_REQUIRED_COLUMNS = ("lecturer", "code", "title", "unit", "department")
COURSE_OPTIONAL_COLUMNS = ()

# Older exports named the lecturer column `lecturer_username`. Normalising here
# means those files keep importing without a second code path.
_CSV_ALIASES = {"lecturer_username": "lecturer"}

MIN_COURSE_UNIT = 1
MAX_COURSE_UNIT = 12


def _temp_password() -> str:
    return get_random_string(10, allowed_chars=_PASSWORD_ALPHABET)


def _read_csv(upload, required_columns):
    """Return (rows, error). `rows` is a list of stripped-value dicts.

    `utf-8-sig` matters: Excel-exported CSVs carry a BOM that would otherwise
    become part of the first header name.
    """
    try:
        text = io.TextIOWrapper(upload.file, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(text)
        fieldnames = [
            _CSV_ALIASES.get(name, name)
            for name in ((raw or "").strip().lower() for raw in (reader.fieldnames or []))
        ]
        missing = [col for col in required_columns if col not in fieldnames]
        if missing:
            return [], f"CSV is missing required column(s): {', '.join(missing)}."
        rows = []
        for raw in reader:
            row = {}
            for key, value in raw.items():
                if key is None:
                    continue
                name = (key or "").strip().lower()
                row[_CSV_ALIASES.get(name, name)] = (value or "").strip()
            if any(row.values()):  # ignore trailing blank lines
                rows.append(row)
    except UnicodeDecodeError:
        return [], "Could not read the file as UTF-8. Re-save it as CSV UTF-8."
    if not rows:
        return [], "The file has a header but no data rows."
    return rows, None


@hod_required
def dashboard(request):
    return render(
        request,
        "hod/dashboard.html",
        {
            "course_count": Course.objects.count(),
            "lecturer_count": User.objects.filter(role=User.Role.LECTURER).count(),
            "lecture_count": Lecture.objects.count(),
            "open_complaints": Complaint.objects.filter(
                status=Complaint.Status.SUBMITTED
            ).count(),
            "recent_courses": Course.objects.select_related("lecturer").order_by("-created_at")[:8],
        },
    )


@hod_required
def course_list(request):
    courses = Course.objects.select_related("lecturer", "course_rep")
    paginator = Paginator(courses, 25)
    return render(
        request,
        "hod/courses.html",
        {
            "page": paginator.get_page(request.GET.get("page")),
            "total": paginator.count,
        },
    )


@hod_required
def course_edit(request, course_id: int):
    """Reassigning a course to a different lecturer.

    Previously only possible through Django admin, which is why a change of
    lecturer meant editing the database by hand.
    """
    course = get_object_or_404(Course, pk=course_id)
    if request.method == "POST":
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            course = form.save()
            messages.success(request, f"{course.code} updated.")
            return redirect("hod:courses")
    else:
        form = CourseForm(instance=course)
    return render(request, "courses/form.html", {"form": form, "course": course})


@hod_required
def lecturer_list(request):
    lecturers = User.objects.filter(role=User.Role.LECTURER).order_by(
        "last_name", "first_name", "username"
    )
    return render(request, "hod/lecturers.html", {"lecturers": lecturers})


@hod_required
def create_lecturer(request):
    if request.method == "POST":
        form = LecturerCreateForm(request.POST)
        if form.is_valid():
            password = _temp_password()
            lecturer: User = form.save(commit=False)
            lecturer.role = User.Role.LECTURER
            lecturer.must_change_password = True
            lecturer.set_password(password)
            lecturer.save()
            messages.success(request, f"Lecturer account created for {lecturer.username}.")
            return render(
                request,
                "hod/lecturer_created.html",
                {"lecturer": lecturer, "password": password},
            )
    else:
        form = LecturerCreateForm()
    return render(request, "hod/lecturer_form.html", {"form": form})


@hod_required
def import_lecturers(request):
    context = {
        "form": CsvUploadForm(),
        "required_columns": LECTURER_REQUIRED_COLUMNS,
        "optional_columns": LECTURER_OPTIONAL_COLUMNS,
    }
    if request.method == "POST":
        form = CsvUploadForm(request.POST, request.FILES)
        context["form"] = form
        if form.is_valid():
            rows, error = _read_csv(form.cleaned_data["file"], LECTURER_REQUIRED_COLUMNS)
            if error:
                messages.error(request, error)
            else:
                context["result"] = _create_lecturers(rows)
    return render(request, "hod/import_lecturers.html", context)


def _create_lecturers(rows):
    created, skipped, errors = [], [], []
    with transaction.atomic():
        for line, row in enumerate(rows, start=2):  # line 1 is the header
            username = row.get("username", "")
            if not username:
                errors.append({"line": line, "detail": "Missing username."})
                continue
            if User.objects.filter(username__iexact=username).exists():
                skipped.append({"line": line, "username": username, "detail": "Already exists."})
                continue
            password = row.get("password") or _temp_password()
            try:
                with transaction.atomic():
                    user = User(
                        username=username,
                        first_name=row.get("first_name", ""),
                        last_name=row.get("last_name", ""),
                        email=row.get("email", ""),
                        role=User.Role.LECTURER,
                        must_change_password=True,
                    )
                    user.set_password(password)
                    user.full_clean(exclude=("password",))
                    user.save()
            except IntegrityError:
                skipped.append({"line": line, "username": username, "detail": "Already exists."})
            except Exception as exc:  # ValidationError and anything else per-row
                errors.append({"line": line, "detail": _describe(exc)})
            else:
                created.append(
                    {
                        "line": line,
                        "username": username,
                        "name": user.get_full_name(),
                        "password": password,
                    }
                )
    return {"created": created, "skipped": skipped, "errors": errors}


@hod_required
def import_courses(request):
    context = {
        "form": CsvUploadForm(),
        "required_columns": COURSE_REQUIRED_COLUMNS,
        "optional_columns": COURSE_OPTIONAL_COLUMNS,
    }
    if request.method == "POST":
        form = CsvUploadForm(request.POST, request.FILES)
        context["form"] = form
        if form.is_valid():
            rows, error = _read_csv(form.cleaned_data["file"], COURSE_REQUIRED_COLUMNS)
            if error:
                messages.error(request, error)
            else:
                context["result"] = _create_courses(rows)
    return render(request, "hod/import_courses.html", context)


def _create_courses(rows):
    created, skipped, errors = [], [], []
    with transaction.atomic():
        for line, row in enumerate(rows, start=2):
            code = row.get("code", "")
            if not code:
                errors.append({"line": line, "detail": "Missing course code."})
                continue
            if Course.objects.filter(code__iexact=code).exists():
                skipped.append({"line": line, "code": code, "detail": "Already exists."})
                continue
            lecturer_username = row.get("lecturer", "")
            lecturer = User.objects.filter(
                username__iexact=lecturer_username,
                role=User.Role.LECTURER,
            ).first()
            if lecturer is None:
                errors.append(
                    {"line": line, "detail": f"No lecturer named '{lecturer_username}'."}
                )
                continue
            raw_unit = row.get("unit", "")
            if not raw_unit.isdigit() or not (
                MIN_COURSE_UNIT <= int(raw_unit) <= MAX_COURSE_UNIT
            ):
                errors.append(
                    {
                        "line": line,
                        "detail": (
                            f"Unit must be a whole number between {MIN_COURSE_UNIT} and "
                            f"{MAX_COURSE_UNIT}, got '{raw_unit}'."
                        ),
                    }
                )
                continue
            try:
                with transaction.atomic():
                    # course_rep is deliberately not importable: reps are students
                    # who are appointed after the catalogue exists, so they're
                    # assigned from the course edit page instead.
                    course = Course.objects.create(
                        code=code,
                        title=row.get("title", ""),
                        unit=int(raw_unit),
                        department=row.get("department", ""),
                        lecturer=lecturer,
                    )
            except IntegrityError:
                skipped.append({"line": line, "code": code, "detail": "Already exists."})
            except Exception as exc:
                errors.append({"line": line, "detail": _describe(exc)})
            else:
                created.append(
                    {
                        "line": line,
                        "code": course.code,
                        "title": course.title,
                        "unit": course.unit,
                        "lecturer": lecturer.get_full_name() or lecturer.username,
                    }
                )
    return {"created": created, "skipped": skipped, "errors": errors}


def _describe(exc: Exception) -> str:
    messages_ = getattr(exc, "messages", None)
    if messages_:
        return " ".join(messages_)
    return str(exc) or exc.__class__.__name__
