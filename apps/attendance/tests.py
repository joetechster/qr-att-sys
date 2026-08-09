import pickle
from unittest import mock

import numpy as np
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import StudentProfile, User
from apps.courses.models import Course, Enrollment
from apps.lectures.models import Lecture, QRToken


# A 1x1 JPEG is enough: face detection is mocked out, the view only needs the
# data URL to decode to *some* bytes.
PIXEL_DATA_URL = (
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL"
    "DBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)


class ScanRedirectTests(TestCase):
    """A successful scan should hand the student back to their dashboard."""

    def setUp(self):
        lecturer = User.objects.create_user("lec1", password="x", role=User.Role.LECTURER)
        self.student = User.objects.create_user(
            "stu1", password="x", role=User.Role.STUDENT
        )
        StudentProfile.objects.create(
            user=self.student,
            matric_number="PCU/2024/001",
            department="CS",
            face_encoding=pickle.dumps(np.zeros(128)),
        )
        course = Course.objects.create(
            code="CSC301", title="Compilers", department="CS", lecturer=lecturer
        )
        Enrollment.objects.create(student=self.student, course=course)
        now = timezone.now()
        self.lecture = Lecture.objects.create(
            course=course,
            title="Week 1",
            scheduled_start=now,
            scheduled_end=now + timezone.timedelta(hours=2),
            status=Lecture.Status.ACTIVE,
            created_by=lecturer,
        )
        self.token = QRToken.objects.create(lecture=self.lecture)
        self.client.force_login(self.student)

    def post_scan(self):
        return self.client.post(
            reverse("scan_verify"),
            {"token": str(self.token.token), "image": PIXEL_DATA_URL},
        )

    @mock.patch("apps.attendance.views.compare_to_encoding", return_value=0.2)
    def test_success_returns_the_dashboard_url_and_queues_a_message(self, _compare):
        response = self.post_scan()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["redirect_url"], reverse("student:dashboard"))

        # The message is rendered by base.html on the page we redirect to.
        dashboard = self.client.get(reverse("student:dashboard"))
        self.assertContains(dashboard, "Attendance marked for CSC301")

    @mock.patch("apps.attendance.views.compare_to_encoding", return_value=0.9)
    def test_a_failed_face_match_carries_no_redirect(self, _compare):
        response = self.post_scan()
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("redirect_url", response.json())


class ScanRoleGateTests(TestCase):
    """The scanner fetches /scan/verify/, so a refusal must stay JSON.

    An HTML login redirect here surfaces to the student as an unreadable parse
    error rather than a message they can act on.
    """

    def setUp(self):
        self.lecturer = User.objects.create_user(
            "lec9", password="x", role=User.Role.LECTURER
        )

    def test_a_non_student_gets_json_not_html(self):
        self.client.force_login(self.lecturer)
        response = self.client.post(reverse("scan_verify"), {"token": "x", "image": ""})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertFalse(response.json()["ok"])
        self.assertIn("students", response.json()["error"])

    def test_an_anonymous_scan_is_also_json(self):
        response = self.client.post(reverse("scan_verify"), {"token": "x", "image": ""})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_the_scan_page_itself_tells_a_lecturer_what_is_wrong(self):
        self.client.force_login(self.lecturer)
        response = self.client.get(reverse("scan_page"))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "errors/wrong_account.html")
