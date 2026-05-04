from django.urls import path

from . import views


urlpatterns = [
    path("login/", views.AppLoginView.as_view(), name="login"),
    path("logout/", views.AppLogoutView.as_view(), name="logout"),
    path("register/student/", views.register_student, name="register_student"),
]
