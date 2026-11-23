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



class AppsToCreateTests(unittest.TestCase):
    """The runner creates a listed app the ticket names."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, agent_runner, 'ROOT',
                        agent_runner.ROOT)
        agent_runner.ROOT = Path(self.tmp.name)
        (agent_runner.ROOT / 'events').mkdir()

    def apps(self, body):
        return agent_runner.apps_to_create({'body': body})

    def test_a_named_missing_app_is_created(self):
        self.assertEqual(self.apps('A new `accounts` app'),
                         ['accounts'])

    def test_an_existing_app_is_not_created_again(self):
        self.assertEqual(self.apps('Change `events`'), [])

    def test_an_app_not_in_the_list_is_ignored(self):
        self.assertEqual(self.apps('A new `payments` app'), [])


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


if __name__ == '__main__':
    unittest.main()
