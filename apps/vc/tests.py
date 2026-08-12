from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.complaints.models import Complaint


class VcConsoleTests(TestCase):
    """The VC sees escalated complaints and nothing else, read-only."""

    def setUp(self):
        self.vc = User.objects.create_user(
            "vc1", password="x", role=User.Role.VICE_CHANCELLOR
        )
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.student = User.objects.create_user(
            "stu1", password="x", role=User.Role.STUDENT
        )
        self.escalated = Complaint.objects.create(
            student=self.student,
            subject="Marks never uploaded",
            body="Two months and counting.",
            escalated_at=timezone.now(),
            escalated_by=self.hod,
            escalation_note="Department cannot resolve this.",
        )
        self.plain = Complaint.objects.create(
            student=self.student, subject="Projector is broken", body="Room 4."
        )

    def test_vc_lands_on_their_own_console(self):
        response = self.client.post(
            reverse("login"), {"username": "vc1", "password": "x"}
        )
        self.assertRedirects(response, "/vc/", fetch_redirect_response=False)

    def test_only_escalated_complaints_are_listed(self):
        self.client.force_login(self.vc)
        response = self.client.get(reverse("vc:complaints"))
        self.assertContains(response, "Marks never uploaded")
        self.assertNotContains(response, "Projector is broken")

    def test_an_unescalated_complaint_is_not_reachable_by_id(self):
        self.client.force_login(self.vc)
        response = self.client.get(
            reverse("vc:complaint_detail", args=[self.plain.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_the_dashboard_counts_unresolved_escalations(self):
        self.client.force_login(self.vc)
        response = self.client.get(reverse("vc:dashboard"))
        self.assertEqual(response.context["unresolved_count"], 1)
        self.assertContains(response, "Unresolved")

    def test_a_resolved_escalation_is_still_visible_to_the_vc(self):
        """Asserted from the VC's side as well as the HOD's: the two read the
        same `escalated_at` invariant through different code paths."""
        self.escalated.status = Complaint.Status.RESOLVED
        self.escalated.save()
        self.client.force_login(self.vc)
        response = self.client.get(reverse("vc:complaints"))
        self.assertContains(response, "Marks never uploaded")
        self.assertEqual(
            self.client.get(reverse("vc:dashboard")).context["unresolved_count"], 0
        )

    def test_detail_shows_the_escalation_note(self):
        self.client.force_login(self.vc)
        response = self.client.get(
            reverse("vc:complaint_detail", args=[self.escalated.pk])
        )
        self.assertContains(response, "Department cannot resolve this.")

    def test_the_hod_console_is_not_the_vcs(self):
        self.client.force_login(self.vc)
        for name in ("hod:dashboard", "hod:complaints"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 403)
                self.assertTemplateUsed(response, "errors/wrong_account.html")

    def test_other_roles_are_kept_out_of_the_vc_console(self):
        for user in (self.hod, self.student):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("vc:complaints"))
                self.assertEqual(response.status_code, 403)
                self.assertTemplateUsed(response, "errors/wrong_account.html")

    def test_signed_out_visitors_are_sent_to_login(self):
        response = self.client.get(reverse("vc:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response["Location"])


class EscalationTests(TestCase):
    """Only the HOD escalates, and escalating twice doesn't rewrite history."""

    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.other_hod = User.objects.create_user(
            "hod2", password="x", role=User.Role.HOD
        )
        self.student = User.objects.create_user(
            "stu1", password="x", role=User.Role.STUDENT
        )
        self.complaint = Complaint.objects.create(
            student=self.student, subject="Attendance not counted", body="Scanned twice."
        )
        self.url = reverse("hod:escalate_complaint", args=[self.complaint.pk])

    def test_hod_escalates_with_a_note(self):
        self.client.force_login(self.hod)
        response = self.client.post(self.url, {"escalation_note": "Needs the VC."})
        self.assertRedirects(
            response, reverse("hod:complaint_detail", args=[self.complaint.pk])
        )
        self.complaint.refresh_from_db()
        self.assertTrue(self.complaint.is_escalated)
        self.assertEqual(self.complaint.escalated_by, self.hod)
        self.assertEqual(self.complaint.escalation_note, "Needs the VC.")

    def test_re_escalating_only_updates_the_note(self):
        self.client.force_login(self.hod)
        self.client.post(self.url, {"escalation_note": "First take."})
        self.complaint.refresh_from_db()
        first_time = self.complaint.escalated_at

        self.client.force_login(self.other_hod)
        self.client.post(self.url, {"escalation_note": "More detail."})
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.escalated_at, first_time)
        self.assertEqual(self.complaint.escalated_by, self.hod)
        self.assertEqual(self.complaint.escalation_note, "More detail.")

    def test_the_note_is_optional(self):
        self.client.force_login(self.hod)
        self.client.post(self.url, {"escalation_note": ""})
        self.complaint.refresh_from_db()
        self.assertTrue(self.complaint.is_escalated)

    def test_a_student_cannot_escalate_their_own_complaint(self):
        self.client.force_login(self.student)
        response = self.client.post(self.url, {"escalation_note": "please"})
        self.assertEqual(response.status_code, 403)
        self.complaint.refresh_from_db()
        self.assertFalse(self.complaint.is_escalated)

    def test_escalation_is_post_only(self):
        self.client.force_login(self.hod)
        self.assertEqual(self.client.get(self.url).status_code, 405)
