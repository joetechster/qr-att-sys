from django.urls import path

from . import views


urlpatterns = [
    path("", views.lecturer_dashboard, name="dashboard"),
    path("lecture/new/", views.create_lecture, name="create_lecture"),
    path("lecture/<int:lecture_id>/", views.lecture_detail, name="lecture_detail"),
    path("lecture/<int:lecture_id>/start/", views.start_lecture, name="start_lecture"),
    path("lecture/<int:lecture_id>/end/", views.end_lecture, name="end_lecture"),
    path("lecture/<int:lecture_id>/qr/", views.qr_display, name="qr_display"),
]
