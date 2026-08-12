from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.complaints.models import Complaint


class StatusTransitionTests(TestCase):
    """The four statuses and the escalation stamp have to stay in step.

    `escalated_at` is what the VC console filters on, so every path that says
    "escalated" must set it, and no path may clear it.
    """

    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.student = User.objects.create_user(
            "stu1", password="x", role=User.Role.STUDENT
        )
        self.complaint = Complaint.objects.create(
            student=self.student, subject="Marks missing", body="Two months."
        )
        self.detail_url = reverse("hod:complaint_detail", args=[self.complaint.pk])
        self.client.force_login(self.hod)

    def test_a_new_complaint_starts_unreviewed(self):
        self.assertEqual(self.complaint.status, Complaint.Status.UNREVIEWED)

    def test_the_review_dropdown_offers_all_four_statuses(self):
        response = self.client.get(self.detail_url)
        choices = response.context["form"].fields["status"].choices
        self.assertEqual(
            [value for value, _ in choices],
            ["unreviewed", "reviewed", "escalated", "resolved"],
        )

    def test_choosing_escalated_in_the_review_form_puts_it_on_the_vcs_desk(self):
        """Status alone is not enough — the VC filters on `escalated_at`."""
        self.client.post(
            self.detail_url, {"status": "escalated", "hod_response": "Above me."}
        )
        self.complaint.refresh_from_db()
        self.assertIsNotNone(self.complaint.escalated_at)
        self.assertEqual(self.complaint.escalated_by, self.hod)
        self.assertIn(
            self.complaint,
            Complaint.objects.filter(escalated_at__isnull=False),
        )

    def test_resolving_an_escalated_complaint_leaves_it_with_the_vc(self):
        self.client.post(
            self.detail_url, {"status": "escalated", "hod_response": ""}
        )
        self.complaint.refresh_from_db()
        escalated_at = self.complaint.escalated_at

        self.client.post(
            self.detail_url, {"status": "resolved", "hod_response": "Sorted."}
        )
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Complaint.Status.RESOLVED)
        self.assertEqual(self.complaint.escalated_at, escalated_at)

    def test_the_escalate_button_does_not_reopen_a_resolved_complaint(self):
        """Attaching a late note must not drag a closed case back into the queue."""
        self.complaint.status = Complaint.Status.RESOLVED
        self.complaint.save()
        self.client.post(
            reverse("hod:escalate_complaint", args=[self.complaint.pk]),
            {"escalation_note": "For the record."},
        )
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Complaint.Status.RESOLVED)
        self.assertIsNotNone(self.complaint.escalated_at)

    def test_a_resolved_complaint_offers_no_escalate_button_on_the_list(self):
        self.complaint.status = Complaint.Status.RESOLVED
        self.complaint.save()
        response = self.client.get(reverse("hod:complaints"))
        self.assertNotContains(response, "escalate/")


class ComplaintFilterTests(TestCase):
    """The filter tiles describe the whole inbox, not the filtered page."""

    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.student = User.objects.create_user(
            "stu1", password="x", role=User.Role.STUDENT
        )
        for status, _ in Complaint.Status.choices:
            Complaint.objects.create(
                student=self.student,
                subject=f"About {status}",
                body="...",
                status=status,
            )
        self.client.force_login(self.hod)

    def tiles(self, response):
        return {tile["label"]: tile["count"] for tile in response.context["status_tiles"]}

    def test_the_tiles_count_the_whole_inbox_not_the_filtered_page(self):
        response = self.client.get(reverse("hod:complaints"), {"status": "reviewed"})
        self.assertEqual(len(response.context["complaints"]), 1)
        self.assertEqual(
            self.tiles(response),
            {"Total": 4, "Unreviewed": 1, "Reviewed": 1, "Escalated": 1, "Resolved": 1},
        )

    def test_the_selected_tile_is_the_only_active_one(self):
        response = self.client.get(reverse("hod:complaints"), {"status": "resolved"})
        active = [t["label"] for t in response.context["status_tiles"] if t["is_active"]]
        self.assertEqual(active, ["Resolved"])

    def test_every_status_gets_a_tile_even_at_zero(self):
        Complaint.objects.all().delete()
        response = self.client.get(reverse("hod:complaints"))
        self.assertEqual(
            self.tiles(response),
            {"Total": 0, "Unreviewed": 0, "Reviewed": 0, "Escalated": 0, "Resolved": 0},
        )

    def test_an_unknown_status_falls_back_to_showing_everything(self):
        """A stale bookmark should land on a usable page, not an empty one."""
        response = self.client.get(reverse("hod:complaints"), {"status": "submitted"})
        self.assertEqual(len(response.context["complaints"]), 4)
        active = [t["label"] for t in response.context["status_tiles"] if t["is_active"]]
        self.assertEqual(active, ["Total"])


class ListEscalateActionTests(TestCase):
    """Escalating from the list returns to the list, and `next` is not trusted."""

    def setUp(self):
        self.hod = User.objects.create_user("hod1", password="x", role=User.Role.HOD)
        self.student = User.objects.create_user(
            "stu1", password="x", role=User.Role.STUDENT
        )
        self.complaint = Complaint.objects.create(
            student=self.student, subject="Marks missing", body="Two months."
        )
        self.url = reverse("hod:escalate_complaint", args=[self.complaint.pk])
        self.client.force_login(self.hod)

    def test_the_list_offers_an_escalate_button(self):
        response = self.client.get(reverse("hod:complaints"))
        self.assertContains(response, self.url)

    def test_escalating_from_the_list_returns_to_the_filtered_list(self):
        target = f"{reverse('hod:complaints')}?status=unreviewed"
        response = self.client.post(self.url, {"escalation_note": "", "next": target})
        self.assertRedirects(response, target)
        self.complaint.refresh_from_db()
        self.assertTrue(self.complaint.is_escalated)
        self.assertEqual(self.complaint.status, Complaint.Status.ESCALATED)

    def test_a_next_pointing_off_site_is_ignored(self):
        response = self.client.post(
            self.url, {"escalation_note": "", "next": "https://evil.example/"}
        )
        self.assertRedirects(
            response, reverse("hod:complaint_detail", args=[self.complaint.pk])
        )

    def test_an_escalated_row_shows_its_state_instead_of_a_button(self):
        self.client.post(self.url, {"escalation_note": ""})
        response = self.client.get(reverse("hod:complaints"))
        self.assertContains(response, "With VC")
        self.assertNotContains(response, self.url)
