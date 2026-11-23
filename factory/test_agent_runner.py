"""Tests for how the agent runner applies the model's edits.

Run from the repository root with:
python -m unittest factory/test_agent_runner.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# The runner reads these at import; the tests never use them.
os.environ.setdefault('ISSUE', '0')
os.environ.setdefault('REPO', 'example/example')
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_runner  # noqa: E402

# The layout project_layout() reads from this project's settings.
LAYOUT = {'apps': ['accounts', 'events'],
          'templates': ['templates'],
          'settings': 'config/settings.py',
          'urls': 'config/urls.py'}


def use_layout(test, layout=LAYOUT, **steps):
    """Give the runner a layout and steps for one test."""
    for name in ('APPS', 'TEMPLATE_DIRS', 'SETTINGS', 'URLS',
                 'PROJECT', 'ALLOWED', 'TESTS', 'PACKAGE',
                 'MIGRATIONS_INIT', 'MIGRATION', 'STEPS',
                 'MAIN_CLEAN'):
        test.addCleanup(setattr, agent_runner, name,
                        getattr(agent_runner, name))
    agent_runner.set_layout(layout)
    agent_runner.STEPS = {'startapp': [],
                          'makemigrations': None,
                          'settings': [], **steps}


def block(path, search, replace):
    """Return one edit block in the format the model uses."""
    return (f'FILE: {path}\n<<<<<<< SEARCH\n{search}'
            f'=======\n{replace}>>>>>>> REPLACE\n')


class ApplyEditsTests(unittest.TestCase):
    """apply_edits() writes every block or none of them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old_root = agent_runner.ROOT
        agent_runner.ROOT = self.root
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        self.old_root)

    def apply(self, text):
        return agent_runner.apply_edits(text, lambda path: True)

    def test_empty_search_creates_a_new_file(self):
        changed = self.apply(block('app/apps.py', '', 'A\n'))
        self.assertEqual(changed, ['app/apps.py'])
        text = (self.root / 'app/apps.py').read_text()
        self.assertEqual(text, 'A\n')

    def test_search_on_a_missing_file_is_refused(self):
        with self.assertRaisesRegex(ValueError,
                                    'does not exist yet'):
            self.apply(block('app/apps.py', 'A\n', 'B\n'))
        self.assertFalse((self.root / 'app').exists())

    def test_empty_search_on_an_existing_file_is_refused(self):
        (self.root / 'notes.md').write_text('old\n')
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.apply(block('notes.md', '', 'new\n'))
        text = (self.root / 'notes.md').read_text()
        self.assertEqual(text, 'old\n')

    def test_empty_search_fills_an_empty_file(self):
        (self.root / 'app').mkdir()
        (self.root / 'app/__init__.py').write_text('')
        changed = self.apply(block('app/__init__.py', '', 'x\n'))
        self.assertEqual(changed, ['app/__init__.py'])
        text = (self.root / 'app/__init__.py').read_text()
        self.assertEqual(text, 'x\n')

    def test_a_bad_block_writes_nothing(self):
        (self.root / 'a.py').write_text('x = 1\n')
        reply = (block('new.py', '', 'y = 2\n')
                 + block('a.py', 'x = 1\n', 'x = 3\n')
                 + block('missing.py', 'z\n', 'w\n'))
        with self.assertRaises(ValueError):
            self.apply(reply)
        self.assertFalse((self.root / 'new.py').exists())
        text = (self.root / 'a.py').read_text()
        self.assertEqual(text, 'x = 1\n')

    def test_every_bad_block_is_named(self):
        reply = (block('one.py', 'a\n', 'b\n')
                 + block('ok.py', '', 'x\n')
                 + block('two.py', 'c\n', 'd\n'))
        with self.assertRaises(ValueError) as caught:
            self.apply(reply)
        message = str(caught.exception)
        self.assertIn('one.py does not exist', message)
        self.assertIn('two.py does not exist', message)
        self.assertFalse((self.root / 'ok.py').exists())

    def test_later_blocks_see_earlier_ones(self):
        reply = (block('new.py', '', 'x = 1\n')
                 + block('new.py', 'x = 1\n', 'x = 2\n'))
        self.assertEqual(self.apply(reply), ['new.py'])
        text = (self.root / 'new.py').read_text()
        self.assertEqual(text, 'x = 2\n')

    def test_a_refused_path_writes_nothing(self):
        reply = (block('ok.py', '', 'x\n')
                 + block('no.py', '', 'y\n'))
        with self.assertRaisesRegex(ValueError, 'may not'):
            agent_runner.apply_edits(
                reply, lambda path: path == 'ok.py')
        self.assertFalse((self.root / 'ok.py').exists())



