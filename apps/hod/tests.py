from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.courses.models import Course


def csv_upload(text: str, name: str = "upload.csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, text.encode("utf-8"), content_type="text/csv")


class RoleGateTests(TestCase):
    """Course creation belongs to the HOD now, not the lecturer."""

    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.lecturer = User.objects.create_user(
            "lec1", password="x", role=User.Role.LECTURER
        )

    def test_hod_can_open_course_form(self):
        self.client.force_login(self.hod)
        self.assertEqual(self.client.get(reverse("course_create")).status_code, 200)

    def test_lecturer_is_bounced_from_course_form(self):
        self.client.force_login(self.lecturer)
        response = self.client.get(reverse("course_create"))
        self.assertRedirects(response, reverse("course_list"))

    def test_lecturer_is_told_the_hod_console_is_not_theirs(self):
        """A silent bounce to /auth/login/ read as "the app logged me out"."""
        self.client.force_login(self.lecturer)
        for name in ("hod:dashboard", "hod:lecturers", "hod:import_courses", "hod:courses"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 403)
                self.assertTemplateUsed(response, "errors/wrong_account.html")
                self.assertContains(response, "lec1", status_code=403)

    def test_anonymous_visitors_keep_their_destination(self):
        response = self.client.get(reverse("hod:courses"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response["Location"])
        self.assertIn("next=/hod/courses/", response["Location"])

    def test_lecturer_can_still_open_the_lecture_form(self):
        self.client.force_login(self.lecturer)
        response = self.client.get(reverse("lecturer:create_lecture"))
        self.assertEqual(response.status_code, 200)
        # The inline "create a new course" mode is gone.
        self.assertNotContains(response, "course_mode")


class ConsoleRenderTests(TestCase):
    """Every console page renders — these templates have no other coverage."""

    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        lecturer = User.objects.create_user(
            "j.adeyemi", password="x", role=User.Role.LECTURER
        )
        Course.objects.create(
            code="CSC301", title="Compilers", unit=3, department="CS", lecturer=lecturer
        )
        self.client.force_login(self.hod)

    def test_all_hod_pages_render(self):
        for name in (
            "hod:dashboard",
            "hod:courses",
            "hod:lecturers",
            "hod:create_lecturer",
            "hod:import_lecturers",
            "hod:import_courses",
            "hod:complaints",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_dashboard_counts_reflect_the_database(self):
        response = self.client.get(reverse("hod:dashboard"))
        self.assertEqual(response.context["course_count"], 1)
        self.assertEqual(response.context["lecturer_count"], 1)


class LecturerImportTests(TestCase):
    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.client.force_login(self.hod)
        self.url = reverse("hod:import_lecturers")

    def post(self, text):
        return self.client.post(self.url, {"file": csv_upload(text)})

    def test_creates_skips_and_errors_are_reported_separately(self):
        User.objects.create_user("b.okoro", password="x", role=User.Role.LECTURER)
        response = self.post(
            "username,first_name,last_name,email\n"
            "j.adeyemi,Jumoke,Adeyemi,j.adeyemi@pcu.edu.ng\n"
            "b.okoro,Bright,Okoro,b.okoro@pcu.edu.ng\n"
            ",Nameless,Row,\n"
        )
        result = response.context["result"]
        self.assertEqual([row["username"] for row in result["created"]], ["j.adeyemi"])
        self.assertEqual([row["username"] for row in result["skipped"]], ["b.okoro"])
        self.assertEqual(len(result["errors"]), 1)
        # Line numbers are 1-based including the header, so the bad row is line 4.
        self.assertEqual(result["errors"][0]["line"], 4)

    def test_created_lecturers_must_change_their_password(self):
        self.post("username,first_name,last_name\nj.adeyemi,Jumoke,Adeyemi\n")
        lecturer = User.objects.get(username="j.adeyemi")
        self.assertEqual(lecturer.role, User.Role.LECTURER)
        self.assertTrue(lecturer.must_change_password)

    def test_generated_password_actually_authenticates(self):
        response = self.post("username,first_name,last_name\nj.adeyemi,Jumoke,Adeyemi\n")
        password = response.context["result"]["created"][0]["password"]
        self.assertTrue(
            self.client.login(username="j.adeyemi", password=password),
            "The password shown to the HOD must be the one that was set.",
        )

    def test_bom_prefixed_header_is_still_recognised(self):
        # Excel writes CSVs with a UTF-8 BOM; without utf-8-sig the first
        # column name would come through as "﻿username".
        upload = SimpleUploadedFile(
            "excel.csv",
            "﻿username,first_name,last_name\nj.adeyemi,Jumoke,Adeyemi\n".encode("utf-8"),
            content_type="text/csv",
        )
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(len(response.context["result"]["created"]), 1)

    def test_missing_column_is_rejected_before_any_row_is_created(self):
        response = self.post("username,first_name\nj.adeyemi,Jumoke\n")
        self.assertIsNone(response.context.get("result"))
        self.assertFalse(User.objects.filter(username="j.adeyemi").exists())
        self.assertContains(response, "missing required column")

    def test_non_csv_upload_is_rejected(self):
        upload = SimpleUploadedFile("staff.txt", b"username\nx\n", content_type="text/plain")
        response = self.client.post(self.url, {"file": upload})
        self.assertFormError(response.context["form"], "file", "Upload a .csv file.")


class CourseImportTests(TestCase):
    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.lecturer = User.objects.create_user(
            "j.adeyemi", password="x", role=User.Role.LECTURER
        )
        self.client.force_login(self.hod)
        self.url = reverse("hod:import_courses")

    def post(self, text):
        return self.client.post(self.url, {"file": csv_upload(text)})

    HEADER = "lecturer,code,title,unit,department\n"

    def test_rows_are_created_skipped_and_errored(self):
        Course.objects.create(
            code="CSC305", title="OS", unit=2, department="CS", lecturer=self.lecturer
        )
        response = self.post(
            self.HEADER
            + "j.adeyemi,CSC301,Intro to Compilers,3,Computer Science\n"
            + "j.adeyemi,CSC305,Operating Systems,2,Computer Science\n"
            + "nobody,CSC307,Networks,3,Computer Science\n"
        )
        result = response.context["result"]
        self.assertEqual([row["code"] for row in result["created"]], ["CSC301"])
        self.assertEqual([row["code"] for row in result["skipped"]], ["CSC305"])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("nobody", result["errors"][0]["detail"])
        self.assertFalse(Course.objects.filter(code="CSC307").exists())

    def test_lecturer_is_taken_from_the_row_not_the_uploading_hod(self):
        self.post(self.HEADER + "j.adeyemi,CSC301,Intro to Compilers,3,Computer Science\n")
        course = Course.objects.get(code="CSC301")
        self.assertEqual(course.lecturer, self.lecturer)
        self.assertEqual(course.unit, 3)

    def test_a_non_lecturer_username_is_an_error(self):
        User.objects.create_user("s.bello", password="x", role=User.Role.STUDENT)
        response = self.post(self.HEADER + "s.bello,CSC301,Compilers,3,Computer Science\n")
        self.assertEqual(len(response.context["result"]["errors"]), 1)
        self.assertFalse(Course.objects.exists())

    def test_unit_must_be_a_whole_number_in_range(self):
        response = self.post(
            self.HEADER
            + "j.adeyemi,CSC301,Compilers,abc,Computer Science\n"
            + "j.adeyemi,CSC302,Networks,0,Computer Science\n"
            + "j.adeyemi,CSC303,Graphics,13,Computer Science\n"
            + "j.adeyemi,CSC304,Databases,4,Computer Science\n"
        )
        result = response.context["result"]
        self.assertEqual([row["code"] for row in result["created"]], ["CSC304"])
        self.assertEqual(len(result["errors"]), 3)
        self.assertIn("abc", result["errors"][0]["detail"])
        self.assertEqual(Course.objects.count(), 1)

    def test_the_older_lecturer_username_heading_still_works(self):
        """Files exported before the column was renamed must keep importing."""
        response = self.post(
            "lecturer_username,code,title,unit,department\n"
            "j.adeyemi,CSC301,Compilers,3,Computer Science\n"
        )
        self.assertEqual(len(response.context["result"]["created"]), 1)
        self.assertEqual(Course.objects.get(code="CSC301").lecturer, self.lecturer)

    def test_a_file_without_unit_is_rejected_before_any_row_is_created(self):
        response = self.post(
            "lecturer,code,title,department\nj.adeyemi,CSC301,Compilers,CS\n"
        )
        self.assertIsNone(response.context.get("result"))
        self.assertContains(response, "missing required column")
        self.assertFalse(Course.objects.exists())

    def test_an_unknown_department_is_reported_per_row(self):
        """The importer holds the same vocabulary as the course form's dropdown.

        Without this, a strict dropdown beside a permissive importer just moves
        free text into the column through the back door.
        """
        response = self.post(
            self.HEADER
            + "j.adeyemi,CSC301,Compilers,3,Maths\n"
            + "j.adeyemi,CSC302,Networks,3,Cybersecurity\n"
        )
        result = response.context["result"]
        self.assertEqual([row["code"] for row in result["created"]], ["CSC302"])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("Maths", result["errors"][0]["detail"])
        self.assertIn("Cybersecurity", result["errors"][0]["detail"])

    def test_a_department_is_stored_in_its_canonical_casing(self):
        self.post(self.HEADER + "j.adeyemi,CSC301,Compilers,3, computer science \n")
        self.assertEqual(
            Course.objects.get(code="CSC301").department, "Computer Science"
        )


class ImportTemplateTests(TestCase):
    """The starter file has to be importable as-is, header and all."""

    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.client.force_login(self.hod)

    def download(self, name):
        response = self.client.get(reverse(name))
        self.assertEqual(response.status_code, 200)
        return response

    def test_templates_download_as_attachments(self):
        for name, filename in (
            ("hod:lecturer_template", "lecturers_template.csv"),
            ("hod:course_template", "courses_template.csv"),
        ):
            with self.subTest(name=name):
                response = self.download(name)
                self.assertIn("text/csv", response["Content-Type"])
                self.assertIn(filename, response["Content-Disposition"])

    def test_the_lecturer_template_imports_without_edits(self):
        text = self.download("hod:lecturer_template").content.decode("utf-8-sig")
        response = self.client.post(
            reverse("hod:import_lecturers"), {"file": csv_upload(text)}
        )
        result = response.context["result"]
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["created"]), 2)
        # Blank password column means a generated one, not an empty password.
        self.assertTrue(all(row["password"] for row in result["created"]))

    def test_the_course_template_imports_once_its_lecturers_exist(self):
        for username in ("j.adeyemi", "b.okoro"):
            User.objects.create_user(username, password="x", role=User.Role.LECTURER)
        text = self.download("hod:course_template").content.decode("utf-8-sig")
        response = self.client.post(
            reverse("hod:import_courses"), {"file": csv_upload(text)}
        )
        result = response.context["result"]
        self.assertEqual(result["errors"], [])
        self.assertEqual(Course.objects.count(), 2)

    def test_a_lecturer_cannot_download_the_templates(self):
        lecturer = User.objects.create_user(
            "lec1", password="x", role=User.Role.LECTURER
        )
        self.client.force_login(lecturer)
        for name in ("hod:lecturer_template", "hod:course_template"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)


class CourseEditTests(TestCase):
    """Reassigning a course was previously only possible in Django admin.

    These post `department="CS"`, which is not in the department vocabulary —
    they pass because `CourseForm` offers a course's stored department back
    under "Currently set". That is deliberate coverage of the escape hatch from
    this side, not stale fixture data: an HOD reassigning a legacy course's
    lecturer must not be forced to reclassify it first.
    """

    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.old = User.objects.create_user(
            "j.adeyemi", password="x", role=User.Role.LECTURER
        )
        self.new = User.objects.create_user(
            "b.okoro", password="x", role=User.Role.LECTURER
        )
        self.course = Course.objects.create(
            code="CSC301", title="Compilers", unit=3, department="CS", lecturer=self.old
        )
        self.client.force_login(self.hod)

    def test_hod_can_hand_a_course_to_a_different_lecturer(self):
        response = self.client.post(
            reverse("hod:course_edit", args=[self.course.pk]),
            {
                "code": "CSC301",
                "title": "Compilers",
                "unit": 3,
                "department": "CS",
                "lecturer": self.new.pk,
                "course_rep": "",
            },
        )
        self.assertRedirects(response, reverse("hod:courses"))
        self.course.refresh_from_db()
        self.assertEqual(self.course.lecturer, self.new)

    def test_unit_outside_the_allowed_range_is_refused(self):
        response = self.client.post(
            reverse("hod:course_edit", args=[self.course.pk]),
            {
                "code": "CSC301",
                "title": "Compilers",
                "unit": 99,
                "department": "CS",
                "lecturer": self.old.pk,
                "course_rep": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["unit"])
        self.course.refresh_from_db()
        self.assertEqual(self.course.unit, 3)


class LecturerCreateViewTests(TestCase):
    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.client.force_login(self.hod)

    def test_creating_a_lecturer_shows_the_password_once(self):
        response = self.client.post(
            reverse("hod:create_lecturer"),
            {
                "username": "j.adeyemi",
                "first_name": "Jumoke",
                "last_name": "Adeyemi",
                "email": "j.adeyemi@pcu.edu.ng",
            },
        )
        self.assertEqual(response.status_code, 200)
        password = response.context["password"]
        lecturer = User.objects.get(username="j.adeyemi")
        self.assertEqual(lecturer.role, User.Role.LECTURER)
        self.assertTrue(lecturer.must_change_password)
        self.assertTrue(lecturer.check_password(password))
