"""Where each role belongs.

Lives apart from `views.py` so `decorators.py` can import it without pulling the
whole view module in — the decorators are imported *by* several view modules.
"""
from __future__ import annotations


def role_home(user) -> str:
    """The landing page for a signed-in user, by role."""
    from .models import User

    if user.role == User.Role.STUDENT:
        return "/student/"
    if user.role in {User.Role.LECTURER, User.Role.COURSE_REP}:
        return "/lecturer/"
    if user.role == User.Role.HOD:
        return "/hod/"
    return "/admin/"
