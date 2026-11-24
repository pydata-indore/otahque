"""Tests for how the agent runner applies the model's edits.

Run from the repository root with:
python -m unittest factory/test_agent_runner.py
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The runner reads these at import; the tests never use them.
os.environ.setdefault('ISSUE', '0')
os.environ.setdefault('REPO', 'example/example')
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_runner  # noqa: E402
import confirm_gate  # noqa: E402

# The real lookup, kept before any test replaces it.
HEAD_COMMIT = agent_runner.head_commit

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
    """apply_edits() writes each file's blocks or none."""

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

    def test_a_bad_file_keeps_the_good_ones(self):
        (self.root / 'a.py').write_text('x = 1\n')
        reply = (block('new.py', '', 'y = 2\n')
                 + block('a.py', 'x = 1\n', 'x = 3\n')
                 + block('missing.py', 'z\n', 'w\n'))
        partial = agent_runner.PartialEdits
        with self.assertRaises(partial) as caught:
            self.apply(reply)
        self.assertEqual(sorted(caught.exception.changed),
                         ['a.py', 'new.py'])
        self.assertIn('missing.py', str(caught.exception))
        self.assertEqual((self.root / 'a.py').read_text(),
                         'x = 3\n')
        self.assertFalse((self.root / 'missing.py').exists())

    def test_nothing_written_is_not_partial(self):
        reply = block('missing.py', 'z\n', 'w\n')
        with self.assertRaises(ValueError) as caught:
            self.apply(reply)
        self.assertNotIsInstance(caught.exception,
                                 agent_runner.PartialEdits)
        self.assertNotIn('Applied anyway', str(caught.exception))

    def test_a_symlink_is_never_written_through(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        secret = Path(outside.name) / 'runner.py'
        secret.write_text('safe = True\n')
        try:
            (self.root / 'tests.py').symlink_to(secret)
        except OSError:
            self.skipTest('this system cannot make symlinks')
        reply = ('FILE: tests.py\n<<<<<<< APPEND\n'
                 'safe = False\n>>>>>>> APPEND\n')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.apply(reply)
        self.assertEqual(secret.read_text(), 'safe = True\n')

    def test_a_linked_folder_is_never_written_through(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        try:
            (self.root / 'app').symlink_to(
                outside.name, target_is_directory=True)
        except OSError:
            self.skipTest('this system cannot make symlinks')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.apply(block('app/new.py', '', 'x = 1\n'))
        self.assertFalse(
            (Path(outside.name) / 'new.py').exists())

    def test_every_bad_block_in_a_file_is_named(self):
        (self.root / 'a.py').write_text('x = 1\ny = 1\n')
        reply = (block('a.py', 'nope\n', 'z\n')
                 + block('a.py', 'x = 1\n', 'x = 2\n')
                 + block('a.py', 'also nope\n', 'w\n'))
        with self.assertRaises(ValueError) as caught:
            self.apply(reply)
        message = str(caught.exception)
        self.assertIn('nope', message)
        self.assertIn('also nope', message)
        self.assertEqual((self.root / 'a.py').read_text(),
                         'x = 1\ny = 1\n')

    def test_a_resent_append_is_not_added_twice(self):
        (self.root / 'tests.py').write_text(
            'class A:\n    pass\n')
        reply = ('FILE: tests.py\n<<<<<<< APPEND\n'
                 'class B:\n    pass\n>>>>>>> APPEND\n')
        self.apply(reply)
        self.apply(reply)
        text = (self.root / 'tests.py').read_text()
        self.assertEqual(text.count('class B:'), 1)

    def test_one_bad_block_keeps_its_file_unchanged(self):
        (self.root / 'a.py').write_text('x = 1\ny = 1\n')
        reply = (block('a.py', 'x = 1\n', 'x = 2\n')
                 + block('a.py', 'nope\n', 'z\n'))
        with self.assertRaises(ValueError):
            self.apply(reply)
        self.assertEqual((self.root / 'a.py').read_text(),
                         'x = 1\ny = 1\n')

    def test_append_adds_to_the_end(self):
        (self.root / 'tests.py').write_text(
            'class A:\n    pass\n')
        reply = ('FILE: tests.py\n<<<<<<< APPEND\n'
                 'class B:\n    pass\n>>>>>>> APPEND\n')
        self.assertEqual(self.apply(reply), ['tests.py'])
        self.assertEqual((self.root / 'tests.py').read_text(),
                         'class A:\n    pass\n\n\n'
                         'class B:\n    pass\n')

    def test_append_creates_a_missing_file(self):
        reply = ('FILE: notes.md\n<<<<<<< APPEND\n'
                 '# Notes\n>>>>>>> APPEND\n')
        self.assertEqual(self.apply(reply), ['notes.md'])
        self.assertEqual((self.root / 'notes.md').read_text(),
                         '# Notes\n')

    def test_append_and_search_mix_in_one_reply(self):
        (self.root / 't.py').write_text(
            'import os\n\n\nclass A:\n    pass\n')
        reply = (block('t.py', 'import os\n',
                       'import os\nimport sys\n')
                 + 'FILE: t.py\n<<<<<<< APPEND\nclass B:\n'
                 '    pass\n>>>>>>> APPEND\n')
        self.apply(reply)
        text = (self.root / 't.py').read_text()
        self.assertTrue(text.startswith('import os\nimport sys'))
        self.assertTrue(text.endswith('class B:\n    pass\n'))

    def test_every_bad_block_is_named(self):
        reply = (block('one.py', 'a\n', 'b\n')
                 + block('ok.py', '', 'x\n')
                 + block('two.py', 'c\n', 'd\n'))
        with self.assertRaises(ValueError) as caught:
            self.apply(reply)
        message = str(caught.exception)
        self.assertIn('one.py does not exist', message)
        self.assertIn('two.py does not exist', message)
        self.assertTrue((self.root / 'ok.py').exists())

    def test_later_blocks_see_earlier_ones(self):
        reply = (block('new.py', '', 'x = 1\n')
                 + block('new.py', 'x = 1\n', 'x = 2\n'))
        self.assertEqual(self.apply(reply), ['new.py'])
        text = (self.root / 'new.py').read_text()
        self.assertEqual(text, 'x = 2\n')

    def test_a_refused_path_is_never_written(self):
        reply = (block('ok.py', '', 'x\n')
                 + block('no.py', '', 'y\n'))
        with self.assertRaisesRegex(ValueError, 'may not'):
            agent_runner.apply_edits(
                reply, lambda path: path == 'ok.py')
        self.assertFalse((self.root / 'no.py').exists())
        self.assertTrue((self.root / 'ok.py').exists())



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

    def test_an_extra_blank_line_is_not_a_missing_break(self):
        message = agent_runner.search_problem(
            'a.py', 'x = 1\n', 'x = 1\n\n', 0)
        self.assertNotIn('line break', message)
        self.assertIn('blank lines differ', message)

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
        # A symlink is unlinked; a Windows junction is removed
        # like an empty folder. Neither touches the target.
        self.addCleanup(lambda: link.unlink()
                        if link.is_symlink() else os.rmdir(link))
        reply = block('accounts/tests_dir/tests.py',
                      'x\n', 'y\n')
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


def badge(severity):
    """Return a Qodo severity badge line."""
    return (f'<img src="https://img.shields.io/badge/{severity}-'
            '634FD1?style=flat-square" alt="x">\n')


def finding(n, title, kind='🐞 Bug', path='events/views.py',
            line=14):
    """Return one finding as Qodo's review comment lists it."""
    return (f'<details>\n<summary>  {n}.  {title} <code>{kind}'
            f'</code></summary>\n><summary>Code</summary>\n'
            f'><code>[{path}[R{line}-{line + 1}]](https://x/'
            f'pull/1/files#diff-abc)</code>\n</details>\n')


def review_comment(*parts, resolved=''):
    """Return a review comment shaped like Qodo's."""
    return ('<h3>Code Review by Qodo</h3>\n<code>🐞 Bugs (2)'
            '</code>\n' + ''.join(parts)
            + ('<details><summary><strong>Resolved findings'
               '</strong></summary>\n' + resolved if resolved
               else '')
            + '<!-- https://github.com/o/r/commit/'
            + 'a' * 40 + ' -->\n')


class GateReadingTests(unittest.TestCase):
    """The gate reads each finding's severity and type."""

    def test_each_finding_takes_its_groups_severity(self):
        body = review_comment(
            badge('High'), finding(1, 'Gate passes wrongly'),
            badge('Medium'), finding(2, 'Wrong advice'),
            '<details><summary><ins><strong>View medium (1)'
            '</strong></ins></summary>\n',
            finding(3, 'No PR report', line=1348))
        found = agent_runner.read_findings(body)
        self.assertEqual(
            [(f['title'], f['severity']) for f in found],
            [('Gate passes wrongly', 'High'),
             ('Wrong advice', 'Medium'),
             ('No PR report', 'Medium')])
        self.assertEqual(found[2]['where'],
                         'events/views.py:1348')
        self.assertEqual(found[2]['path'], 'events/views.py')

    def test_rule_violations_and_requirement_gaps(self):
        body = review_comment(
            badge('Low'),
            finding(1, 'A long line', '📘 Rule violation'),
            badge('Medium'),
            finding(2, 'Missing test', '📎 Requirement gap'))
        found = agent_runner.read_findings(body)
        self.assertEqual(
            [(f['type'], f['severity']) for f in found],
            [('Rule violation', 'Low'),
             ('Requirement gap', 'Medium')])

    def test_a_finding_before_any_badge_is_unknown(self):
        body = review_comment(finding(1, 'Odd'), badge('Low'),
                              finding(2, 'Fine'))
        found = agent_runner.read_findings(body)
        self.assertEqual([f['severity'] for f in found],
                         ['?', 'Low'])

    def test_resolved_findings_are_not_open(self):
        body = review_comment(
            badge('Medium'), finding(1, 'Open one'),
            resolved=(badge('Medium')
                      + finding(2, '<s>Done</s> <code>✓ Resolved'
                                   '</code>')))
        found = agent_runner.read_findings(body)
        self.assertEqual([f['title'] for f in found],
                         ['Open one'])

    def test_a_number_in_a_resolved_title_is_not_open(self):
        body = review_comment(resolved=(
            badge('Medium')
            + finding(1, '<s>Handle (2) cases</s> <code>✓ '
                         'Resolved</code>')))
        body = body.replace('<code>🐞 Bugs (2)</code>', '')
        self.assertFalse(agent_runner.has_open_count(body))
        self.assertEqual(agent_runner.read_findings(body), [])

    def test_a_review_with_zero_findings_is_not_open(self):
        # PR 40's header: every category shows (0).
        body = ('<h3>Code Review by Qodo</h3>\n\n<code>🐞 Bugs '
                '(0)</code>  <code>📘 Rule violations (0)</code>'
                '  <code>📎 Requirement gaps (0)</code>\n')
        self.assertFalse(agent_runner.has_open_count(body))
        self.assertEqual(agent_runner.read_findings(body), [])

    def test_a_count_of_ten_is_open(self):
        body = '<code>🐞 Bugs (10)</code>'
        self.assertTrue(agent_runner.has_open_count(body))

    def test_the_category_count_shows_open_findings(self):
        body = review_comment(badge('High'), finding(1, 'Open'))
        self.assertTrue(agent_runner.has_open_count(body))

    def test_a_struck_title_outside_the_section_is_skipped(self):
        body = review_comment(badge('High'),
                              finding(1, '<s>Fixed</s>'))
        self.assertEqual(agent_runner.read_findings(body), [])

    def test_the_reviewed_commit_is_read_from_the_footer(self):
        body = review_comment(badge('Low'), finding(1, 'x'))
        self.assertEqual(agent_runner.reviewed_commit(body),
                         'a' * 40)
        self.assertIsNone(agent_runner.reviewed_commit('none'))

    def test_named_files_are_shown_but_never_dot_files(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        agent_runner.ROOT)
        agent_runner.ROOT = Path(self.tmp.name)
        use_layout(self)
        (agent_runner.ROOT / 'AGENTS.md').write_text('Rules\n')
        (agent_runner.ROOT / '.env').write_text('SECRET=1\n')
        text = agent_runner.finding_files([
            {'path': 'AGENTS.md'}, {'path': '.env'},
            {'path': 'missing.py'}, {'path': ''}])
        self.assertIn('--- AGENTS.md ---', text)
        self.assertNotIn('SECRET', text)


class GateLoopTests(unittest.TestCase):
    """The review loop ends only when the gate is met."""

    HEAD = 'b' * 40

    def setUp(self):
        self.posted, self.fixed = [], []
        self.reviewed = self.HEAD
        fake = {
            # The wait's own snapshot says nothing is open; the
            # loop must use the fresh read from review_state().
            'wait_for_review': lambda pr, since:
                (1, False, self.HEAD),
            'review_state': self.next_state,
            'head_commit': lambda pr=None: self.HEAD,
            'finding_files': lambda findings: '',
            'review_text': lambda pr, cid: 'review',
            'diff_from_main': lambda: 'diff',
            'comment': lambda kind, n, text:
                self.posted.append(text),
            'edit_loop': lambda *a: self.fixed.append(a[-1]),
            'commit': lambda message: 'c0ffee1',
            'push': lambda branch: None,
            'step_files': lambda issue: '',
            'log': lambda text: None,
            'REVIEW_ROUNDS': 2,
        }
        for name, value in fake.items():
            self.addCleanup(setattr, agent_runner, name,
                            getattr(agent_runner, name))
            setattr(agent_runner, name, value)
        self.addCleanup(setattr, agent_runner, 'ask_json',
                        agent_runner.ask_json)
        self.addCleanup(setattr, agent_runner, 'GENERATED',
                        agent_runner.GENERATED)
        agent_runner.GENERATED = []
        use_layout(self)

    def next_state(self, comment_id):
        """Stand in for review_state(): one fresh read."""
        found = self.findings.pop(0)
        return found, self.reviewed, bool(found)

    def run_loop(self, findings, verdicts):
        self.findings = findings
        replies = list(verdicts)
        agent_runner.ask_json = lambda messages: {
            'findings': replies.pop(0)}
        agent_runner.review(35, 'ch20', {'body': 'Ticket'}, [],
                            agent_runner.now())

    def finding(self, severity, kind='Bug', title='T'):
        return {'id': 1, 'title': title, 'severity': severity,
                'type': kind, 'where': 'a.py:1'}

    def test_only_low_findings_meet_the_gate(self):
        low = self.finding('Low', 'Rule violation', 'Long line')
        self.run_loop([[low]], [])
        self.assertEqual(self.fixed, [])
        self.assertIn("**Gate met on Qodo's comment.**",
                      self.posted[-1])
        self.assertIn('Long line (Rule violation',
                      self.posted[-1])

    def test_a_valid_medium_bug_is_fixed_then_rechecked(self):
        bug = self.finding('Medium', 'Bug', 'Wrong 404')
        self.run_loop([[bug], []],
                      [[{'n': 1, 'verdict': 'confirmed',
                         'reason': 'real'}]])
        self.assertEqual(self.fixed, ['Review fix 1'])
        self.assertIn("**Gate met on Qodo's comment.**",
                      self.posted[-1])
        self.assertIn('Wrong 404', self.posted[-1])

    def test_a_disputed_high_finding_is_not_done(self):
        high = self.finding('High')
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'Quality gate not met'):
            self.run_loop([[high]],
                          [[{'n': 1, 'verdict': 'disputed',
                             'reason': 'Chapter 21'}]])
        self.assertEqual(self.fixed, [])
        self.assertIn('a human decides', self.posted[-1])

    def test_a_finding_the_model_skips_is_fixed(self):
        bug = self.finding('High')
        self.run_loop([[bug], []], [[]])
        self.assertEqual(self.fixed, ['Review fix 1'])

    def test_findings_left_after_the_last_round_fail(self):
        bug = self.finding('Medium')
        yes = [{'n': 1, 'verdict': 'confirmed', 'reason': 'r'}]
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'fix rounds'):
            self.run_loop([[bug], [bug], [bug]], [yes, yes, yes])
        self.assertEqual(len(self.fixed), 2)

    def test_unknown_severity_counts_as_blocking(self):
        odd = self.finding('?')
        with self.assertRaises(agent_runner.Blocked):
            self.run_loop([[odd]],
                          [[{'n': 1, 'verdict': 'disputed',
                             'reason': 'r'}]])

    def test_a_finding_added_while_waiting_is_seen(self):
        # The wait saw nothing open; the fresh read has a High.
        with self.assertRaises(agent_runner.Blocked):
            self.run_loop([[self.finding('High')]],
                          [[{'n': 1, 'verdict': 'disputed',
                             'reason': 'r'}]])
        self.assertIn('a human decides', self.posted[-1])

    def test_an_unknown_pr_head_never_meets_the_gate(self):
        agent_runner.head_commit = lambda pr: None
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'does not cover'):
            self.run_loop([[]], [])
        self.assertNotIn('**Gate met.**', self.posted[-1])
        self.assertIn('PR head `unknown`', self.posted[-1])

    def test_a_review_of_an_older_commit_fails(self):
        self.reviewed = 'c' * 40
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'does not cover'):
            self.run_loop([[]], [])

    def test_a_failed_head_lookup_gives_no_head(self):
        def broken(*args, **kwargs):
            raise RuntimeError('gh pr: network')
        self.addCleanup(setattr, agent_runner, 'gh',
                        agent_runner.gh)
        self.addCleanup(setattr, agent_runner, 'head_commit',
                        agent_runner.head_commit)
        agent_runner.gh = broken
        agent_runner.head_commit = HEAD_COMMIT
        self.assertIsNone(agent_runner.head_commit(35))

    def test_a_stale_review_ends_with_a_pr_report(self):
        def stale(pr, since):
            raise agent_runner.StaleReview('a' * 40, self.HEAD)
        agent_runner.wait_for_review = stale
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'does not cover'):
            agent_runner.review(35, 'ch20', {'body': 'T'}, [],
                                agent_runner.now())
        self.assertIn('NOT the same commit', self.posted[-1])

    def test_a_disputed_migration_finding_is_not_fixed(self):
        agent_runner.GENERATED = [
            'events/migrations/0002_x.py']
        rule = self.finding('Medium', 'Rule violation',
                            'Long migration line')
        with self.assertRaises(agent_runner.Blocked):
            self.run_loop([[rule]],
                          [[{'n': 1, 'verdict': 'disputed',
                             'reason': 'rule 1 exempts it'}]])
        self.assertEqual(self.fixed, [])
        self.assertIn('Dispute (never confirm)',
                      agent_runner.generated_note())

    def test_a_stale_review_never_meets_the_gate(self):
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'head commit'):
            agent_runner.finish(35, [], [], True, '', 'a' * 40,
                                self.HEAD)
        self.assertIn('NOT the same commit', self.posted[-1])


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


