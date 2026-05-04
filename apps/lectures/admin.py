from django.contrib import admin

from .models import Lecture, QRToken


@admin.register(Lecture)
class LectureAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "scheduled_start", "scheduled_end", "status")
    list_filter = ("status", "course")
    search_fields = ("title", "course__code")


@admin.register(QRToken)
class QRTokenAdmin(admin.ModelAdmin):
    list_display = ("token", "lecture", "is_used", "used_by", "used_at", "created_at")
    list_filter = ("is_used", "lecture")
    readonly_fields = ("token", "created_at", "used_at")
