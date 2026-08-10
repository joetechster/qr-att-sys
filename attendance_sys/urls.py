from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("apps.accounts.urls")),
    path("courses/", include("apps.courses.urls")),
    path("lectures/", include("apps.lectures.urls")),
    path("scan/", include("apps.attendance.urls")),
    path("lecturer/", include(("apps.lectures.dashboard_urls", "lecturer"), namespace="lecturer")),
    path("student/", include(("apps.accounts.student_urls", "student"), namespace="student")),
    path("complaints/", include("apps.complaints.urls")),
    path("hod/", include(("apps.hod.urls", "hod"), namespace="hod")),
    path("vc/", include(("apps.vc.urls", "vc"), namespace="vc")),
    path("", RedirectView.as_view(url="/auth/login/", permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