class TokenTests(unittest.TestCase):
    """The run stops when its PR could not start the checks."""

    def test_missing_agent_token_stops_the_run(self):
        reason = agent_runner.token_problem('false')
        self.assertIn('AGENT_GH_TOKEN', reason)
        self.assertIn('checks', reason)

    def test_agent_token_set_or_unknown_is_fine(self):
        self.assertIsNone(agent_runner.token_problem('true'))
        # A run outside Actions does not say either way.
        self.assertIsNone(agent_runner.token_problem(''))


# Qodo's recorded runs on PR #44 (23 November 2026), newest
# first: the chapter commit got a full review, then the README
# rewrap on top of it was skipped twice.
CHAPTER = '0330f4e962f6649c66d112f3e2e899859d2221bd'
REWRAP = '711a77013274b828b4331d84ff1bc0c29f5b62a2'
PR44_RUNS = [
    {'run_id': 2118564, 'commit_sha': REWRAP,
     'started_at': '2026-11-23T18:10:15.591129Z',
     'status': 'completed', 'review_effort': 'skip',
     'review_complete': False},
    {'run_id': 2118531, 'commit_sha': REWRAP,
     'started_at': '2026-11-23T18:08:31.320570Z',
     'status': 'completed', 'review_effort': 'skip',
     'review_complete': False},
    {'run_id': 2118391, 'commit_sha': CHAPTER,
     'started_at': '2026-11-23T18:01:18.461244Z',
     'status': 'completed', 'review_effort': 'extended',
     'review_complete': True},
]