class TestsStepPathTests(unittest.TestCase):
    """The tests step may touch tests and new package files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old_root = agent_runner.ROOT
        agent_runner.ROOT = self.root
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        self.old_root)
        use_layout(self)
        (self.root / 'events').mkdir()
        (self.root / 'events/__init__.py').write_text('')
        for args in (['init', '-q'],
                     ['add', 'events/__init__.py'],
                     ['-c', 'user.name=t', '-c',
                      'user.email=t@example.com',
                      'commit', '-q', '-m', 'start']):
            agent_runner.run(['git', *args])

    def allowed(self, path):
        return agent_runner.tests_step_path(path)

    def test_tests_are_allowed(self):
        self.assertTrue(self.allowed('accounts/tests.py'))

    def test_a_new_package_file_is_allowed(self):
        self.assertTrue(self.allowed('accounts/__init__.py'))

    def test_a_package_file_made_this_run_can_be_fixed(self):
        new = self.root / 'accounts/__init__.py'
        new.parent.mkdir()
        new.write_text('"""Accounts."""\n')
        self.assertTrue(self.allowed('accounts/__init__.py'))

    def test_an_existing_app_package_is_refused(self):
        self.assertFalse(self.allowed('events/__init__.py'))

    def test_other_app_files_are_refused(self):
        self.assertFalse(self.allowed('accounts/models.py'))



class TicketDocsTests(unittest.TestCase):
    """The agent sees the existing docs the ticket names."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        agent_runner.ROOT)
        agent_runner.ROOT = Path(self.tmp.name)
        design = agent_runner.ROOT / 'docs/design'
        design.mkdir(parents=True)
        (design / 'erd.md').write_text('# ERD\n')

    def test_existing_named_docs_are_shown_once(self):
        body = ('Update `docs/design/erd.md`, add '
                '`docs/adr/ADR-002-user-model.md`, and check '
                '`docs/design/erd.md` again.')
        docs = agent_runner.ticket_docs({'body': body})
        self.assertEqual(docs, ['docs/design/erd.md'])

    def test_a_ticket_without_docs_shows_none(self):
        docs = agent_runner.ticket_docs({'body': 'No docs.'})
        self.assertEqual(docs, [])

    def test_a_path_outside_docs_is_not_shown(self):
        (agent_runner.ROOT / 'notes.md').write_text('private\n')
        docs = agent_runner.ticket_docs(
            {'body': 'See `docs/../notes.md`.'})
        self.assertEqual(docs, [])

    def test_a_doc_the_agent_cannot_edit_is_not_shown(self):
        adr = agent_runner.ROOT / 'docs/adr'
        adr.mkdir()
        (adr / 'ADR-002.v2.md').write_text('# ADR\n')
        docs = agent_runner.ticket_docs(
            {'body': 'Edit `docs/adr/ADR-002.v2.md`.'})
        self.assertEqual(docs, [])

    def test_another_spelling_of_a_doc_is_not_shown(self):
        body = ('`docs/design/erd.md`, `docs//design/erd.md`, '
                '`docs/design/./erd.md`')
        docs = agent_runner.ticket_docs({'body': body})
        self.assertEqual(docs, ['docs/design/erd.md'])

    def test_a_long_doc_shows_its_first_whole_lines(self):
        limit = agent_runner.DOC_LIMIT
        line = 'A line of text.\n'
        count = limit // len(line) + 50
        big = agent_runner.ROOT / 'docs/design/big.md'
        big.write_text('# Start\n' + line * count + '# End\n')
        text = agent_runner.doc_text(['docs/design/big.md',
                                      'docs/design/erd.md'])
        shown = text.split('--- docs/design/erd.md ---')[0]
        self.assertIn('# Start\n', shown)
        self.assertNotIn('# End', shown)
        self.assertIn('cut here', shown)
        self.assertLess(len(shown), limit + 200)
        # The cut falls between lines, so SEARCH stays whole.
        self.assertIn(line + '(cut here', shown)
        self.assertIn('# ERD', text)

    def test_one_very_long_line_is_not_shown_in_part(self):
        limit = agent_runner.DOC_LIMIT
        big = agent_runner.ROOT / 'docs/design/big.md'
        big.write_text('y' * (limit + 10) + '\n')
        text = agent_runner.doc_text(['docs/design/big.md'])
        shown = text.split('---')[-1].split('(')[0]
        self.assertNotIn('y', shown)
        self.assertIn('only the first 0 are shown', text)

    def test_an_edit_in_the_shown_part_still_applies(self):
        limit = agent_runner.DOC_LIMIT
        big = agent_runner.ROOT / 'docs/design/big.md'
        big.write_text('# Start\n' + 'x\n' * limit)
        agent_runner.apply_edits(
            'FILE: docs/design/big.md\n<<<<<<< SEARCH\n# Start\n'
            '=======\n# Begin\n>>>>>>> REPLACE\n',
            lambda path: True)
        self.assertTrue(big.read_text().startswith('# Begin\n'))


