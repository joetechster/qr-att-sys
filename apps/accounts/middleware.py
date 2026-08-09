"""Pin accounts holding a temporary password to the password-change page."""
from __future__ import annotations

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

# Reachable while a forced password change is pending. Without login/logout in
# here the user would be trapped: the redirect would fire before they could
# sign out. `/admin/` is deliberately absent, so a temp-password account can't
# slip in through the side door.
EXEMPT_URL_NAMES = ("password_change", "login", "logout")


class ForcePasswordChangeMiddleware:
    """Redirect `must_change_password` users to /auth/password/change/."""

    def __init__(self, get_response):
        self.get_response = get_response
        self._exempt_paths: set[str] | None = None

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.must_change_password:
            if not self._is_exempt(request.path):
                return redirect("password_change")
        return self.get_response(request)

    def _is_exempt(self, path: str) -> bool:
        if self._exempt_paths is None:
            # Resolved on first use, not at import time — the URLConf isn't
            # loaded yet when middleware is instantiated.
            self._exempt_paths = {reverse(name) for name in EXEMPT_URL_NAMES}
        if path in self._exempt_paths:
            return True
        for prefix in (settings.STATIC_URL, settings.MEDIA_URL):
            if prefix and path.startswith("/" + prefix.lstrip("/")):
                return True
        return False