class ReviewCoverageTests(unittest.TestCase):
    """A skipped head passes only after docs-only changes."""

    def check(self, runs, changed):
        return confirm_gate.coverage_problem(
            runs, REWRAP, lambda base: changed)

    def test_a_complete_review_of_the_head_passes(self):
        runs = [dict(PR44_RUNS[2], commit_sha=REWRAP)]
        self.assertEqual(self.check(runs, None), (None, ''))

    def test_skipped_head_after_readme_change_passes(self):
        problem, note = self.check(PR44_RUNS, ['README.md'])
        self.assertIsNone(problem)
        self.assertIn('0330f4e', note)
        self.assertIn('README.md', note)

    def test_skipped_head_after_agents_md_change_fails(self):
        problem, _ = self.check(
            PR44_RUNS, ['README.md', 'AGENTS.md'])
        self.assertIn('AGENTS.md', problem)

    def test_skipped_head_after_code_change_fails(self):
        problem, _ = self.check(
            PR44_RUNS, ['docs/design/erd.md',
                        'events/models.py'])
        self.assertIn('events/models.py', problem)

    def test_full_review_not_an_ancestor_fails(self):
        problem, _ = self.check(PR44_RUNS, None)
        self.assertIn('0330f4e', problem)

    def test_unreadable_records_fail(self):
        for runs in (None, []):
            with self.subTest(runs=runs):
                problem, _ = self.check(runs, ['README.md'])
                self.assertIn('could not be read', problem)

    def test_no_run_for_the_head_fails(self):
        problem, _ = self.check(PR44_RUNS[2:], ['README.md'])
        self.assertIn('no completed review run of the head',
                      problem)

    def test_only_skipped_runs_fail(self):
        problem, _ = self.check(PR44_RUNS[:2], ['README.md'])
        self.assertIn('no complete review', problem)

    def test_markdown_counts_as_docs_except_agents_md(self):
        self.assertTrue(confirm_gate.is_docs('README.md'))
        self.assertTrue(confirm_gate.is_docs('docs/adr/a.md'))
        self.assertFalse(confirm_gate.is_docs('AGENTS.md'))
        self.assertFalse(confirm_gate.is_docs('x/AGENTS.md'))
        self.assertFalse(confirm_gate.is_docs('events/views.py'))