class StartappNoteTests(unittest.TestCase):
    """The criteria check is told which files startapp made."""

    def setUp(self):
        self.addCleanup(setattr, agent_runner, 'STARTAPP_FILES',
                        agent_runner.STARTAPP_FILES)

    def test_no_note_without_startapp(self):
        agent_runner.STARTAPP_FILES = []
        self.assertEqual(agent_runner.startapp_note(), '')

    def test_the_note_names_each_file(self):
        agent_runner.STARTAPP_FILES = ['accounts/views.py',
                                       'accounts/admin.py']
        note = agent_runner.startapp_note()
        self.assertIn('accounts/views.py', note)
        self.assertIn('accounts/admin.py', note)
        self.assertIn('not the model', note)


class RunChecksTests(unittest.TestCase):
    """run_checks() never runs Django on refused changes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = []
        fake = {
            'ROOT': self.root,
            'manage': lambda *args: (
                self.calls.append(args) or (0, 'OK')),
        }
        for name, value in fake.items():
            self.addCleanup(setattr, agent_runner, name,
                            getattr(agent_runner, name))
            setattr(agent_runner, name, value)
        use_layout(self)

    def check(self, *paths):
        self.addCleanup(setattr, agent_runner, 'changed_paths',
                        agent_runner.changed_paths)
        agent_runner.changed_paths = lambda: list(paths)
        return agent_runner.run_checks()

    def test_code_in_migrations_init_stops_before_django(self):
        init = self.root / 'accounts/migrations/__init__.py'
        init.parent.mkdir(parents=True)
        init.write_text('import os\n')
        passed, report = self.check(
            'accounts/migrations/__init__.py')
        self.assertFalse(passed)
        self.assertIn('Must stay empty', report)
        self.assertEqual(self.calls, [])

    def test_a_refused_path_stops_before_django(self):
        passed, report = self.check('factory/agent_runner.py')
        self.assertFalse(passed)
        self.assertIn('Not allowed', report)
        self.assertEqual(self.calls, [])

    def test_allowed_changes_run_django(self):
        (self.root / 'README.md').write_text('Notes\n')
        passed, report = self.check('README.md')
        self.assertTrue(passed)
        self.assertIn(('check',), self.calls)
        self.assertIn(('test',), self.calls)


class LayoutTests(unittest.TestCase):
    """The agent's paths come from the settings' layout."""

    def setUp(self):
        use_layout(self)

    def test_app_code_and_templates_are_open(self):
        for path in ('events/models.py', 'accounts/managers.py',
                     'events/templates/events/list.html',
                     'templates/base.html', 'config/urls.py',
                     'config/settings.py', 'docs/adr/ADR-3.md'):
            self.assertTrue(agent_runner.may_edit(path), path)

    def test_project_tests_count_as_tests(self):
        self.assertTrue(
            agent_runner.TESTS.fullmatch('config/tests.py'))
        self.assertTrue(agent_runner.may_edit('config/tests.py'))

    def test_other_project_files_are_closed(self):
        for path in ('config/wsgi.py', 'config/asgi.py',
                     'manage.py', 'pyproject.toml'):
            self.assertFalse(agent_runner.may_edit(path), path)

    def test_migrations_are_closed_to_the_agent(self):
        path = 'events/migrations/0001_initial.py'
        self.assertFalse(agent_runner.may_edit(path))
        self.assertTrue(agent_runner.MIGRATION.fullmatch(path))

    def test_denied_places_stay_closed(self):
        for path in ('factory/agent_runner.py', '.env',
                     '.github/workflows/agent.yml',
                     'static/otahque/site.css'):
            self.assertFalse(agent_runner.may_edit(path), path)

    def test_an_unsafe_layout_entry_is_dropped(self):
        use_layout(self, {
            'apps': ['events', '.venv/lib/admin', 'factory',
                     None, '../other'],
            'templates': ['static', ''],
            'settings': 'config/settings.py', 'urls': None})
        self.assertEqual(agent_runner.APPS, ['events'])
        self.assertEqual(agent_runner.TEMPLATE_DIRS, [])
        self.assertFalse(agent_runner.may_edit('factory/x.py'))
        self.assertFalse(agent_runner.may_edit('static/a.html'))

    def test_an_app_not_in_the_settings_is_closed(self):
        path = 'payments/views.py'
        self.assertFalse(agent_runner.may_edit(path))
        agent_runner.add_app('payments')
        self.assertTrue(agent_runner.may_edit(path))

    def test_the_layout_line_is_found_in_noisy_output(self):
        out = ('warning\nLAYOUT={"apps": ["events"], '
               '"settings": "config/settings.py"}\n')
        layout = agent_runner.read_layout(out)
        self.assertEqual(layout['apps'], ['events'])

    def test_output_without_a_layout_stops_the_run(self):
        with self.assertRaises(agent_runner.Blocked):
            agent_runner.read_layout('Traceback ...\n')


class RunnerStepsTests(unittest.TestCase):
    """The ticket's Runner section says what the runner does."""

    def steps(self, section):
        return agent_runner.runner_steps(
            '## Intended result\n\nText.\n\n## Runner\n\n'
            + section + '\n## Not in this ticket\n\n- x\n')

    def test_no_section_asks_for_nothing(self):
        steps = agent_runner.runner_steps('## Intended result\n')
        self.assertEqual(steps, {'startapp': [],
                                 'makemigrations': None,
                                 'settings': []})

    def test_every_step_is_read(self):
        steps = self.steps(
            '- `startapp accounts`\n- `makemigrations`\n'
            '- settings: INSTALLED_APPS, AUTH_USER_MODEL\n')
        self.assertEqual(steps['startapp'], ['accounts'])
        self.assertEqual(steps['makemigrations'], [])
        self.assertEqual(steps['settings'],
                         ['INSTALLED_APPS', 'AUTH_USER_MODEL'])

    def test_makemigrations_takes_apps_and_a_name(self):
        steps = self.steps(
            '- makemigrations events --name event_slug\n')
        self.assertEqual(steps['makemigrations'],
                         ['events', '--name', 'event_slug'])

    def test_windows_line_endings_are_read(self):
        steps = agent_runner.runner_steps(
            '## Runner\r\n\r\n- makemigrations\r\n')
        self.assertEqual(steps['makemigrations'], [])

    def test_an_unknown_line_stops_the_run(self):
        for line in ('- migrate', '- makemigrations; rm -rf .',
                     '- startapp ../x', '- settings: debug'):
            with self.assertRaisesRegex(agent_runner.Blocked,
                                        'cannot use'):
                self.steps(line + '\n')

    def test_a_protected_setting_stops_the_run(self):
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'SECRET_KEY'):
            self.steps('- settings: MIDDLEWARE, SECRET_KEY\n')


