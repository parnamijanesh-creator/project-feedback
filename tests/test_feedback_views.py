"""Automated tests for Feedback Submission Interface with HTMX (Issue #7)."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.cycles.models import FeedbackCard, FeedbackCycle
from apps.projects.models import Project, ProjectMember

User = get_user_model()


class FeedbackSubmissionViewTests(TestCase):
    """Test suite covering HTMX submissions, user card isolation, edit, delete, and closed states."""

    def setUp(self):
        self.client_a = Client()
        self.client_b = Client()
        self.outsider_client = Client()

        self.user_a = User.objects.create_user(
            username="alice_dev", email="alice@example.com", password="Password123!"
        )
        self.user_b = User.objects.create_user(
            username="bob_dev", email="bob@example.com", password="Password123!"
        )
        self.outsider = User.objects.create_user(
            username="outsider_user", email="outsider@example.com", password="Password123!"
        )

        self.project = Project.objects.create(name="Core App", created_by=self.user_a)
        ProjectMember.objects.create(
            project=self.project, user=self.user_a, role=ProjectMember.Role.FACILITATOR
        )
        ProjectMember.objects.create(
            project=self.project, user=self.user_b, role=ProjectMember.Role.MEMBER
        )

        self.cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.user_a,
            status=FeedbackCycle.Status.COLLECTING,
        )

        self.client_a.login(username="alice_dev", password="Password123!")
        self.client_b.login(username="bob_dev", password="Password123!")
        self.outsider_client.login(username="outsider_user", password="Password123!")

        self.submit_url = reverse(
            "feedback_submit", kwargs={"slug": self.project.slug, "pk": self.cycle.pk}
        )

    def test_submit_view_renders_three_columns_and_forms(self):
        """View renders Start, Stop, and Continue columns with textarea and Anonymous checkbox."""
        response = self.client_a.get(self.submit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Start")
        self.assertContains(response, "Stop")
        self.assertContains(response, "Continue")
        self.assertContains(response, 'name="is_anonymous"')
        self.assertContains(response, 'name="text"')

    def test_non_member_cannot_access_or_submit_feedback(self):
        """Non-members receiving HTTP 403 Forbidden for both GET and POST."""
        get_resp = self.outsider_client.get(self.submit_url)
        self.assertEqual(get_resp.status_code, 403)

        post_resp = self.outsider_client.post(
            self.submit_url,
            data={"category": "START", "text": "Unwelcome suggestion"},
        )
        self.assertEqual(post_resp.status_code, 403)

    def test_htmx_card_creation_named(self):
        """Submitting named card via HTMX POST returns card partial and persists author."""
        post_data = {
            "category": "START",
            "text": "Automate deployment pipeline",
            "is_anonymous": "false",
        }
        response = self.client_b.post(
            self.submit_url,
            data=post_data,
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Automate deployment pipeline")
        self.assertContains(response, "bob_dev")

        card = FeedbackCard.objects.filter(text="Automate deployment pipeline").first()
        self.assertIsNotNone(card)
        self.assertEqual(card.user, self.user_b)
        self.assertFalse(card.is_anonymous)

    def test_htmx_card_creation_anonymous_with_session_tracking(self):
        """Submitting anonymous card clears user_id in DB, but stores ID in session for author."""
        post_data = {
            "category": "STOP",
            "text": "Stop interrupting deep work hours",
            "is_anonymous": "on",
        }
        response = self.client_b.post(
            self.submit_url,
            data=post_data,
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stop interrupting deep work hours")
        self.assertContains(response, "Anonymous")

        card = FeedbackCard.objects.filter(text="Stop interrupting deep work hours").first()
        self.assertIsNotNone(card)
        self.assertIsNone(card.user)
        self.assertTrue(card.is_anonymous)

        # Check session contains anonymous card id
        anon_ids = self.client_b.session.get("anonymous_card_ids", [])
        self.assertIn(card.id, anon_ids)

        # In submit view, author user_b can see their anonymous card
        get_response = self.client_b.get(self.submit_url)
        self.assertContains(get_response, "Stop interrupting deep work hours")

    def test_strict_isolation_between_teammates_during_collecting(self):
        """User A cannot see cards submitted by User B, whether named or anonymous."""
        # User B submits a named card and an anonymous card
        FeedbackCard.objects.create(
            cycle=self.cycle,
            user=self.user_b,
            category=FeedbackCard.Category.START,
            text="User B secret proposal",
            is_anonymous=False,
        )
        FeedbackCard.objects.create(
            cycle=self.cycle,
            user=None,
            category=FeedbackCard.Category.CONTINUE,
            text="User B anonymous note",
            is_anonymous=True,
        )

        # User A views submission board
        response_a = self.client_a.get(self.submit_url)
        self.assertEqual(response_a.status_code, 200)
        self.assertNotContains(response_a, "User B secret proposal")
        self.assertNotContains(response_a, "User B anonymous note")

    def test_empty_or_whitespace_card_returns_error(self):
        """Empty card submission returns 422 with validation error."""
        response = self.client_a.post(
            self.submit_url,
            data={"category": "START", "text": "   "},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Card text cannot be blank.", status_code=422)
        self.assertEqual(FeedbackCard.objects.count(), 0)

    def test_card_edit_flow(self):
        """Author can retrieve edit form and update card text via HTMX."""
        card = FeedbackCard.objects.create(
            cycle=self.cycle,
            user=self.user_b,
            category=FeedbackCard.Category.CONTINUE,
            text="Initial text for continue",
            is_anonymous=False,
        )
        edit_url = reverse(
            "card_edit",
            kwargs={"slug": self.project.slug, "cycle_pk": self.cycle.pk, "card_pk": card.pk},
        )

        # Other user cannot edit
        forbidden_resp = self.client_a.get(edit_url)
        self.assertEqual(forbidden_resp.status_code, 403)

        # Author retrieves edit form
        get_form_resp = self.client_b.get(edit_url)
        self.assertEqual(get_form_resp.status_code, 200)
        self.assertContains(get_form_resp, "Initial text for continue")

        # Author updates card text
        update_resp = self.client_b.post(
            edit_url,
            data={"text": "Updated text for continue card"},
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertContains(update_resp, "Updated text for continue card")
        card.refresh_from_db()
        self.assertEqual(card.text, "Updated text for continue card")

    def test_card_delete_flow(self):
        """Author can delete their card; non-owner cannot delete."""
        card = FeedbackCard.objects.create(
            cycle=self.cycle,
            user=self.user_b,
            category=FeedbackCard.Category.STOP,
            text="Card to be removed",
            is_anonymous=False,
        )
        delete_url = reverse(
            "card_delete",
            kwargs={"slug": self.project.slug, "cycle_pk": self.cycle.pk, "card_pk": card.pk},
        )

        # User A cannot delete User B's card
        forbidden_resp = self.client_a.post(delete_url)
        self.assertEqual(forbidden_resp.status_code, 403)
        self.assertTrue(FeedbackCard.objects.filter(pk=card.pk).exists())

        # User B deletes their card
        delete_resp = self.client_b.post(delete_url)
        self.assertEqual(delete_resp.status_code, 200)
        self.assertFalse(FeedbackCard.objects.filter(pk=card.pk).exists())

    def test_closed_cycle_rejects_submissions_and_disables_forms(self):
        """When cycle is RETROSPECTIVE or COMPLETED, submissions return 403 and forms are disabled."""
        self.cycle.status = FeedbackCycle.Status.RETROSPECTIVE
        self.cycle.save()

        get_resp = self.client_b.get(self.submit_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, "Feedback collection is closed for this cycle.")
        # Form submission disabled
        self.assertNotContains(get_resp, 'hx-post="')

        post_resp = self.client_b.post(
            self.submit_url,
            data={"category": "START", "text": "Too late card"},
        )
        self.assertEqual(post_resp.status_code, 403)