class ParseRunsTests(unittest.TestCase):
    """Only a list of run records counts as readable."""

    def test_real_output_is_read(self):
        out = 'note\n' + json.dumps({'review_runs': PR44_RUNS})
        self.assertEqual(confirm_gate.parse_runs(0, out),
                         PR44_RUNS)

    def test_malformed_records_are_unreadable(self):
        truncated = json.dumps(
            {'review_runs': [],
             'qar_operation_result_truncated': True})
        for out in ('{"review_runs": [null]}',
                    '{"review_runs": {}}', '[]', 'no json',
                    truncated):
            with self.subTest(out=out):
                self.assertIsNone(
                    confirm_gate.parse_runs(0, out))
        self.assertIsNone(confirm_gate.parse_runs(
            1, json.dumps({'review_runs': PR44_RUNS})))


class VerdictTests(unittest.TestCase):
    """The confirm job's verdict on the head it was handed."""

    def test_docs_only_skip_is_confirmed(self):
        met, text = confirm_gate.verdict(
            PR44_RUNS, REWRAP, [REWRAP, REWRAP],
            lambda b: ['README.md'])
        self.assertTrue(met)
        self.assertIn('only docs changed', text)

    def test_head_moved_after_the_agent_job_fails(self):
        met, text = confirm_gate.verdict(
            PR44_RUNS, CHAPTER, [REWRAP, REWRAP], lambda b: [])
        self.assertFalse(met)
        self.assertIn('moved', text)

    def test_push_while_records_were_read_fails(self):
        met, text = confirm_gate.verdict(
            PR44_RUNS, REWRAP, [REWRAP, CHAPTER],
            lambda b: ['README.md'])
        self.assertFalse(met)
        self.assertIn('moved', text)


class CheckedTests(unittest.TestCase):
    """A failing check still gives a reason, never a crash."""

    def test_an_error_becomes_gate_not_met(self):
        def broken(pr, repo, handed):
            raise RuntimeError('gh pr: HTTP 502')
        self.addCleanup(setattr, confirm_gate, 'confirm',
                        confirm_gate.confirm)
        confirm_gate.confirm = broken
        met, text = confirm_gate.checked('48', 'o/r', REWRAP)
        self.assertFalse(met)
        self.assertIn('HTTP 502', text)

    def test_undecodable_cli_output_is_unreadable(self):
        self.assertIsNone(confirm_gate.parse_runs(
            0, b'\xff\xfe'.decode('utf-8', 'replace')))


