"""Tests for the registrations app."""
from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase

from events.models import Event
from .models import Registration

User = get_user_model()


class RegistrationTests(TestCase):
    """A registration links a member to an event."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            title='Python meetup',
            starts_at=datetime(2026, 11, 19, 18, 30,
                               tzinfo=UTC),
            ends_at=datetime(2026, 11, 19, 20, 30,
                             tzinfo=UTC),
            timezone='Europe/London',
            location='Leeds Central Library',
            capacity=40,
        )
        cls.member = User.objects.create_user(
            'sai@example.org', display_name='Sai'
        )
        cls.registration = Registration.objects.create(
            event=cls.event, member=cls.member
        )

    def test_registration_links_event_and_member(self):
        registration = self.registration
        self.assertEqual(registration.event, self.event)
        self.assertEqual(registration.member, self.member)
        self.assertEqual(
            registration.status, Registration.Status.ACTIVE
        )
        self.assertQuerySetEqual(
            self.event.registrations.all(), [registration]
        )
        self.assertQuerySetEqual(
            self.member.registrations.all(), [registration]
        )

    def test_event_with_registration_is_kept(self):
        with self.assertRaises(ProtectedError):
            self.event.delete()
        self.assertTrue(
            Event.objects.filter(pk=self.event.pk).exists()
        )

    def test_member_with_registration_is_kept(self):
        with self.assertRaises(ProtectedError):
            self.member.delete()
        self.assertTrue(
            User.objects.filter(pk=self.member.pk).exists()
        )
