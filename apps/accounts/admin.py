from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import (
    ReadOnlyPasswordHashField,
    ReadOnlyPasswordHashWidget,
    UserChangeForm,
)
from django.utils.translation import gettext_lazy as _

from .models import StudentProfile, User


class PasswordStatusWidget(ReadOnlyPasswordHashWidget):
    """Password readout without the stored hash's internals.

    Django lists the hasher's safe summary — algorithm, iterations, salt and a
    truncated hash — beside the reset button. None of it is actionable when
    provisioning an account, so keep only whether a password is set.
    """

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # Entries carrying a value are the safe summary; the value-less ones are
        # status messages ("No password set.") that are worth keeping.
        summary = [entry for entry in context["summary"] if not entry.get("value")]
        context["summary"] = summary or [{"label": _("Password set.")}]
        return context


class AppUserChangeForm(UserChangeForm):
    password = ReadOnlyPasswordHashField(
        label=_("Password"),
        help_text=_(
            "Raw passwords are not stored, so there is no way to see "
            "the user’s password."
        ),
        widget=PasswordStatusWidget,
    )


@admin.register(User)
class AppUserAdmin(UserAdmin):
    form = AppUserChangeForm
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
