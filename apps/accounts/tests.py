import pickle
from datetime import timedelta
from unittest import mock

import numpy as np
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import StudentProfile, User


NEW_PASSWORD = "wrGh3-Quiet-Harbour"

# A 1x1 JPEG: face detection is mocked out, the view only needs the data URL to
# decode to *some* bytes.
PIXEL_DATA_URL = (
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL"
    "DBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)


class ForcePasswordChangeMiddlewareTests(TestCase):
    def setUp(self):
        self.lecturer = User.objects.create_user(
            "lec1", password="temp-pass-1234", role=User.Role.LECTURER
        )
        self.lecturer.must_change_password = True
        self.lecturer.save(update_fields=("must_change_password",))
        self.client.force_login(self.lecturer)

    def test_ordinary_pages_redirect_to_the_password_change_form(self):
        for target in ("lecturer:dashboard", "course_list", "profile"):
            with self.subTest(target=target):
                response = self.client.get(reverse(target))
                self.assertRedirects(response, reverse("password_change"))

    def test_admin_is_not_a_side_door(self):
        response = self.client.get("/admin/")
        self.assertRedirects(
            response, reverse("password_change"), fetch_redirect_response=False
        )

    def test_the_password_change_page_itself_is_reachable(self):
        response = self.client.get(reverse("password_change"))
        self.assertEqual(response.status_code, 200)

    def test_logout_stays_reachable_so_the_user_is_not_trapped(self):
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(reverse("password_change"), response["Location"])

    def test_changing_the_password_clears_the_flag_and_releases_the_user(self):
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": "temp-pass-1234",
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("profile"))
        self.lecturer.refresh_from_db()
        self.assertFalse(self.lecturer.must_change_password)
        self.assertEqual(self.client.get(reverse("lecturer:dashboard")).status_code, 200)

    def test_users_without_the_flag_are_untouched(self):
        student = User.objects.create_user(
            "stu1", password="x", role=User.Role.STUDENT
        )
        self.client.force_login(student)
        self.assertEqual(self.client.get(reverse("student:dashboard")).status_code, 200)


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "lec1", password="x", role=User.Role.LECTURER, first_name="Old"
        )
        self.client.force_login(self.user)

    def test_anonymous_users_are_sent_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response["Location"])

    def test_every_role_can_open_their_profile(self):
        for role in (
            User.Role.STUDENT,
            User.Role.LECTURER,
            User.Role.HOD,
            User.Role.VICE_CHANCELLOR,
        ):
            with self.subTest(role=role):
                user = User.objects.create_user(f"u-{role}", password="x", role=role)
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse("profile")).status_code, 200)

    def test_name_and_email_can_be_edited(self):
        response = self.client.post(
            reverse("profile"),
            {"first_name": "Jumoke", "last_name": "Adeyemi", "email": "j@pcu.edu.ng"},
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), "Jumoke Adeyemi")
        self.assertEqual(self.user.email, "j@pcu.edu.ng")

    def test_role_cannot_be_escalated_through_the_profile_form(self):
        self.client.post(
            reverse("profile"),
            {"first_name": "J", "last_name": "A", "email": "", "role": User.Role.HOD},
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.LECTURER)


def _encoding():
    return pickle.dumps(np.zeros(128))


