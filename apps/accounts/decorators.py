"""Role gates shared across apps.

Every app used to hand-roll its own `_lecturer_required` / `_hod_required`
closure. They only ever differed in the allowed role and where they bounced
you to, so they collapse into one factory here.
"""
from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .roles import role_home


def role_required(
    *roles,
    redirect_to: str | None = None,
    message: str | None = None,
    json: bool = False,
):
    """Allow only the listed `User.Role` values through.

    Anonymous users are handled here too, so views wrapped with this don't also
    need `@login_required`. What happens on refusal depends on *why*:

    * not signed in      → the login page, keeping the deep link in `?next=`
    * `redirect_to` set  → that URL, optionally with `message`. This is a
      considered in-app denial ("only the HOD can create courses"), not a mixup.
    * otherwise          → a 403 page naming the account you're actually signed
      in as. All tabs in a browser share one session, so signing in elsewhere
      silently reassigns this one; saying so beats a silent redirect.
    * `json=True`        → a 403 JSON body, for endpoints the browser fetches.
    """
    allowed = {str(role) for role in roles}

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_authenticated and user.role in allowed:
                return view(request, *args, **kwargs)
            if json:
                return JsonResponse(
                    {"ok": False, "error": message or "You are not signed in to do that."},
                    status=403,
                )
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
            if redirect_to:
                if message:
                    messages.error(request, message)
                return redirect(redirect_to)
            return render(
                request,
                "errors/wrong_account.html",
                {"role_home": role_home(user)},
                status=403,
            )

        return wrapped

    return decorator
