from django.urls import path

from . import views


urlpatterns = [
    path("", views.hod_complaint_list, name="dashboard"),
    path(
        "complaint/<int:complaint_id>/",
        views.hod_complaint_detail,
        name="complaint_detail",
    ),
]
