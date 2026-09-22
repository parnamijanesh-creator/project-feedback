"""Automated tests for FeedbackCard model and anonymity guarantees (Issue #6)."""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase

from apps.cycles.admin import FeedbackCardAdmin
from apps.cycles.models import FeedbackCard, FeedbackCycle
from apps.projects.models import Project

User = get_user_model()


class FeedbackCardAnonymityTests(TestCase):
    """Test suite ensuring strict database-level anonymity and model constraints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="sarah_engineer",
            email="sarah@example.com",
            password="Password123!",
        )
        self.project = Project.objects.create(
            name="Alpha Team",
            created_by=self.user,
        )
        self.cycle = FeedbackCycle.objects.create(
            project=self.project,
            facilitator=self.user,
        )

    def test_feedback_card_fields_and_defaults(self):
        """Verify model fields, default is_anonymous=False, and relationships."""
        card = FeedbackCard.objects.create(
            cycle=self.cycle,
            user=self.user,
            category=FeedbackCard.Category.START,
            text="Start daily async standups",
        )
        self.assertEqual(card.cycle, self.cycle)
        self.assertEqual(card.user, self.user)
        self.assertEqual(card.category, FeedbackCard.Category.START)
        self.assertFalse(card.is_anonymous)
        self.assertIsNotNone(card.created_at)

    def test_anonymous_card_clears_user_to_none(self):
        """When is_anonymous=True, user is cleared to None before commit."""
        card = FeedbackCard(
            cycle=self.cycle,
            user=self.user,
            category=FeedbackCard.Category.STOP,
            text="Stop having meetings without clear agendas",
            is_anonymous=True,
        )
        card.save()

        card.refresh_from_db()
        self.assertIsNone(card.user)
        self.assertTrue(card.is_anonymous)

    def test_database_table_confirms_null_user_id_for_anonymous_card(self):
        """Direct inspection of database table row verifies user_id IS NULL."""
        card = FeedbackCard.objects.create(
            cycle=self.cycle,
            user=self.user,
            category=FeedbackCard.Category.CONTINUE,
            text="Continue thorough code reviews",
            is_anonymous=True,
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, is_anonymous FROM cycles_feedbackcard WHERE id = %s;",
                [card.id],
            )
            row = cursor.fetchone()
            db_user_id, db_is_anonymous = row[0], row[1]
            self.assertIsNone(db_user_id)
            self.assertTrue(db_is_anonymous)

    def test_reverse_query_excludes_anonymous_cards(self):
        """user.cards.all() returns only non-anonymous cards, zero anonymous cards."""
        # Non-anonymous card
        named_card = FeedbackCard.objects.create(
            cycle=self.cycle,
            user=self.user,
            category=FeedbackCard.Category.START,
            text="Start pairing on tough issues",
            is_anonymous=False,
        )
        # Anonymous card (passed with self.user)
        anon_card = FeedbackCard.objects.create(
            cycle=self.cycle,
            user=self.user,
            category=FeedbackCard.Category.STOP,
            text="Stop late releases on Fridays",
            is_anonymous=True,
        )

        user_cards = self.user.cards.all()
        self.assertEqual(user_cards.count(), 1)
        self.assertIn(named_card, user_cards)
        self.assertNotIn(anon_card, user_cards)

    def test_non_anonymous_card_preserves_user(self):
        """When is_anonymous=False, user relationship is preserved and accessible."""
        card = FeedbackCard.objects.create(
            cycle=self.cycle,
            user=self.user,
            category=FeedbackCard.Category.CONTINUE,
            text="Continue the lunch and learn sessions",
            is_anonymous=False,
        )
        card.refresh_from_db()
        self.assertEqual(card.user, self.user)
        self.assertEqual(card.user.username, "sarah_engineer")

    def test_blank_or_whitespace_text_rejected(self):
        """Saving card with blank or whitespace-only text raises ValidationError."""
        card_empty = FeedbackCard(
            cycle=self.cycle,
            user=self.user,
            category=FeedbackCard.Category.START,
            text="",
        )
        with self.assertRaises(ValidationError):
            card_empty.save()

        card_whitespace = FeedbackCard(
            cycle=self.cycle,
            user=self.user,
            category=FeedbackCard.Category.STOP,
            text="    \n\t   ",
        )
        with self.assertRaises(ValidationError):
            card_whitespace.save()

    def test_invalid_category_rejected(self):
        """Saving card with invalid category choice raises ValidationError."""
        card_invalid = FeedbackCard(
            cycle=self.cycle,
            user=self.user,
            category="INVALID_CATEGORY",
            text="Valid text but invalid category",
        )
        with self.assertRaises(ValidationError):
            card_invalid.save()

    def test_admin_displays_anonymous_for_author(self):
        """FeedbackCardAdmin displays 'Anonymous' for anonymous cards and username for non-anonymous."""
        admin_instance = FeedbackCardAdmin(FeedbackCard, admin.site)

        anon_card = FeedbackCard.objects.create(
            cycle=self.cycle,
            user=self.user,
            category=FeedbackCard.Category.START,
            text="Anonymous feedback test",
            is_anonymous=True,
        )
        self.assertEqual(admin_instance.author_display(anon_card), "Anonymous")

        named_card = FeedbackCard.objects.create(
            cycle=self.cycle,
            user=self.user,
            category=FeedbackCard.Category.STOP,
            text="Named feedback test",
            is_anonymous=False,
        )
        self.assertEqual(admin_instance.author_display(named_card), "sarah_engineer")
