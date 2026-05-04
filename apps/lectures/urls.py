from django.urls import path

from . import views


urlpatterns = [
    path("<int:lecture_id>/qr/current/", views.current_token, name="current_token"),
]
