from django.urls import path

from . import views


app_name = "student"

urlpatterns = [
    path("", views.student_dashboard, name="dashboard"),
    path("enroll/<int:course_id>/", views.enroll, name="enroll"),
]
