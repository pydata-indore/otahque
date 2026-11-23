"""Tests that cover the whole project."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase


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
