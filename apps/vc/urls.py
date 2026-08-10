from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("complaints/", views.complaint_list, name="complaints"),
    path("complaints/<int:complaint_id>/", views.complaint_detail, name="complaint_detail"),
]