class RenameTests(unittest.TestCase):
    """A rename counts under its old name too."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(setattr, confirm_gate, 'ROOT',
                        confirm_gate.ROOT)
        confirm_gate.ROOT = root = Path(folder.name)
        def git(*args):
            return confirm_gate.git(*args)[1].strip()
        confirm_gate.git('init', '-q')
        (root / 'AGENTS.md').write_text('rules\n' * 20)
        git('add', '.')
        git('-c', 'user.name=t', '-c', 'user.email=t@e.x',
            'commit', '-qm', 'one')
        self.base = git('rev-parse', 'HEAD')
        git('mv', 'AGENTS.md', 'README.md')
        git('-c', 'user.name=t', '-c', 'user.email=t@e.x',
            'commit', '-qm', 'two')
        self.head = git('rev-parse', 'HEAD')

    def test_accented_markdown_name_counts_as_docs(self):
        git = confirm_gate.git
        name = 'r\u00e9sum\u00e9.md'
        (confirm_gate.ROOT / name).write_text('x\n')
        git('add', '.')
        git('-c', 'user.name=t', '-c', 'user.email=t@e.x',
            'commit', '-qm', 'three')
        head = git('rev-parse', 'HEAD')[1].strip()
        files = confirm_gate.changed_since(self.head, head)
        self.assertEqual(files, [name])
        self.assertTrue(confirm_gate.is_docs(files[0]))

    def test_renamed_agents_md_is_not_docs_only(self):
        files = confirm_gate.changed_since(self.base, self.head)
        self.assertIn('AGENTS.md', files)
        problem, _ = confirm_gate.coverage_problem(
            [dict(PR44_RUNS[0], commit_sha=self.head),
             dict(PR44_RUNS[2], commit_sha=self.base)],
            self.head,
            lambda b: confirm_gate.changed_since(b, self.head))
        self.assertIn('AGENTS.md', problem)


class QodoCliTests(unittest.TestCase):
    """The key goes only to the pinned, unchanged CLI."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.cli = Path(folder.name) / 'qodo.mjs'
        self.cli.write_text('pinned', encoding='utf-8')
        self.calls = []
        self.addCleanup(setattr, confirm_gate.subprocess, 'run',
                        confirm_gate.subprocess.run)
        confirm_gate.subprocess.run = (
            lambda *a, **k: self.calls.append((a, k)))
        pinned = hashlib.sha256(b'pinned').hexdigest()
        for name, value in {'QODO_API_KEY': 'k',
                            'QODO_CLI_JS': str(self.cli),
                            'QODO_SHA256': pinned}.items():
            self.addCleanup(os.environ.pop, name, None)
            os.environ[name] = value

    def test_changed_cli_never_gets_the_key(self):
        self.cli.write_text('changed', encoding='utf-8')
        self.assertIsNone(confirm_gate.qodo_runs(44, 'o/r'))
        self.assertEqual(self.calls, [])

    def test_no_key_means_no_records(self):
        os.environ['QODO_API_KEY'] = ''
        self.assertIsNone(confirm_gate.qodo_runs(44, 'o/r'))
        self.assertEqual(self.calls, [])


class HandoffTests(unittest.TestCase):
    """A comment-level pass hands the PR to the confirm job."""

    def setUp(self):
        self.posted = []
        self.addCleanup(setattr, agent_runner, 'comment',
                        agent_runner.comment)
        agent_runner.comment = (
            lambda kind, n, text: self.posted.append(text))
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.output = Path(folder.name) / 'out'
        self.addCleanup(os.environ.pop, 'GITHUB_OUTPUT', None)
        os.environ['GITHUB_OUTPUT'] = str(self.output)

    def test_gate_met_on_comment_hands_off(self):
        agent_runner.finish(44, [], [], True, '', REWRAP,
                            REWRAP)
        self.assertIn("Gate met on Qodo's comment",
                      self.posted[-1])
        self.assertIn('confirm job', self.posted[-1])
        self.assertEqual(
            self.output.read_text(encoding='utf-8'),
            f'pr=44\nhead={REWRAP}\n')

    def test_a_failed_gate_hands_nothing_off(self):
        with self.assertRaises(agent_runner.Blocked):
            agent_runner.finish(44, [], [], False, 'Open High.',
                                REWRAP, REWRAP)
        self.assertFalse(self.output.exists())


class SandboxTests(unittest.TestCase):
    """Generated code runs as a user who cannot see secrets."""

    def setUp(self):
        self.calls = []
        self.addCleanup(setattr, agent_runner, 'run',
                        agent_runner.run)
        agent_runner.run = (
            lambda args, env=None: self.calls.append(args)
            or (0, ''))
        for name in ('SANDBOX_USER', 'GITHUB_ACTIONS'):
            self.addCleanup(os.environ.pop, name, None)
            os.environ.pop(name, None)

    def test_manage_runs_as_the_sandbox_user(self):
        os.environ['SANDBOX_USER'] = 'otahque-sandbox'
        os.environ['EURI_API_KEY'] = 'secret-value'
        self.addCleanup(os.environ.pop, 'EURI_API_KEY', None)
        agent_runner.manage('test')
        args = self.calls[-1]
        self.assertEqual(args[:5], ['sudo', '-n', '-u',
                                    'otahque-sandbox', '--'])
        self.assertIn('env', args)
        self.assertIn('-i', args)
        self.assertEqual(args[-2:], ['manage.py', 'test'])
        self.assertNotIn('secret-value', ' '.join(args))
        self.assertIn('umask 000', ' '.join(args))

    def test_manage_runs_directly_outside_actions(self):
        agent_runner.manage('check')
        self.assertEqual(self.calls[-1],
                         ['uv', 'run', 'python', 'manage.py',
                          'check'])

    def test_actions_without_a_sandbox_user_stops(self):
        os.environ['GITHUB_ACTIONS'] = 'true'
        self.assertIn('SANDBOX_USER',
                      agent_runner.sandbox_problem())
        os.environ['SANDBOX_USER'] = 'otahque-sandbox'
        self.assertIsNone(agent_runner.sandbox_problem())

    def test_outside_actions_needs_no_sandbox(self):
        self.assertIsNone(agent_runner.sandbox_problem())