SETTINGS = '''"""Settings for the test project."""

from decouple import config

try:
    SECRET_KEY = config('DJANGO_SECRET_KEY')
except KeyError:
    raise

DEBUG = config('DJANGO_DEBUG', default='') == 'True'

INSTALLED_APPS = [
    'django.contrib.auth',
    'events.apps.EventsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
]
'''
SECURITY = ("    'django.middleware.security."
            "SecurityMiddleware',\n")


class SettingsGuardTests(unittest.TestCase):
    """Only the settings a ticket names may change."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        agent_runner.ROOT)
        agent_runner.ROOT = Path(self.tmp.name)
        use_layout(self, settings=['INSTALLED_APPS',
                                   'AUTH_USER_MODEL'])
        self.path = agent_runner.ROOT / 'config/settings.py'
        self.path.parent.mkdir()
        self.path.write_text(SETTINGS)
        for args in (['init', '-q'], ['add', '.'],
                     ['-c', 'user.name=t', '-c',
                      'user.email=t@example.com',
                      'commit', '-q', '-m', 'start']):
            agent_runner.run(['git', *args])

    def change(self, old, new):
        text = self.path.read_text()
        self.assertIn(old, text)
        self.path.write_text(text.replace(old, new, 1))
        return agent_runner.settings_problems()

    def test_no_change_has_no_problems(self):
        self.assertEqual(agent_runner.settings_problems(), [])

    def test_an_app_entry_in_a_named_setting_passes(self):
        self.assertEqual(self.change(
            "    'events.apps.EventsConfig',\n",
            "    'accounts.apps.AccountsConfig',\n"
            "    'events.apps.EventsConfig',\n"), [])

    def test_a_new_named_setting_with_its_comment_passes(self):
        self.assertEqual(self.change(
            ']\n\nMIDDLEWARE', "]\n\n# See ADR-002.\n"
            "AUTH_USER_MODEL = 'accounts.User'\n\nMIDDLEWARE"),
            [])

    def test_a_setting_the_ticket_does_not_name_fails(self):
        problems = self.change(
            SECURITY, SECURITY + "    'x.Middleware',\n")
        self.assertEqual(len(problems), 1)
        self.assertIn('x.Middleware', problems[0])

    def test_a_named_setting_opens_it(self):
        agent_runner.STEPS['settings'].append('MIDDLEWARE')
        self.assertEqual(self.change(
            SECURITY, SECURITY + "    'x.Middleware',\n"), [])

    def test_a_protected_setting_fails_even_if_named(self):
        agent_runner.STEPS['settings'].append('DEBUG')
        problems = self.change(
            "DEBUG = config('DJANGO_DEBUG', default='') "
            "== 'True'", 'DEBUG = True')
        self.assertEqual(len(problems), 2)

    def test_the_secret_key_block_is_closed(self):
        problems = self.change(
            "    SECRET_KEY = config('DJANGO_SECRET_KEY')",
            "    SECRET_KEY = 'x'")
        self.assertTrue(problems)

    def test_a_new_secret_key_line_fails(self):
        problems = self.change(
            '\nDEBUG =', "\nSECRET_KEY = 'x'\nDEBUG =")
        self.assertTrue(problems)

    def test_an_import_fails(self):
        problems = self.change(
            'from decouple import config\n',
            'from decouple import config\nimport os\n')
        self.assertEqual(len(problems), 1)

    def test_a_blank_line_inside_a_docstring_fails(self):
        problems = self.change(
            '"""Settings for the test project."""',
            '"""Settings for the test project.\n\nMore."""')
        self.assertTrue(problems)

    def test_a_blank_line_between_statements_passes(self):
        self.assertEqual(self.change(
            ']\n\nMIDDLEWARE', ']\n\n\nMIDDLEWARE'), [])

    def test_a_comment_not_above_a_named_setting_fails(self):
        problems = self.change(
            '\nDEBUG =', '\n# A note.\n\nDEBUG =')
        self.assertEqual(len(problems), 1)

    def test_two_statements_on_one_line_fail(self):
        problems = self.change(
            "]\n\nMIDDLEWARE", "]\n\nDEBUG = True; "
            "AUTH_USER_MODEL = 'accounts.User'\n\nMIDDLEWARE")
        self.assertTrue(problems)

    def test_a_walrus_in_a_named_value_fails(self):
        problems = self.change(
            "]\n\nMIDDLEWARE", "]\n\nAUTH_USER_MODEL = "
            "(DEBUG := True) and 'accounts.User'\n\nMIDDLEWARE")
        self.assertTrue(problems)

    def test_a_call_in_a_named_value_fails(self):
        problems = self.change(
            "]\n\nMIDDLEWARE", "]\n\nAUTH_USER_MODEL = "
            "globals().update(DEBUG=True) or 'a.User'\n\n"
            "MIDDLEWARE")
        self.assertTrue(problems)

    def test_a_file_that_does_not_parse_fails(self):
        problems = self.change('INSTALLED_APPS = [',
                               'INSTALLED_APPS = [[')
        self.assertIn('does not parse', problems[0])


class MigrationStepTests(unittest.TestCase):
    """Only the runner writes migrations, kept as written."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.made = []
        self.pending = 0
        fake = {
            'ROOT': self.root,
            'manage': self.manage,
            'run_migrations': lambda: [
                p for p in self.made
                if (self.root / p).exists()],
            'GENERATED': [],
        }
        for name, value in fake.items():
            self.addCleanup(setattr, agent_runner, name,
                            getattr(agent_runner, name))
            setattr(agent_runner, name, value)
        use_layout(self, makemigrations=[])
        (self.root / 'events/migrations').mkdir(parents=True)

    def manage(self, *args):
        """Stand in for manage.py; makemigrations writes."""
        if args == ('makemigrations',):
            number = len(self.made) + 1
            name = f'events/migrations/{number:04d}_x.py'
            # Django's lines run past 65 characters.
            (self.root / name).write_text('x = ' + '1' * 90)
            self.made.append(name)
            return 0, 'Migrations for events'
        if args[:2] == ('makemigrations', '--check'):
            return self.pending, 'No changes detected'
        return 0, 'OK'

    def check(self, *paths):
        self.addCleanup(setattr, agent_runner, 'changed_paths',
                        agent_runner.changed_paths)
        agent_runner.changed_paths = lambda: list(paths)
        return agent_runner.run_checks()

    def test_generated_migrations_pass_the_checks(self):
        passed, report = self.check()
        self.assertTrue(passed, report)
        made = list(agent_runner.GENERATED)
        self.assertEqual(made, ['events/migrations/0001_x.py'])
        # On the next attempt the generated file is a change.
        passed, report = self.check(*made)
        self.assertTrue(passed, report)
        self.assertNotIn('Lines over', report)

    def test_each_attempt_replaces_the_last_ones(self):
        self.check()
        first = agent_runner.GENERATED[0]
        self.check(first)
        self.assertFalse((self.root / first).exists())
        self.assertEqual(len(agent_runner.GENERATED), 1)

    def test_a_migration_from_the_agent_is_refused(self):
        passed, report = self.check(
            'events/migrations/0009_mine.py')
        self.assertFalse(passed)
        self.assertIn('Not allowed', report)
        self.assertEqual(self.made, [])

    def test_pending_changes_fail_when_migrating(self):
        self.pending = 1
        passed, report = self.check()
        self.assertFalse(passed)
        self.assertIn('has no migration', report)

    def test_pending_changes_are_recorded_on_main(self):
        self.pending = 1
        agent_runner.STEPS['makemigrations'] = None
        passed, report = self.check()
        self.assertTrue(passed)
        self.assertIn('recorded only', report)

    def test_pending_changes_fail_once_main_is_clean(self):
        self.pending = 1
        agent_runner.STEPS['makemigrations'] = None
        agent_runner.MAIN_CLEAN = True
        passed, report = self.check()
        self.assertFalse(passed)

    def test_the_baseline_never_generates(self):
        self.pending = 1
        agent_runner.MAIN_CLEAN = True
        self.addCleanup(setattr, agent_runner, 'changed_paths',
                        agent_runner.changed_paths)
        agent_runner.changed_paths = list
        passed, report = agent_runner.run_checks(baseline=True)
        self.assertTrue(passed, report)
        self.assertEqual(self.made, [])

    def started(self, files):
        self.addCleanup(setattr, agent_runner, 'run',
                        agent_runner.run)
        agent_runner.run = lambda args: (0, '\n'.join(files))
        return agent_runner.migrations_started()

    def test_no_migration_file_means_not_started(self):
        # Chapters 15 to 17: models, on purpose no migration.
        self.assertFalse(self.started(['events/models.py']))

    def test_clean_migrations_mean_started(self):
        self.assertTrue(self.started(
            ['events/migrations/0001_initial.py']))

    def test_pending_changes_on_a_migrated_main_stop(self):
        self.pending = 1
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'main has migrations'):
            self.started(['events/migrations/0001_initial.py'])

    def test_a_missing_migration_counts_as_red(self):
        out = ('Found 29 test(s).\nValueError: Dependency on '
               'app with no migrations: accounts\n')
        self.assertTrue(agent_runner.fails_for_new_code(out))
        agent_runner.STEPS['makemigrations'] = None
        self.addCleanup(setattr, agent_runner,
                        'added_test_names',
                        agent_runner.added_test_names)
        agent_runner.added_test_names = set
        self.assertFalse(agent_runner.fails_for_new_code(out))


