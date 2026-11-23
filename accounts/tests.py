"""Tests for the accounts app."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .models import User


class UserModelTests(SimpleTestCase):
    """The User model's rules, checked without a database."""

    def test_user_model_is_accounts_user(self):
        self.assertIs(get_user_model(), User)
        self.assertEqual(User.USERNAME_FIELD, 'email')

    def test_password_is_stored_as_a_hash(self):
        user = User(email='sai@example.org',
                    display_name='Sai')
        user.set_password('correct horse')
        self.assertNotEqual(user.password, 'correct horse')
        self.assertTrue(
            user.password.startswith('pbkdf2_sha256$')
        )
        self.assertTrue(user.check_password('correct horse'))
        self.assertFalse(user.check_password('wrong horse'))

    def test_email_and_display_name_are_required(self):
        user = User()
        user.set_password('correct horse')
        with self.assertRaises(ValidationError) as caught:
            user.full_clean(validate_unique=False)
        self.assertEqual(
            sorted(caught.exception.message_dict),
            ['display_name', 'email'],
        )


class UserManagerTests(SimpleTestCase):
    """The manager's refusals, checked before any save."""

    def test_create_user_requires_an_email(self):
        with self.assertRaisesMessage(
            ValueError, 'An email address is required.'
        ):
            User.objects.create_user(
                email='', password='correct horse',
                display_name='Sai',
            )

    def test_superuser_flags_must_be_true(self):
        with self.assertRaisesMessage(
            ValueError, 'needs is_superuser=True.'
        ):
            User.objects.create_superuser(
                email='sam@example.org',
                password='correct horse',
                display_name='Sam',
                is_superuser=False,
            )
