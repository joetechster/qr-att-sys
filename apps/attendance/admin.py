from django.contrib import admin

from .models import AttendanceRecord


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "lecture", "marked_at", "face_match_distance")
    list_filter = ("lecture__course", "lecture")
    search_fields = ("student__username", "lecture__title")
    readonly_fields = ("marked_at", "face_match_distance", "qr_token")