class MigrationNoteTests(unittest.TestCase):
    """The model is told the script writes the migrations."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        agent_runner.ROOT)
        agent_runner.ROOT = Path(self.tmp.name)
        self.addCleanup(setattr, agent_runner, 'GENERATED',
                        agent_runner.GENERATED)

    def refusal(self):
        reply = ('FILE: events/migrations/0001_initial.py\n'
                 '<<<<<<< SEARCH\n=======\nx = 1\n'
                 '>>>>>>> REPLACE\n')
        with self.assertRaises(ValueError) as caught:
            agent_runner.apply_edits(reply,
                                     agent_runner.may_edit)
        return str(caught.exception)

    def test_no_note_without_makemigrations(self):
        use_layout(self)
        self.assertEqual(agent_runner.migrations_note(), '')
        self.assertIn('makes no migration', self.refusal())

    def test_the_note_and_refusal_name_makemigrations(self):
        use_layout(self, makemigrations=[])
        self.assertIn('makemigrations itself',
                      agent_runner.migrations_note())
        self.assertIn('send no block', self.refusal())

    def test_triage_hears_which_files_are_generated(self):
        use_layout(self, makemigrations=[])
        agent_runner.GENERATED = []
        self.assertEqual(agent_runner.generated_note(), '')
        agent_runner.GENERATED = [
            'events/migrations/0001_initial.py']
        note = agent_runner.generated_note()
        self.assertIn('events/migrations/0001_initial.py', note)
        self.assertIn('rule 1', note)


class SearchFeedbackTests(unittest.TestCase):
    """A failed SEARCH says why, and the retry shows the file."""

    OLD = ('"""Tests for the accounts app."""\n\n'
           'from django.test import SimpleTestCase\n\n'
           'x = 1\nx = 1\n')

    def problem(self, search):
        return agent_runner.search_problem(
            'accounts/tests.py', self.OLD, search,
            self.OLD.count(search))

    def test_the_first_missing_line_is_named(self):
        # The book's listing has no module docstring here.
        message = self.problem(
            'from django.test import TestCase\n')
        self.assertIn("'from django.test import TestCase'",
                      message)
        self.assertIn('not from the reference', message)

    def test_a_repeated_match_asks_for_context(self):
        self.assertIn('matches 2 times', self.problem('x = 1\n'))

    def test_lines_in_another_order_are_explained(self):
        message = self.problem(
            'from django.test import SimpleTestCase\n'
            '"""Tests for the accounts app."""\n')
        self.assertIn('not in this order', message)

    def test_a_line_wanted_twice_but_there_once_is_named(self):
        old = '"""Doc."""\nx = 1\n'
        message = agent_runner.search_problem(
            'a.py', old, 'x = 1\nx = 1\n', 0)
        self.assertIn('2 times', message)

    def test_a_missing_final_line_break_is_named(self):
        old = '"""Doc."""\nx = 1'
        message = agent_runner.search_problem(
            'a.py', old, 'x = 1\n', 0)
        self.assertIn('line break', message)

    def setup_root(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        agent_runner.ROOT)
        self.addCleanup(setattr, agent_runner, 'changed_paths',
                        agent_runner.changed_paths)
        agent_runner.ROOT = Path(self.tmp.name)
        agent_runner.changed_paths = lambda: []
        use_layout(self)
        (agent_runner.ROOT / 'accounts').mkdir()
        (agent_runner.ROOT / 'accounts/tests.py').write_text(
            self.OLD)
        (agent_runner.ROOT / '.env').write_text('SECRET=1\n')

    def test_a_symlink_to_env_is_never_shown(self):
        self.setup_root()
        link = agent_runner.ROOT / 'accounts/tests_link.py'
        try:
            link.symlink_to(agent_runner.ROOT / '.env')
        except OSError:
            self.skipTest('symlinks need extra rights here')
        reply = block('accounts/tests_link.py', 'x\n', 'y\n')
        self.assertEqual(agent_runner.retry_files(
            reply, agent_runner.tests_step_path), [])

    def test_a_folder_link_out_of_the_repo_is_never_shown(self):
        # A junction (Windows) or symlinked folder: the file is
        # not itself a link, but it resolves outside the repo.
        self.setup_root()
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        (Path(outside.name) / 'tests.py').write_text('SECRET\n')
        link = agent_runner.ROOT / 'accounts/tests_dir'
        if os.name == 'nt':
            made = agent_runner.run(
                ['cmd', '/c', 'mklink', '/J', str(link),
                 outside.name])[0] == 0
        else:
            link.symlink_to(outside.name)
            made = True
        if not made:
            self.skipTest('could not make a folder link')
        self.addCleanup(lambda: os.path.isdir(link)
                        and os.rmdir(link))
        reply = block('accounts/tests_dir/tests.py', 'x\n', 'y\n')
        self.assertTrue(agent_runner.tests_step_path(
            'accounts/tests_dir/tests.py'))
        self.assertEqual(agent_runner.retry_files(
            reply, agent_runner.tests_step_path), [])

    def test_a_block_missing_a_marker_still_shows_its_file(self):
        self.setup_root()
        reply = ('FILE: accounts/tests.py\n<<<<<<< SEARCH\nx\n'
                 '>>>>>>> REPLACE\n')
        self.assertEqual(agent_runner.retry_files(
            reply, agent_runner.tests_step_path),
            ['accounts/tests.py'])

    def test_a_long_doc_keeps_its_limit_on_a_retry(self):
        self.setup_root()
        (agent_runner.ROOT / 'docs').mkdir()
        big = agent_runner.ROOT / 'docs/big.md'
        big.write_text('A line.\n' * agent_runner.DOC_LIMIT)
        text = agent_runner.retry_text(['docs/big.md'])
        self.assertIn('cut here', text)
        self.assertLess(len(text), agent_runner.DOC_LIMIT + 300)

    def test_the_retry_shows_the_files_the_reply_named(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        agent_runner.ROOT)
        self.addCleanup(setattr, agent_runner, 'changed_paths',
                        agent_runner.changed_paths)
        agent_runner.ROOT = Path(self.tmp.name)
        agent_runner.changed_paths = lambda: []
        use_layout(self)
        (agent_runner.ROOT / 'accounts').mkdir()
        (agent_runner.ROOT / 'accounts/tests.py').write_text(
            self.OLD)
        (agent_runner.ROOT / '.env').write_text('SECRET=1\n')
        reply = (block('accounts/tests.py', 'nope\n', 'y\n')
                 + block('.env', 'SECRET=1\n', 'x\n')
                 + block('docs/../.env', 'S\n', 'x\n')
                 + block('config/missing.py', '', 'x\n'))
        paths = agent_runner.retry_files(
            reply, agent_runner.tests_step_path)
        self.assertEqual(paths, ['accounts/tests.py'])


class NamedTestsTests(unittest.TestCase):
    """The tests step writes every test the ticket names."""

    BODY = ('`test_create_user_saves_a_member` and '
            '`test_every_model_change_has_a_migration`.')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        agent_runner.ROOT)
        agent_runner.ROOT = Path(self.tmp.name)
        use_layout(self)
        for folder in ('accounts', 'config'):
            (agent_runner.ROOT / folder).mkdir()
        agent_runner.run(['git', 'init', '-q'])

    def write(self, path, *names, head='class T(TestCase):\n'):
        text = ''.join(f'    def {n}(self):\n        pass\n'
                       for n in names)
        (agent_runner.ROOT / path).write_text(head + text)

    def missing(self):
        return agent_runner.missing_named_tests(self.BODY)

    def test_a_ticket_without_names_asks_for_nothing(self):
        self.assertEqual(
            agent_runner.missing_named_tests('Three tests.'), [])

    def test_a_forgotten_test_file_is_named(self):
        # Chapter 18, run 2: only config/tests.py was written.
        self.write('config/tests.py',
                   'test_every_model_change_has_a_migration')
        self.assertEqual(self.missing(),
                         ['test_create_user_saves_a_member'])

    def test_all_named_tests_written_pass(self):
        self.write('config/tests.py',
                   'test_every_model_change_has_a_migration')
        self.write('accounts/tests.py',
                   'test_create_user_saves_a_member')
        self.assertEqual(self.missing(), [])

    def test_an_async_test_counts(self):
        (agent_runner.ROOT / 'accounts/tests.py').write_text(
            'class T(TestCase):\n'
            '    async def test_create_user_saves_a_member('
            'self):\n        pass\n')
        self.write('config/tests.py',
                   'test_every_model_change_has_a_migration')
        self.assertEqual(self.missing(), [])

    def test_a_helper_class_does_not_count(self):
        self.write('config/tests.py',
                   'test_every_model_change_has_a_migration')
        self.write('accounts/tests.py',
                   'test_create_user_saves_a_member',
                   head='class Helper:\n')
        self.assertEqual(self.missing(),
                         ['test_create_user_saves_a_member'])

    def test_a_name_in_a_string_does_not_count(self):
        self.write('config/tests.py',
                   'test_every_model_change_has_a_migration')
        (agent_runner.ROOT / 'accounts/tests.py').write_text(
            'NOTE = """\n'
            '    def test_create_user_saves_a_member(self):\n'
            '"""\n')
        self.assertEqual(self.missing(),
                         ['test_create_user_saves_a_member'])

    def test_a_subclass_of_a_local_test_case_counts(self):
        self.write('config/tests.py',
                   'test_every_model_change_has_a_migration')
        self.write('accounts/tests.py',
                   'test_create_user_saves_a_member',
                   head='class Base(django.test.TestCase):\n'
                        '    pass\n\n\nclass T(Base):\n')
        self.assertEqual(self.missing(), [])

    def test_a_name_outside_a_test_file_does_not_count(self):
        self.write('accounts/models.py',
                   'test_create_user_saves_a_member')
        self.assertIn('test_create_user_saves_a_member',
                      self.missing())


