from django.urls import path

from . import views


urlpatterns = [
    path("login/", views.AppLoginView.as_view(), name="login"),
    path("logout/", views.AppLogoutView.as_view(), name="logout"),
    path("register/student/", views.register_student, name="register_student"),
    path("profile/", views.profile, name="profile"),
    path(
        "password/change/",
        views.AppPasswordChangeView.as_view(),
        name="password_change",
    ),
]