class PushTests(unittest.TestCase):
    """The token never appears in a command line."""

    def setUp(self):
        self.calls = []
        self.addCleanup(setattr, agent_runner.subprocess, 'run',
                        agent_runner.subprocess.run)
        agent_runner.subprocess.run = self.fake_run
        self.addCleanup(setattr, agent_runner, 'guard_git',
                        agent_runner.guard_git)
        agent_runner.guard_git = lambda: None
        self.addCleanup(os.environ.pop, 'GH_TOKEN', None)
        os.environ['GH_TOKEN'] = 'ghs_secret'

    def fake_run(self, args, **kwargs):
        self.calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args, self.code, '', 'denied for ghs_secret')

    def test_push_keeps_the_token_out_of_the_arguments(self):
        self.code = 0
        agent_runner.push('ch21-x')
        args, kwargs = self.calls[-1]
        self.assertNotIn('ghs_secret', ' '.join(args))
        self.assertEqual(kwargs['env']['GIT_PUSH_TOKEN'],
                         'ghs_secret')

    def test_a_failed_push_hides_the_token(self):
        self.code = 1
        with self.assertRaises(agent_runner.Blocked) as caught:
            agent_runner.push('ch21-x')
        self.assertNotIn('ghs_secret', str(caught.exception))


class CommitPathTests(unittest.TestCase):
    """Nothing outside the run's paths reaches a commit."""

    def setUp(self):
        use_layout(self)
        self.calls = []
        for name, value in {
                'guard_git': lambda: None,
                'run': lambda args, env=None:
                    self.calls.append(args) or (0, 'abc1234'),
                }.items():
            self.addCleanup(setattr, agent_runner, name,
                            getattr(agent_runner, name))
            setattr(agent_runner, name, value)
        self.addCleanup(setattr, agent_runner, 'changed_paths',
                        agent_runner.changed_paths)

    def changed(self, *paths):
        agent_runner.changed_paths = lambda: list(paths)

    def test_a_file_changed_outside_the_paths_stops(self):
        self.changed('events/models.py',
                     'factory/agent_runner.py')
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'factory/agent_runner.py'):
            agent_runner.commit('Chapter 22: queries')
        self.assertEqual(self.calls, [])

    def test_settings_changed_beyond_the_ticket_stops(self):
        self.changed('config/settings.py')
        self.addCleanup(setattr, agent_runner,
                        'settings_problems',
                        agent_runner.settings_problems)
        agent_runner.settings_problems = lambda: ['DEBUG']
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'DEBUG'):
            agent_runner.commit('Chapter 22')
        self.assertEqual(self.calls, [])

    def test_allowed_files_are_committed(self):
        self.changed('events/models.py', 'events/tests.py')
        self.assertEqual(agent_runner.commit('Chapter 22'),
                         'abc1234')
        self.assertIn('commit', self.calls[-2])


# The first local review of #47 (24 November 2026), trimmed:
# two action-required findings and one recommended, all new.
KEY_ID = 'a2290413-4f3d-4f2d-9606-782b6ba1727e'
CLI_ID = '4673d4f3-b357-419f-8d9d-748fd44e2e3a'
CRASH_ID = 'd37a93dd-8f96-4328-852e-b15e8cc38796'
LOCAL_47 = {
    'finding_state': {'complete': True,
                      'introduced': [KEY_ID, CLI_ID, CRASH_ID],
                      'still_open': [], 'resolved': [],
                      'dismissed': []},
    'meta': {'coverage': {'complete': True}},
    'findings': [
        {'id': KEY_ID,
         'title': 'Generated code can read the Qodo key',
         'category': 'Security',
         'action_level': 'action_required',
         'description': 'The key is in the runner process.',
         'location': {'file_path': '.github/workflows/agent.yml',
                      'start_line': 87}},
        {'id': CLI_ID,
         'title': 'A replaced Qodo script can receive the key',
         'category': 'Security',
         'action_level': 'action_required',
         'description': 'Hash then open again.',
         'location': {'file_path': 'factory/agent_runner.py',
                      'start_line': 2027}},
        {'id': CRASH_ID,
         'title': 'Malformed review records crash the runner',
         'category': 'Reliability',
         'action_level': 'remediation_recommended',
         'description': 'A null run raises.',
         'location': {'file_path': 'factory/agent_runner.py',
                      'start_line': 2048}},
    ],
}


class LocalFindingsTests(unittest.TestCase):
    """A local review result becomes the gate's findings."""

    def test_levels_map_to_gate_severities(self):
        found = agent_runner.local_findings(LOCAL_47)
        self.assertEqual([f['severity'] for f in found],
                         ['High', 'High', 'Medium'])
        self.assertEqual(found[0]['type'], 'Security')
        self.assertEqual(found[0]['where'],
                         '.github/workflows/agent.yml:87')

    def test_only_open_findings_count(self):
        result = json.loads(json.dumps(LOCAL_47))
        result['finding_state']['introduced'] = [KEY_ID]
        result['finding_state']['resolved'] = [CLI_ID, CRASH_ID]
        found = agent_runner.local_findings(result)
        self.assertEqual([f['title'] for f in found],
                         ['Generated code can read the Qodo key'])

    def test_unknown_level_counts_as_high(self):
        result = json.loads(json.dumps(LOCAL_47))
        result['findings'][2]['action_level'] = 'mystery'
        found = agent_runner.local_findings(result)
        self.assertEqual(found[2]['severity'], 'High')

    def test_incomplete_or_malformed_results_are_unusable(self):
        partial = json.loads(json.dumps(LOCAL_47))
        partial['meta']['coverage']['complete'] = False
        unfinished = json.loads(json.dumps(LOCAL_47))
        unfinished['finding_state']['complete'] = False
        no_state = {k: v for k, v in LOCAL_47.items()
                    if k != 'finding_state'}
        odd = json.loads(json.dumps(LOCAL_47))
        odd['meta'] = 'complete'
        missing = json.loads(json.dumps(LOCAL_47))
        missing['findings'] = missing['findings'][:2]
        unhashable = json.loads(json.dumps(LOCAL_47))
        unhashable['finding_state']['introduced'] = [{'id': 1}]
        for result in (partial, unfinished, no_state, odd, None,
                       [], {'findings': [None]}, missing,
                       unhashable):
            with self.subTest(result=result):
                self.assertIsNone(
                    agent_runner.local_findings(result))


