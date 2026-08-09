from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course

from .forms import LectureForm
from .models import Lecture, QRToken


class LectureCreationTests(TestCase):
    """Lecturers schedule lectures; they no longer create courses while doing it."""

    def setUp(self):
        self.lecturer = User.objects.create_user(
            "lec1", password="x", role=User.Role.LECTURER
        )
        self.other = User.objects.create_user(
            "lec2", password="x", role=User.Role.LECTURER
        )
        self.mine = Course.objects.create(
            code="CSC301", title="Compilers", department="CS", lecturer=self.lecturer
        )
        self.theirs = Course.objects.create(
            code="CSC305", title="OS", department="CS", lecturer=self.other
        )
        self.client.force_login(self.lecturer)

    def payload(self, course):
        start = timezone.now()
        return {
            "course": course.pk,
            "title": "Week 1",
            "scheduled_start": start.strftime("%Y-%m-%dT%H:%M"),
            "scheduled_end": (start + timezone.timedelta(hours=2)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
        }

    def test_the_form_no_longer_offers_inline_course_creation(self):
        form = LectureForm(user=self.lecturer)
        for gone in ("course_mode", "new_course_code", "new_course_title"):
            self.assertNotIn(gone, form.fields)

    def test_course_is_required(self):
        form = LectureForm(data={"title": "Week 1"}, user=self.lecturer)
        self.assertFalse(form.is_valid())
        self.assertIn("course", form.errors)

    def test_a_lecturer_only_sees_their_own_courses(self):
        form = LectureForm(user=self.lecturer)
        codes = set(form.fields["course"].queryset.values_list("code", flat=True))
        self.assertEqual(codes, {"CSC301"})

    def test_lecture_is_created_against_an_assigned_course(self):
        response = self.client.post(
            reverse("lecturer:create_lecture"), self.payload(self.mine)
        )
        lecture = Lecture.objects.get()
        self.assertRedirects(
            response, reverse("lecturer:lecture_detail", args=[lecture.pk])
        )
        self.assertEqual(lecture.course, self.mine)
        self.assertEqual(lecture.created_by, self.lecturer)

    def test_another_lecturers_course_is_rejected(self):
        response = self.client.post(
            reverse("lecturer:create_lecture"), self.payload(self.theirs)
        )
        self.assertEqual(response.status_code, 200)  # redisplayed with errors
        self.assertFalse(Lecture.objects.exists())

    def test_starting_a_lecture_opens_the_qr_display(self):
        self.client.post(reverse("lecturer:create_lecture"), self.payload(self.mine))
        lecture = Lecture.objects.get()
        response = self.client.post(
            reverse("lecturer:start_lecture", args=[lecture.pk])
        )
        self.assertRedirects(response, reverse("lecturer:qr_display", args=[lecture.pk]))
        lecture.refresh_from_db()
        self.assertEqual(lecture.status, Lecture.Status.ACTIVE)
        self.assertEqual(QRToken.objects.filter(lecture=lecture, is_used=False).count(), 1)

    def test_students_cannot_reach_the_lecture_form(self):
        student = User.objects.create_user("stu1", password="x", role=User.Role.STUDENT)
        self.client.force_login(student)
        response = self.client.get(reverse("lecturer:create_lecture"))
        # 403 with an explanation, not a redirect: bouncing a signed-in user to
        # the login page reads as being logged out at random.
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "errors/wrong_account.html")