class KeepCommittedTests(unittest.TestCase):
    """Review rounds keep a migration whose time alone is new."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        agent_runner.ROOT)
        agent_runner.ROOT = Path(self.tmp.name)
        use_layout(self)
        self.path = 'events/migrations/0001_initial.py'
        target = agent_runner.ROOT / self.path
        target.parent.mkdir(parents=True)
        target.write_text('# Generated on Monday\nx = 1\n')
        for args in (['init', '-q'], ['add', '.'],
                     ['-c', 'user.name=t', '-c',
                      'user.email=t@example.com',
                      'commit', '-q', '-m', 'start']):
            agent_runner.run(['git', *args])

    def regenerate(self, text):
        target = agent_runner.ROOT / self.path
        target.write_text(text)
        agent_runner.keep_committed(self.path)
        return target.read_text()

    def test_a_new_time_only_keeps_the_committed_file(self):
        self.assertEqual(
            self.regenerate('# Generated on Tuesday\nx = 1\n'),
            '# Generated on Monday\nx = 1\n')

    def test_a_real_change_is_kept(self):
        self.assertEqual(
            self.regenerate('# Generated on Tuesday\nx = 2\n'),
            '# Generated on Tuesday\nx = 2\n')

    def test_committed_migrations_count_as_this_runs(self):
        agent_runner.BASE = 'HEAD'
        self.addCleanup(setattr, agent_runner, 'BASE', 'HEAD')
        code, first = agent_runner.run(
            ['git', 'rev-parse', 'HEAD'])
        new = 'events/migrations/0002_more.py'
        (agent_runner.ROOT / new).write_text('y = 1\n')
        self.assertEqual(agent_runner.run_migrations(), [new])
        agent_runner.run(['git', 'add', '.'])
        agent_runner.run(['git', '-c', 'user.name=t', '-c',
                          'user.email=t@example.com', 'commit',
                          '-q', '-m', 'branch'])
        # Against main's commit the committed file still counts,
        # and main's own 0001 does not.
        agent_runner.BASE = first.strip()
        self.assertEqual(agent_runner.run_migrations(), [new])


if __name__ == '__main__':
    unittest.main()
