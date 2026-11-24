"""Tests that cover the whole project."""
import os
import subprocess
import sys
from io import StringIO

from django.conf import settings
from django.contrib import admin
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class MigrationTests(TestCase):
    """Every model change has a migration."""

    def test_every_model_change_has_a_migration(self):
        output = StringIO()
        try:
            call_command(
                'makemigrations', '--check', '--dry-run',
                stdout=output,
            )
        except SystemExit:
            self.fail(
                'Missing migrations:\n' + output.getvalue()
            )


class AdminUrlTests(SimpleTestCase):
    """The admin's address comes from DJANGO_ADMIN_URL."""

    def test_admin_lives_at_admin_url(self):
        self.assertEqual(reverse('admin:index'),
                         '/' + settings.ADMIN_URL)
        self.assertEqual(admin.site.site_header,
                         'Otahque administration')

    def test_a_badly_formed_path_stops_the_project(self):
        for value in ('admin', '/admin/', 'events/',
                      'private/<slug:name>/'):
            with self.subTest(value=value):
                env = dict(os.environ, DJANGO_ADMIN_URL=value)
                done = subprocess.run(
                    [sys.executable, 'manage.py', 'check'],
                    cwd=settings.BASE_DIR, env=env,
                    capture_output=True, text=True,
                )
                self.assertNotEqual(done.returncode, 0)
                self.assertIn(
                    'DJANGO_ADMIN_URL must end with / and not '
                    'start with it', done.stderr,
                )
