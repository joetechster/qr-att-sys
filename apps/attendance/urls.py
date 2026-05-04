from django.urls import path

from . import views


urlpatterns = [
    path("", views.scan_page, name="scan_page"),
    path("verify/", views.verify, name="scan_verify"),
]
