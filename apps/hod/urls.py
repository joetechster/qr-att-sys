from django.urls import path

from apps.complaints import views as complaint_views

from . import views


# The complaint views keep their original `hod:complaint_detail` name so their
# existing reverses and templates stay valid; only the path moved under
# /hod/complaints/ to make room for the rest of the console.
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("complaints/", complaint_views.hod_complaint_list, name="complaints"),
    path(
        "complaints/<int:complaint_id>/",
        complaint_views.hod_complaint_detail,
        name="complaint_detail",
    ),
    path("courses/", views.course_list, name="courses"),
    path("courses/<int:course_id>/edit/", views.course_edit, name="course_edit"),
    path("lecturers/", views.lecturer_list, name="lecturers"),
    path("lecturers/new/", views.create_lecturer, name="create_lecturer"),
    path("import/lecturers/", views.import_lecturers, name="import_lecturers"),
    path("import/courses/", views.import_courses, name="import_courses"),
    # `kind` is pinned per route rather than captured, so only the two known
    # templates are reachable and the view needs no validation of its own.
    path(
        "import/lecturers/template.csv",
        views.import_template,
        {"kind": "lecturers"},
        name="lecturer_template",
    ),
    path(
        "import/courses/template.csv",
        views.import_template,
        {"kind": "courses"},
        name="course_template",
    ),
]
