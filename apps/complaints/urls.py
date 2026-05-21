from django.urls import path

from . import views


app_name = "complaints"

urlpatterns = [
    path("submit/", views.submit_complaint, name="submit"),
    path("mine/", views.my_complaints, name="my_complaints"),
]