class LocalReviewTests(unittest.TestCase):
    """Before the commit: fix confirmed, list the rest."""

    def setUp(self):
        self.fixed, self.results = [], []
        self.restored = []
        fake = {
            'run_local_review': self.next_result,
            'edit_loop': lambda *a: self.fixed.append(a[-1]),
            'diff': lambda: 'working diff',
            'snapshot': lambda: 'tree1',
            'restore': self.restored.append,
            'finding_files': lambda findings: '',
            'step_files': lambda issue: '',
            'log': lambda text: None,
            'LOCAL_REVIEW_ROUNDS': 2,
        }
        for name, value in fake.items():
            self.addCleanup(setattr, agent_runner, name,
                            getattr(agent_runner, name))
            setattr(agent_runner, name, value)
        self.addCleanup(setattr, agent_runner, 'ask_json',
                        agent_runner.ask_json)
        use_layout(self)

    def next_result(self, issue, round_):
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def only(self, *ids):
        result = json.loads(json.dumps(LOCAL_47))
        result['finding_state']['introduced'] = list(ids)
        return result

    def verdicts(self, *pairs):
        replies = [{'findings': [
            {'n': n, 'verdict': v, 'reason': 'why'}
            for n, v in pairs]}]
        agent_runner.ask_json = lambda messages: replies.pop(0)

    def test_a_confirmed_medium_is_fixed_then_reviewed(self):
        self.results = [self.only(CRASH_ID), self.only()]
        self.verdicts((1, 'confirmed'))
        section, fixed, undo = agent_runner.local_review(
            {'body': 'T'}, [])
        self.assertEqual(self.fixed, ['Local review fix 1'])
        self.assertTrue(fixed)
        self.assertIn('| Fixed |', section)
        self.assertIn('Malformed review records crash',
                      section)
        self.assertIn('No High or Medium finding is left open',
                      section)
        rolled = undo('criteria 3 failed')
        self.assertNotIn('| Fixed |', rolled)
        self.assertIn('Undone with the rollback', rolled)
        self.assertIn('criteria 3 failed', rolled)

    def test_a_disputed_finding_is_left_for_a_human(self):
        self.results = [self.only(KEY_ID)]
        self.verdicts((1, 'disputed'))
        section, fixed, undo = agent_runner.local_review(
            {'body': 'T'}, [])
        self.assertEqual(self.fixed, [])
        self.assertFalse(fixed)
        self.assertIn('| For a human |', section)
        self.assertIn('disputed', section)
        self.assertIn('a human decides', section)

    def test_a_failed_fix_round_is_undone(self):
        self.results = [self.only(CRASH_ID)]
        self.verdicts((1, 'confirmed'))

        def failing(*args):
            raise agent_runner.Blocked('checks still fail')
        agent_runner.edit_loop = failing
        section, fixed, undo = agent_runner.local_review(
            {'body': 'T'}, [])
        self.assertEqual(self.restored, ['tree1'])
        self.assertFalse(fixed)
        self.assertIn('Fix failed; change undone', section)

    def test_a_fix_still_open_next_round_is_not_fixed(self):
        self.results = [self.only(CRASH_ID),
                        self.only(CRASH_ID),
                        self.only(CRASH_ID)]
        self.verdicts((1, 'confirmed'))
        replies = [{'findings': [{'n': 1, 'verdict': 'confirmed',
                                  'reason': 'r'}]}] * 3
        agent_runner.ask_json = lambda messages: replies[0]
        section, _, undo = agent_runner.local_review(
            {'body': 'T'}, [])
        self.assertIn('Still open after the fix', section)
        self.assertNotIn('| Fixed |', section)

    def test_no_snapshot_means_no_fix(self):
        self.results = [self.only(CRASH_ID)]
        self.verdicts((1, 'confirmed'))
        agent_runner.snapshot = lambda: None
        section, fixed, undo = agent_runner.local_review(
            {'body': 'T'}, [])
        self.assertEqual(self.fixed, [])
        self.assertFalse(fixed)
        self.assertIn('no snapshot to undo', section)

    def test_without_main_snapshot_nothing_is_fixed(self):
        self.results = [self.only(CRASH_ID)]
        self.verdicts((1, 'confirmed'))
        section, fixed, _ = agent_runner.local_review(
            {'body': 'T'}, [], can_fix=False)
        self.assertEqual(self.fixed, [])
        self.assertFalse(fixed)
        self.assertIn('no snapshot to undo', section)

    def test_lows_from_every_round_are_kept(self):
        low = self.only(KEY_ID, CRASH_ID)
        low['findings'][0]['action_level'] = 'informational'
        self.results = [low, self.only()]
        self.verdicts((1, 'confirmed'))
        section, _, undo = agent_runner.local_review(
            {'body': 'T'}, [])
        self.assertIn('Generated code can read the Qodo key',
                      section.split('Low findings')[1])

    def test_a_review_that_cannot_run_is_reported(self):
        self.results = [agent_runner.QodoUnavailable('no key')]
        section, fixed, undo = agent_runner.local_review(
            {'body': 'T'}, [])
        self.assertIn('did not run: no key', section)
        self.assertEqual(self.fixed, [])

    def test_an_unusable_result_is_reported(self):
        partial = self.only(KEY_ID)
        partial['meta']['coverage']['complete'] = False
        self.results = [partial]
        section, fixed, undo = agent_runner.local_review(
            {'body': 'T'}, [])
        self.assertIn('incomplete or unreadable', section)


class SnapshotTests(unittest.TestCase):
    """A snapshot that may miss changes is never returned."""

    def setUp(self):
        self.addCleanup(setattr, agent_runner, 'run',
                        agent_runner.run)

    def test_failed_staging_gives_no_snapshot(self):
        codes = {'add': 1, 'write-tree': 0, 'reset': 0}
        agent_runner.run = lambda args, env=None: (
            codes[args[1]], 'a' * 40)
        self.assertIsNone(agent_runner.snapshot())

    def test_a_full_snapshot_is_returned(self):
        agent_runner.run = lambda args, env=None: (0, 'b' * 40)
        self.assertEqual(agent_runner.snapshot(), 'b' * 40)


class RestoreTests(unittest.TestCase):
    """A rollback that fails stops the run."""

    def test_a_failed_git_step_raises(self):
        self.addCleanup(setattr, agent_runner, 'run',
                        agent_runner.run)
        agent_runner.run = lambda args, env=None: (
            (1, 'fatal: bad tree') if 'read-tree' in args
            else (0, ''))
        with self.assertRaisesRegex(agent_runner.Blocked,
                                    'bad tree'):
            agent_runner.restore('a' * 40)


