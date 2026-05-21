from django.contrib import admin

from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "student",
        "course",
        "lecturer",
        "status",
        "is_anonymous",
        "created_at",
    )
    list_filter = ("status", "is_anonymous", "created_at")
    search_fields = ("subject", "body", "student__username", "student__first_name")
    readonly_fields = ("created_at", "updated_at")