@mock.patch("apps.accounts.views.encode_face", return_value=_encoding())
class StudentRegistrationTests(TestCase):
    url = "/auth/register/student/"

    def payload(self, **overrides):
        data = {
            "first_name": "Ada",
            "last_name": "Okafor",
            "username": "ada.okafor",
            "email": "ada@pcu.edu.ng",
            "matric_number": "PCU/CSC/21/0001",
            "department": "Computer Science",
            "level": "300",
            "password1": NEW_PASSWORD,
            "password2": NEW_PASSWORD,
            "face_image_data": PIXEL_DATA_URL,
        }
        data.update(overrides)
        return data

    def test_the_form_renders_both_wizard_steps(self, _encode):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-step="1"')
        self.assertContains(response, 'data-step="2"')

    def test_a_valid_signup_creates_the_account_and_signs_them_in(self, _encode):
        response = self.client.post(self.url, self.payload())
        self.assertRedirects(response, "/student/")

        user = User.objects.get(username="ada.okafor")
        self.assertEqual(user.role, User.Role.STUDENT)
        profile = StudentProfile.objects.get(user=user)
        self.assertEqual(profile.matric_number, "PCU/CSC/21/0001")
        self.assertEqual(profile.level, "300")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_a_duplicate_matric_number_is_reported_on_its_own_field(self, _encode):
        self.client.post(self.url, self.payload())
        self.client.logout()  # a successful signup signs you in
        response = self.client.post(
            self.url, self.payload(username="second.student", email="")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "matric_number",
            "That matric number is already registered.",
        )
        self.assertEqual(User.objects.count(), 1)

    def test_the_captured_photo_survives_a_validation_error(self, _encode):
        """A typo in one field must not cost the student their photo."""
        self.client.post(self.url, self.payload())
        self.client.logout()
        # Same username as the account that now exists: the form fails, but the photo
        # submitted alongside it must come back in the re-rendered hidden field.
        response = self.client.post(
            self.url, self.payload(matric_number="PCU/CSC/21/0002")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, PIXEL_DATA_URL)

    def test_submitting_without_a_photo_says_so_in_plain_words(self, _encode):
        response = self.client.post(self.url, self.payload(face_image_data=""))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "face_image_data",
            "Take a photo of yourself before creating your account.",
        )
        self.assertFalse(User.objects.exists())

    def test_weak_password_errors_land_on_the_password_field(self, _encode):
        """Django puts these on password2; the browser flags password1. Keep them together."""
        response = self.client.post(
            self.url, self.payload(password1="12345678", password2="mismatched")
        )
        form = response.context["form"]
        self.assertIn("This password is entirely numeric.", form.errors["password1"])
        self.assertNotIn("password2", str(form.errors["password1"]))
        # ...and a mismatch is still reported on its own field, in the same pass.
        self.assertTrue(form.errors["password2"])

    def test_a_junk_photo_is_a_non_field_error(self, _encode):
        response = self.client.post(self.url, self.payload(face_image_data="not-an-image"))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            None,
            "Face image was not captured. Allow camera access and try again.",
        )

    def test_a_signed_in_user_is_sent_to_their_own_dashboard(self, _encode):
        lecturer = User.objects.create_user("lec9", password="x", role=User.Role.LECTURER)
        self.client.force_login(lecturer)
        response = self.client.get(self.url)
        self.assertRedirects(response, "/lecturer/", fetch_redirect_response=False)