class PrivateCopyTests(unittest.TestCase):
    """Qodo reviews a copy the sandbox user cannot reach."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        agent_runner.ROOT)
        agent_runner.ROOT = root = Path(folder.name)
        run = agent_runner.run
        run(['git', 'init', '-q'])
        (root / 'kept.py').write_text('one\n')
        run(['git', 'add', '.'])
        run(['git', '-c', 'user.name=t', '-c',
             'user.email=t@e.x', 'commit', '-qm', 'base'])
        (root / 'kept.py').write_text('two\n')
        (root / 'new.py').write_text('new\n')
        (root / '.qodo').mkdir()
        (root / '.qodo' / 'session-context.json').write_text(
            '{"notes": "planted"}')

    def test_copy_has_the_change_but_not_untracked_extras(self):
        folder, copy = agent_runner.private_copy()
        self.addCleanup(shutil.rmtree, folder, True)
        self.assertEqual((copy / 'kept.py').read_text(), 'two\n')
        self.assertTrue((copy / 'new.py').exists())
        self.assertNotEqual(copy.resolve(),
                            agent_runner.ROOT.resolve())
        code, url = agent_runner.run(
            ['git', '-C', str(copy), 'remote', 'get-url',
             'origin'])
        self.assertIn('github.com', url)


class DeadlineTests(unittest.TestCase):
    """The local review never runs past the run's limit."""

    def test_no_time_left_stops_before_any_call(self):
        calls = []
        for name, value in {
                'RUN_DEADLINE': 0,
                'private_copy': lambda: (Path('.'), Path('.')),
                'qodo': lambda *a, **k: calls.append(a)}.items():
            self.addCleanup(setattr, agent_runner, name,
                            getattr(agent_runner, name))
            setattr(agent_runner, name, value)
        with self.assertRaises(agent_runner.QodoUnavailable):
            agent_runner.run_local_review({'body': 'T'}, 1)
        self.assertEqual(calls, [])


class LocalCliTests(unittest.TestCase):
    """The local review never runs a changed CLI."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.cli = Path(folder.name) / 'qodo.mjs'
        self.cli.write_text('pinned', encoding='utf-8')
        self.calls = []
        self.addCleanup(setattr, agent_runner.subprocess, 'run',
                        agent_runner.subprocess.run)
        agent_runner.subprocess.run = (
            lambda *a, **k: self.calls.append((a, k)))
        pinned = hashlib.sha256(b'pinned').hexdigest()
        for name, value in {'QODO_API_KEY': 'k',
                            'QODO_CLI_JS': str(self.cli),
                            'QODO_SHA256': pinned}.items():
            self.addCleanup(os.environ.pop, name, None)
            os.environ[name] = value

    def test_changed_cli_is_refused(self):
        self.cli.write_text('changed', encoding='utf-8')
        with self.assertRaises(agent_runner.QodoUnavailable):
            agent_runner.qodo('review', 'status', 'x', cwd='.')
        self.assertEqual(self.calls, [])

    def test_no_key_is_refused(self):
        os.environ['QODO_API_KEY'] = ''
        with self.assertRaises(agent_runner.QodoUnavailable):
            agent_runner.qodo('review', 'status', 'x', cwd='.')


class EditLoopStopTests(unittest.TestCase):
    """A run that cannot pass stops early and says why."""

    def setUp(self):
        self.asked = 0
        fake = {
            'ask': self.reply,
            'apply_edits': lambda reply, allowed: ['x.py'],
            'retry_files': lambda reply, allowed: [],
            'retry_text': lambda paths: '',
            'log': lambda text: None,
            'MAX_ATTEMPTS': 3,
        }
        for name, value in fake.items():
            self.addCleanup(setattr, agent_runner, name,
                            getattr(agent_runner, name))
            setattr(agent_runner, name, value)

    def reply(self, messages):
        self.asked += 1
        return 'edits'

    def test_a_settings_refusal_stops_at_once(self):
        report = ('Settings changes not allowed. The ticket '
                  'opens ADMIN_URL; imports are never open:\n'
                  'config/settings.py line 46: ADMIN_URL = '
                  'config(...)')
        with self.assertRaises(agent_runner.Blocked) as caught:
            agent_runner.edit_loop([], None,
                                   lambda: (False, report),
                                   'Code')
        self.assertEqual(self.asked, 1)
        self.assertIn('settings guard', str(caught.exception))
        self.assertIn('ADMIN_URL', str(caught.exception))

    def test_running_out_names_the_last_failure(self):
        report = 'FAILED (failures=2)\ntest_list_shows_drafts'
        with self.assertRaises(agent_runner.Blocked) as caught:
            agent_runner.edit_loop([], None,
                                   lambda: (False, report),
                                   'Code')
        self.assertEqual(self.asked, 3)
        self.assertIn('still failing after 3 attempts',
                      str(caught.exception))
        self.assertIn('test_list_shows_drafts',
                      str(caught.exception))

    def test_a_long_failure_keeps_its_traceback(self):
        report = '\n'.join(
            ['Traceback (most recent call last):']
            + [f'line {n}' for n in range(80)]
            + ['FAILED (errors=1)'])
        with self.assertRaises(agent_runner.Blocked) as caught:
            agent_runner.edit_loop([], None,
                                   lambda: (False, report),
                                   'Code')
        message = str(caught.exception)
        self.assertIn('Traceback (most recent call last)',
                      message)
        self.assertIn('FAILED (errors=1)', message)
        self.assertIn('lines left out', message)

    def test_partly_applied_edits_say_so(self):
        def partly(reply, allowed):
            raise agent_runner.PartialEdits(
                'b.py does not exist yet.\n'
                'Applied anyway: a.py.',
                ['a.py'])
        agent_runner.apply_edits = partly
        with self.assertRaises(agent_runner.Blocked) as caught:
            agent_runner.edit_loop([], None,
                                   lambda: (True, ''), 'Code')
        message = str(caught.exception)
        self.assertIn('Some of your edits were applied', message)
        self.assertIn('Applied anyway: a.py', message)

    def test_unapplied_edits_are_named_too(self):
        def refuse(reply, allowed):
            raise ValueError(
                'No FILE/SEARCH/REPLACE blocks found.')
        agent_runner.apply_edits = refuse
        with self.assertRaises(agent_runner.Blocked) as caught:
            agent_runner.edit_loop([], None,
                                   lambda: (True, ''), 'Code')
        self.assertIn('No FILE/SEARCH/REPLACE blocks',
                      str(caught.exception))

if __name__ == '__main__':
    unittest.main()
