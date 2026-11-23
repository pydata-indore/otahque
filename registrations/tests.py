"""Tests for the registrations app."""
from datetime import UTC, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

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

    def test_second_active_registration_is_refused(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Registration.objects.create(
                    event=self.event, member=self.member
                )
        self.assertEqual(
            self.event.registrations.count(), 1
        )

    def test_member_can_register_after_cancelling(self):
        self.registration.status = 'cancelled'
        self.registration.cancelled_at = timezone.now()
        self.registration.save()
        Registration.objects.create(
            event=self.event, member=self.member
        )
        active = self.event.registrations.filter(
            status=Registration.Status.ACTIVE
        )
        self.assertEqual(active.count(), 1)

    def test_cancelled_at_matches_status(self):
        rows = Registration.objects.filter(
            pk=self.registration.pk
        )
        for status, cancelled_at in [
            ('cancelled', None),
            ('active', timezone.now()),
        ]:
            with self.subTest(status=status):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        rows.update(
                            status=status,
                            cancelled_at=cancelled_at,
                        )

    def test_cancelled_never_before_registered(self):
        rows = Registration.objects.filter(
            pk=self.registration.pk
        )
        day = timedelta(days=1)
        before = self.registration.registered_at - day
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                rows.update(status='cancelled',
                            cancelled_at=before)

    def test_full_clean_explains_a_duplicate(self):
        duplicate = Registration(
            event=self.event, member=self.member
        )
        with self.assertRaises(ValidationError) as caught:
            duplicate.full_clean()
        self.assertEqual(
            caught.exception.messages,
            ['This member already has a place at '
             'this event.'],
        )