class StudentAttendanceStatsTests(TestCase):
    """Per-course and overall attendance on the student dashboard.

    There are no absence rows — a record existing *is* "present" — so the
    denominator has to be derived. Only ENDED lectures count.
    """

    def setUp(self):
        from apps.attendance.models import AttendanceRecord
        from apps.courses.models import Course, Enrollment
        from apps.lectures.models import Lecture

        self.AttendanceRecord = AttendanceRecord
        self.Lecture = Lecture

        self.lecturer = User.objects.create_user(
            "lec1", password="x", role=User.Role.LECTURER
        )
        self.student = User.objects.create_user(
            "stu1", password="x", role=User.Role.STUDENT
        )
        self.course = Course.objects.create(
            code="CSC301", title="Compilers", unit=3, department="CS",
            lecturer=self.lecturer,
        )
        Enrollment.objects.create(student=self.student, course=self.course)
        self.client.force_login(self.student)

    def _lecture(self, status, title="Session"):
        return self.Lecture.objects.create(
            course=self.course,
            title=title,
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=1),
            status=status,
            created_by=self.lecturer,
        )

    def _mark(self, lecture, student=None):
        return self.AttendanceRecord.objects.create(
            lecture=lecture, student=student or self.student, face_match_distance=0.1
        )

    def rows(self):
        return self.client.get(reverse("student:dashboard")).context["rows"]

    def test_only_finished_lectures_count_towards_the_total(self):
        self._mark(self._lecture(self.Lecture.Status.ENDED))
        self._lecture(self.Lecture.Status.ENDED)
        # Neither of these has happened yet, so neither is an absence.
        self._lecture(self.Lecture.Status.ACTIVE)
        self._lecture(self.Lecture.Status.SCHEDULED)

        row = self.rows()[0]
        self.assertEqual(row["held"], 2)
        self.assertEqual(row["attended"], 1)
        self.assertEqual(row["percent"], 50)

    def test_a_class_in_progress_does_not_dent_the_percentage(self):
        self._mark(self._lecture(self.Lecture.Status.ENDED))
        self.assertEqual(self.rows()[0]["percent"], 100)
        self._lecture(self.Lecture.Status.ACTIVE)
        self.assertEqual(self.rows()[0]["percent"], 100)

    def test_attendance_can_never_exceed_the_classes_held(self):
        """A record on a lecture that never ended must not inflate the count."""
        self._mark(self._lecture(self.Lecture.Status.ACTIVE))
        self._mark(self._lecture(self.Lecture.Status.ENDED))

        row = self.rows()[0]
        self.assertEqual(row["held"], 1)
        self.assertEqual(row["attended"], 1)
        self.assertEqual(row["percent"], 100)

    def test_a_course_with_no_finished_classes_reports_no_rate(self):
        self._lecture(self.Lecture.Status.SCHEDULED)
        row = self.rows()[0]
        self.assertEqual(row["held"], 0)
        self.assertIsNone(row["percent"])  # and no ZeroDivisionError

    def test_another_students_attendance_is_not_counted(self):
        other = User.objects.create_user("stu2", password="x", role=User.Role.STUDENT)
        lecture = self._lecture(self.Lecture.Status.ENDED)
        self._mark(lecture, student=other)

        row = self.rows()[0]
        self.assertEqual(row["held"], 1)
        self.assertEqual(row["attended"], 0)

    def test_overall_figures_span_every_enrolled_course(self):
        from apps.courses.models import Course, Enrollment

        second = Course.objects.create(
            code="CSC302", title="Networks", unit=2, department="CS",
            lecturer=self.lecturer,
        )
        Enrollment.objects.create(student=self.student, course=second)

        self._mark(self._lecture(self.Lecture.Status.ENDED))
        self._lecture(self.Lecture.Status.ENDED)
        self.Lecture.objects.create(
            course=second, title="S", scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=1),
            status=self.Lecture.Status.ENDED, created_by=self.lecturer,
        )

        context = self.client.get(reverse("student:dashboard")).context
        self.assertEqual(context["total_held"], 3)
        self.assertEqual(context["total_attended"], 1)
        self.assertEqual(context["overall_percent"], 33)
        self.assertEqual(context["course_count"], 2)

    def test_a_student_without_a_profile_still_sees_their_courses(self):
        """Enrollments used to be keyed off StudentProfile, not the user."""
        self.assertFalse(hasattr(self.student, "student_profile"))
        self.assertEqual(len(self.rows()), 1)


class WrongAccountTests(TestCase):
    """One session per browser is correct; hiding it from the user was not."""

    def setUp(self):
        self.student = User.objects.create_user(
            "stu1", password="x", role=User.Role.STUDENT
        )
        self.hod = User.objects.create_user(
            "ada.hod", password="x", role=User.Role.HOD, first_name="Ada", last_name="Nwosu"
        )

    def test_the_page_names_the_account_actually_signed_in(self):
        self.client.force_login(self.hod)
        response = self.client.get(reverse("student:dashboard"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Ada Nwosu", status_code=403)
        self.assertContains(response, "Head of Department", status_code=403)

    def test_it_offers_a_way_out_in_both_directions(self):
        self.client.force_login(self.hod)
        response = self.client.get(reverse("student:dashboard"))
        self.assertContains(response, "/hod/", status_code=403)
        self.assertContains(response, reverse("logout"), status_code=403)

    def test_anonymous_visitors_are_sent_to_login_keeping_their_destination(self):
        response = self.client.get(reverse("student:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response["Location"])
        self.assertIn("next=/student/", response["Location"])

    def test_the_login_page_no_longer_bounces_a_signed_in_user(self):
        """redirect_authenticated_user made switching accounts impossible."""
        self.client.force_login(self.hod)
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already signed in")

    def test_signing_in_as_someone_else_replaces_the_session(self):
        self.client.force_login(self.hod)
        self.client.post(
            reverse("login"), {"username": "stu1", "password": "x"}
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.student.pk)
        self.assertEqual(self.client.get(reverse("student:dashboard")).status_code, 200)


class ErrorPageTests(TestCase):
    def test_an_unknown_url_renders_the_designed_404(self):
        # DEBUG bypasses handler404 entirely, which is why it is switchable.
        with self.settings(DEBUG=False):
            response = self.client.get("/definitely-not-a-real-page/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "We couldn't find that page", status_code=404)
