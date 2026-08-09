from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import StudentProfile, User


@admin.register(User)
class AppUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "email", "role", "is_active")
    list_filter = ("role", "is_active", "is_staff")

    # Spelled out rather than concatenated onto UserAdmin.fieldsets, which
    # carries a Permissions section with `groups` and `user_permissions`.
    # Authorisation here is entirely User.role — auth.Group is not used anywhere
    # in the project — so offering group pickers when provisioning a lecturer
    # was a menu of settings that did nothing.
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Role", {"fields": ("role", "must_change_password")}),
        ("Status", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "first_name", "last_name", "email", "role",
                           "password1", "password2"),
            },
        ),
    )
    # UserAdmin declares filter_horizontal for the two m2m fields above; leaving
    # it set once they're off the form trips admin.E020 at system-check time.
    filter_horizontal = ()


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("matric_number", "user", "department", "level", "created_at")
    search_fields = ("matric_number", "user__username", "user__first_name", "user__last_name")
    readonly_fields = ("face_encoding", "created_at")
