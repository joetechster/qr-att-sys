from django.test import TestCase

from apps.accounts.models import User
from apps.courses.departments import DEPARTMENT_NAMES
from apps.courses.forms import CourseForm
from apps.courses.models import Course


class CourseDepartmentFormTests(TestCase):
    """Department is a fixed vocabulary, with one deliberate escape hatch."""

    def setUp(self):
        self.lecturer = User.objects.create_user(
            "j.adeyemi", password="x", role=User.Role.LECTURER
        )

    def payload(self, **overrides):
        data = {
            "code": "CSC301",
            "title": "Compilers",
            "unit": 3,
            "department": "Computer Science",
            "lecturer": self.lecturer.pk,
            "course_rep": "",
        }
        data.update(overrides)
        return data

    def test_the_dropdown_is_grouped_by_faculty(self):
        choices = dict(CourseForm().fields["department"].choices)
        self.assertIn("Faculty of Computer Science", choices)
        self.assertIn("Faculty of Natural Sciences", choices)
        self.assertIn("Faculty of Social Sciences", choices)
        self.assertEqual(
            [value for value, _ in choices["Faculty of Computer Science"]],
            ["Cybersecurity", "Software Engineering", "Computer Science"],
        )

    def test_the_first_option_is_blank_so_nothing_is_preselected(self):
        first_value, first_label = CourseForm().fields["department"].choices[0]
        self.assertEqual(first_value, "")
        self.assertEqual(first_label, "Select a department")

    def test_every_listed_department_is_accepted(self):
        for index, name in enumerate(DEPARTMENT_NAMES):
            with self.subTest(department=name):
                form = CourseForm(
                    self.payload(code=f"CSC{300 + index}", department=name)
                )
                self.assertTrue(form.is_valid(), form.errors)

    def test_a_department_outside_the_list_is_refused_on_create(self):
        form = CourseForm(self.payload(department="Mathematics"))
        self.assertFalse(form.is_valid())
        self.assertIn("department", form.errors)

    def test_a_blank_department_is_refused(self):
        form = CourseForm(self.payload(department=""))
        self.assertFalse(form.is_valid())
        self.assertIn("department", form.errors)

    def test_a_legacy_department_stays_selectable_when_editing(self):
        """The escape hatch: reassigning a legacy course's lecturer must not
        force the HOD to reclassify the course first."""
        course = Course.objects.create(
            code="MTH101",
            title="Elementary Mathematics",
            unit=3,
            department="Mathematics",
            lecturer=self.lecturer,
        )
        choices = dict(CourseForm(instance=course).fields["department"].choices)
        # Compared as a list: ChoiceField's setter normalises the nested groups.
        self.assertEqual(
            list(choices["Currently set"]), [("Mathematics", "Mathematics")]
        )

        form = CourseForm(
            self.payload(code="MTH101", title="Elementary Mathematics",
                         department="Mathematics"),
            instance=course,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_a_legacy_department_is_not_offered_on_a_blank_form(self):
        Course.objects.create(
            code="MTH101",
            title="Elementary Mathematics",
            unit=3,
            department="Mathematics",
            lecturer=self.lecturer,
        )
        self.assertNotIn("Currently set", dict(CourseForm().fields["department"].choices))

    def test_editing_a_listed_department_gets_no_escape_hatch_group(self):
        course = Course.objects.create(
            code="CSC301",
            title="Compilers",
            unit=3,
            department="Cybersecurity",
            lecturer=self.lecturer,
        )
        choices = dict(CourseForm(instance=course).fields["department"].choices)
        self.assertNotIn("Currently set", choices)
