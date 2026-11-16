"""Work one labelled issue from ticket to reviewed pull request.

Started by .github/workflows/agent.yml. Standard library only.
The model proposes edits; this script applies them, runs the
checks itself, and stops for help when the retry limit is hit.
See factory/README.md.
"""

import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / 'factory-log.md'
ISSUE = os.environ['ISSUE']
REPO = os.environ['REPO']
RUN_URL = os.environ.get('RUN_URL', '')
MAX_ATTEMPTS = int(os.environ.get('MAX_ATTEMPTS', '3'))
REVIEW_ROUNDS = int(os.environ.get('REVIEW_ROUNDS', '2'))
QODO_WAIT = 60 * int(os.environ.get('QODO_WAIT_MINUTES', '20'))
MAX_LINE = 65
# Stop with a reason before the job's own timeout kills us.
RUN_DEADLINE = time.time() + 60 * int(
    os.environ.get('RUN_MINUTES', '75'))
GIT_STATE = None
# Read-only reference: the published book's code, fetched for
# each run. It guides style and structure; it is never edited.
REFERENCE_REPO = os.environ.get(
    'REFERENCE_REPO', 'SamChawla/otahque-web-book')
REFERENCE_REF = os.environ.get('REFERENCE_REF', 'main')
REFERENCE_FILE_LIMIT = 12000
REFERENCE_TOTAL_LIMIT = 60000
REFERENCE_PATHS = re.compile(
    r'app/(README\.md|docs/[\w/.-]+\.md'
    r'|(events|accounts|registrations|config)/'
    r'(?!migrations/)[\w/]*(models|forms|views|urls|admin'
    r'|tests)\.py'
    r'|(events/)?templates/[\w/]+\.html)$')

# The agent may change only these paths.
ALLOWED = (
    re.compile(r'events/(?!migrations/)[\w/]+\.(py|html)$'),
    re.compile(r'templates/[\w/]+\.html$'),
    re.compile(r'README\.md$'),
    re.compile(r'docs/[\w/]+\.md$'),
)
TESTS = re.compile(r'events/tests[\w/]*\.py$')
CONTEXT = (
    'AGENTS.md', 'docs/STANDARDS.md', 'docs/BOOK_SYNC.md',
    'README.md', 'docs/design/erd.md',
)
LABELS = {
    'ready-for-agent': ('0e8a16', 'The agent may pick this up'),
    'agent-working': ('fbca04', 'The agent is working on it'),
    'agent-pr-open': ('1d76db', 'Agent PR open; needs a human'),
    'agent-blocked': ('d93f0b', 'The agent stopped; needs help'),
}
BANNED = re.compile(
    r'co-authored-by|generated (by|with)|\bclaude\b|\bgpt'
    r'|\bchatgpt\b|\bAI\b|\bLLM\b|\beuri\b', re.I)


class Blocked(Exception):
    """Stop the run and ask a human for help."""


# ---------- logging and commands ----------

def log(text):
    print(text, flush=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(text + '\n')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write(text + '\n')


def safe_env():
    """The environment without any token or key."""
    return {
        k: v for k, v in os.environ.items()
        if not re.search(r'TOKEN|KEY|SECRET', k)
    }


def run(args, env=None):
    done = subprocess.run(
        args, cwd=ROOT, env=env or safe_env(),
        capture_output=True, text=True, timeout=900,
    )
    return done.returncode, done.stdout + done.stderr


def gh(*args, data=None):
    """Run the GitHub CLI with the token; fail loudly."""
    done = subprocess.run(
        ['gh', *args], cwd=ROOT, input=data,
        capture_output=True, text=True, timeout=120,
    )
    if done.returncode:
        raise RuntimeError(f'gh {args[0]}: {done.stderr}')
    return done.stdout


def gh_json(path):
    return json.loads(gh('api', '--paginate', path))


def now():
    return datetime.now(timezone.utc)


def out_of_time():
    if time.time() >= RUN_DEADLINE:
        raise Blocked('The run reached its time limit '
                      '(RUN_MINUTES).')


def tail(text, lines=40):
    return '\n'.join(text.strip().splitlines()[-lines:])


def fence(text):
    return '```text\n' + text.strip() + '\n```'


# ---------- the model ----------

def ask(messages):
    """One chat completion from the OpenAI-compatible API."""
    url = os.environ['EURI_BASE_URL'].rstrip('/')
    body = json.dumps({
        'model': os.environ['EURI_MODEL'],
        'messages': messages,
        'temperature': 0.2,
        'max_tokens': int(
            os.environ.get('MAX_TOKENS', '8000')),
    }).encode()
    request = urllib.request.Request(
        url + '/chat/completions', data=body,
        headers={
            'Authorization':
                'Bearer ' + os.environ['EURI_API_KEY'],
            'Content-Type': 'application/json',
            # The API's firewall refuses urllib's default
            # User-Agent with 403, error code 1010.
            'User-Agent': 'otahque-agent/1.0',
        },
    )
    for wait in (10, 30, 60, None):
        try:
            with urllib.request.urlopen(
                request, timeout=300,
            ) as response:
                reply = json.load(response)
            text = reply['choices'][0]['message']['content']
            messages.append(
                {'role': 'assistant', 'content': text})
            return text
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors='replace')
            log(f'- Model call failed: {error}: '
                f'{detail[:500]}')
            if error.code < 500 and error.code != 429:
                raise Blocked('The model API refused the '
                              f'request ({error.code}).')
            if wait is None:
                raise Blocked('The model API kept failing.')
            time.sleep(wait)
        except (urllib.error.URLError, KeyError,
                TimeoutError) as error:
            log(f'- Model call failed: {error}')
            if wait is None:
                raise Blocked('The model API kept failing.')
            time.sleep(wait)


EDIT = re.compile(
    r'^FILE: *(?P<path>\S+)\n'
    r'<<<<<<< SEARCH\n(?P<search>.*?)'
    r'^=======\n(?P<replace>.*?)'
    r'^>>>>>>> REPLACE$',
    re.M | re.S,
)


def blocked_reason(text):
    found = re.search(r'^BLOCKED: *(.+)$', text, re.M)
    return found.group(1).strip() if found else None


def apply_edits(text, allowed):
    """Apply every edit block; return the paths changed."""
    edits = list(EDIT.finditer(text))
    if not edits:
        raise ValueError('No FILE/SEARCH/REPLACE blocks found.')
    changed = []
    for edit in edits:
        path = edit['path']
        if not allowed(path):
            raise ValueError(f'{path} may not be changed now.')
        target = ROOT / path
        search, replace = edit['search'], edit['replace']
        if not search.strip():
            if target.exists():
                raise ValueError(
                    f'{path} exists: give a SEARCH block.')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(replace, encoding='utf-8')
        else:
            old = target.read_text(encoding='utf-8')
            if old.count(search) != 1:
                raise ValueError(
                    f'SEARCH text in {path} must match exactly'
                    ' once; copy it from the current file.')
            target.write_text(
                old.replace(search, replace),
                encoding='utf-8')
        changed.append(path)
    return changed


def may_edit(path):
    return any(rule.fullmatch(path) for rule in ALLOWED)


def file_text(paths):
    parts = []
    for path in paths:
        target = ROOT / path
        if target.is_file():
            parts.append(
                f'--- {path} ---\n'
                + target.read_text(encoding='utf-8'))
    return '\n\n'.join(parts)


def code_files():
    code, out = run(['git', 'ls-files', 'events', 'templates'])
    return [
        p for p in out.split()
        if p.endswith(('.py', '.html'))
        and '/migrations/' not in p
    ]


# ---------- checks run by this script, not the model ----------

def changed_paths():
    code, out = run(['git', 'status', '--porcelain'])
    paths = []
    for line in out.splitlines():
        path = line[3:].strip()
        if path not in ('factory-log.md',):
            paths.append(path)
    return paths


def long_lines(paths):
    problems = []
    for path in paths:
        if not path.endswith(('.py', '.html')):
            continue
        target = ROOT / path
        if not target.is_file():
            continue
        lines = target.read_text(encoding='utf-8').splitlines()
        for number, line in enumerate(lines, 1):
            if len(line) > MAX_LINE:
                problems.append(
                    f'{path}:{number} has {len(line)} '
                    f'characters. The line is:\n{line}')
    return problems


def manage(*args):
    return run(['uv', 'run', 'python', 'manage.py', *args])


def run_checks():
    """Return (passed, report) for the current working tree."""
    paths = changed_paths()
    report = []
    passed = True
    banned = [p for p in paths if not may_edit(p)]
    if banned:
        passed = False
        report.append('Not allowed: ' + ', '.join(banned))
    lines = long_lines(paths)
    if lines:
        passed = False
        report.append('Lines over 65 characters:\n'
                      + '\n'.join(lines))
    code, out = manage('check')
    passed = passed and code == 0
    report.append('$ manage.py check\n' + tail(out, 20))
    code, out = manage('test', 'events')
    passed = passed and code == 0
    report.append('$ manage.py test events\n' + tail(out))
    code, out = manage(
        'makemigrations', '--check', '--dry-run')
    report.append(
        '$ manage.py makemigrations --check --dry-run'
        f' (exit {code}, recorded only)\n' + tail(out, 10))
    return passed, '\n\n'.join(report)


def fails_for_new_code(out):
    """True if a new test fails, or the new code is missing.

    A missing name (ImportError, AttributeError) means the
    code under test does not exist yet; otherwise one of the
    test methods added in this run must be among the failures.
    """
    if re.search(r'cannot import name|has no attribute'
                 r'|No module named', out):
        return True
    code, added = run(['git', 'diff', '-U0', '--', 'events'])
    names = re.findall(r'^\+\s*def (test_\w+)', added, re.M)
    failed = re.findall(r'^(?:FAIL|ERROR): (test_\w+)',
                        out, re.M)
    return bool(set(names) & set(failed))


def test_count(report):
    found = re.search(r'Ran (\d+) tests?', report)
    return found.group(1) if found else '?'


# ---------- prompts ----------

RULES = """You are the coding agent of the Otahque factory.
The code is printed in a beginner's Django book, so follow the
project rules in AGENTS.md exactly. You cannot run commands:
a script applies your edits and runs the checks, then shows
you the results.

Answer ONLY with edit blocks in this exact form:

FILE: events/models.py
<<<<<<< SEARCH
lines copied exactly from the current file
=======
the new lines
>>>>>>> REPLACE

Use several blocks for several changes. For a new file, leave
SEARCH empty. Every SEARCH must match the file exactly once.
Keep every Python and template line at most 65 characters.
If the ticket cannot be done without breaking a rule, answer
with one line: BLOCKED: <the reason>.
"""


REFERENCE_NOTE = (
    '\n\n# Reference (read only)\n\n'
    'These files come from the published book repository. '
    'Use them to match naming, structure and style when the '
    'ticket needs the same kind of code. Never edit them and '
    'do not copy anything the ticket does not ask for. The '
    'ticket, AGENTS.md and the 65-character limit come first '
    'if they disagree.\n\n')
REFERENCE_TEXT = None


def reference_text():
    """Return the book's code as read-only reference text.

    Failure never stops a run: the ticket and this repository's
    own files are enough, so report it and carry on.
    """
    try:
        tree = json.loads(gh(
            'api', f'repos/{REFERENCE_REPO}/git/trees/'
            f'{REFERENCE_REF}?recursive=1'))['tree']
        # Tests last, so the size limit trims them first.
        paths = sorted(
            (item['path'] for item in tree
             if item['type'] == 'blob'
             and REFERENCE_PATHS.fullmatch(item['path'])),
            key=lambda p: (p.endswith('tests.py'), p))
        parts, total = [], 0
        for path in paths:
            text = gh(
                'api', '-H',
                'Accept: application/vnd.github.raw',
                f'repos/{REFERENCE_REPO}/contents/{path}'
                f'?ref={REFERENCE_REF}')
            text = text[:REFERENCE_FILE_LIMIT]
            if total + len(text) > REFERENCE_TOTAL_LIMIT:
                break
            total += len(text)
            parts.append(
                f'--- {REFERENCE_REPO}:{path} ---\n{text}')
        log(f'- Reference: {len(parts)} files from '
            f'{REFERENCE_REPO}@{REFERENCE_REF}')
        return '\n\n'.join(parts)
    except (RuntimeError, ValueError, KeyError,
            subprocess.SubprocessError) as error:
        log(f'- Reference unavailable, continuing without: '
            f'{error}')
        return ''


def project_brief(issue):
    global REFERENCE_TEXT
    if REFERENCE_TEXT is None:
        REFERENCE_TEXT = reference_text()
    return (
        f'# Ticket #{ISSUE}: {issue["title"]}\n\n'
        f'{issue["body"]}\n\n# Project files\n\n'
        + file_text(CONTEXT) + '\n\n# Code\n\n'
        + file_text(code_files())
        + (REFERENCE_NOTE + REFERENCE_TEXT
           if REFERENCE_TEXT else ''))


def edit_loop(messages, allowed, verify, stage):
    """Ask, apply, verify; retry with feedback up to the limit.

    verify() returns (ok, report). Returns the last report.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        out_of_time()
        log(f'- {stage}: attempt {attempt} of {MAX_ATTEMPTS}')
        reply = ask(messages)
        reason = blocked_reason(reply)
        if reason:
            raise Blocked(f'{stage}: the agent said: {reason}')
        try:
            changed = apply_edits(reply, allowed)
        except ValueError as error:
            feedback = f'Your edits were not applied: {error}'
            log(f'  - {feedback}')
        else:
            names = ', '.join(sorted(set(changed)))
            log(f'  - Changed: {names}')
            ok, report = verify()
            if ok:
                return report
            feedback = 'The checks failed:\n\n' + report
            if 'Lines over' in report:
                feedback += (
                    '\n\nFor each long line, send a block whose '
                    'SEARCH is that exact line and whose '
                    'REPLACE splits or shortens it to at most '
                    f'{MAX_LINE} characters. Count the '
                    'characters; do not change other lines.')
            log('  - Checks failed:\n' + fence(tail(report, 25)))
        messages.append({'role': 'user', 'content': (
            feedback + '\n\nCurrent files you changed:\n\n'
            + file_text(changed_paths())
            + '\n\nSend corrected edit blocks.')})
    raise Blocked(
        f'{stage}: still failing after {MAX_ATTEMPTS} attempts.')


def ask_json(messages):
    for attempt in range(2):
        reply = ask(messages)
        found = re.search(r'\{.*\}', reply, re.S)
        if found:
            try:
                return json.loads(found.group(0))
            except json.JSONDecodeError:
                pass
        messages.append({'role': 'user', 'content':
                         'Answer with one valid JSON object.'})
    raise Blocked('The agent did not return valid JSON.')


def diff():
    run(['git', 'add', '-A', '--', '.', ':!factory-log.md'])
    code, out = run(['git', 'diff', '--cached'])
    run(['git', 'reset', '-q'])
    return out


# ---------- GitHub ----------

def ensure_labels():
    have = {
        label['name'] for label in json.loads(gh(
            'label', 'list', '-R', REPO, '--json', 'name',
            '--limit', '200'))
    }
    for name, (color, text) in LABELS.items():
        if name not in have:
            gh('label', 'create', name, '-R', REPO,
               '--color', color, '--description', text)


def set_label(add, remove=()):
    args = ['issue', 'edit', ISSUE, '-R', REPO,
            '--add-label', add]
    for name in remove:
        args += ['--remove-label', name]
    gh(*args)


def comment(kind, number, text):
    gh(kind, 'comment', str(number), '-R', REPO,
       '--body-file', '-', data=text)


def git_state():
    """Git config and hooks, which generated code must not
    change."""
    git = ROOT / '.git'
    hooks = sorted(
        p.name for p in (git / 'hooks').iterdir()
        if not p.name.endswith('.sample'))
    return (git / 'config').read_bytes(), hooks


def guard_git():
    if git_state() != GIT_STATE:
        raise Blocked('.git/config or .git/hooks changed during '
                      'the run; not committing or pushing.')


def git_identity():
    return [
        '-c', 'core.hooksPath=/dev/null',
        '-c', 'user.name=otahque-agent',
        '-c', 'user.email=41898282+github-actions[bot]'
        '@users.noreply.github.com',
    ]


def commit(message):
    if BANNED.search(message):
        message = 'Apply the change requested in #' + ISSUE
    guard_git()
    run(['git', 'add', '-A', '--', '.', ':!factory-log.md'])
    code, out = run(
        ['git', *git_identity(), 'commit', '-q', '-m', message])
    if code:
        raise Blocked('git commit failed:\n' + out)
    code, sha = run(['git', 'rev-parse', '--short', 'HEAD'])
    return sha.strip()


def push(branch):
    guard_git()
    token = os.environ['GH_TOKEN']
    remote = (f'https://x-access-token:{token}'
              f'@github.com/{REPO}.git')
    # No hooks, and no token or key in the environment: the
    # only credential is the one in the push URL.
    done = subprocess.run(
        ['git', '-c', 'core.hooksPath=/dev/null', 'push',
         remote, f'HEAD:refs/heads/{branch}'],
        cwd=ROOT, env=safe_env(), capture_output=True,
        text=True, timeout=120)
    if done.returncode:
        raise Blocked('git push failed:\n'
                      + done.stderr.replace(token, '***'))


def branch_name(title):
    found = re.match(r'Chapter (\d+):\s*(.*)', title)
    words = re.findall(r'[a-z0-9]+', title.lower())
    if found:
        rest = re.findall(r'[a-z0-9]+', found[2].lower())
        return f'ch{int(found[1]):02d}-' + '-'.join(rest[:2])
    return f'issue-{ISSUE}-' + '-'.join(words[:3])


# ---------- Qodo ----------

def plain(text):
    text = re.sub(r'</?s>', '~~', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(re.sub(r'\n{3,}', '\n\n', text))


def is_qodo(item):
    return item['user']['login'].startswith('qodo')


def wait_for_review(pr, since):
    """Wait for Qodo's review comment to appear or be updated."""
    stamp = since.strftime('%Y-%m-%dT%H:%M:%SZ')
    deadline = min(time.time() + QODO_WAIT, RUN_DEADLINE)
    while time.time() < deadline:
        time.sleep(30)
        for item in gh_json(
                f'repos/{REPO}/issues/{pr}/comments'):
            body = item['body']
            if (is_qodo(item)
                    and 'Code Review by Qodo' in body
                    and item['updated_at'] >= stamp
                    and re.search(r'\(\d+\)', body)):
                time.sleep(60)  # let the edit settle
                return item['id']
    out_of_time()
    raise Blocked(
        f'Qodo did not review PR #{pr} within '
        f'{QODO_WAIT // 60} minutes.')


def review_text(pr, comment_id):
    main = gh_json(f'repos/{REPO}/issues/comments/{comment_id}')
    # Qodo strikes through a finding once it is resolved; such
    # inline comments are left out so they are not fixed twice.
    inline = [
        f'{c["path"]}:{c.get("line")}\n{plain(c["body"])}'
        for c in gh_json(f'repos/{REPO}/pulls/{pr}/comments')
        if is_qodo(c) and '<s>' not in c['body']
    ]
    text = plain(main['body']) + '\n\n' + '\n\n'.join(inline)
    return text[:20000]


# ---------- the run ----------

def main():
    LOG.write_text('', encoding='utf-8')
    log(f'## Agent run for #{ISSUE}\n')
    if RUN_URL:
        log(f'Run: {RUN_URL}\n')
    ensure_labels()
    global GIT_STATE
    GIT_STATE = git_state()
    issue = json.loads(gh(
        'issue', 'view', ISSUE, '-R', REPO,
        '--json', 'title,body,state'))
    if issue['state'] != 'OPEN':
        raise Blocked(f'#{ISSUE} is not open.')
    set_label('agent-working', ['ready-for-agent'])
    comment('issue', ISSUE,
            f'The agent picked this up. Run: {RUN_URL}')

    branch = branch_name(issue['title'])
    code, out = run(['git', 'ls-remote', '--heads', 'origin',
                     branch])
    if out.strip():
        raise Blocked(f'Branch {branch} already exists; '
                      'delete or rename it first.')
    run(['git', 'switch', '-c', branch])
    log(f'Branch: `{branch}`\n')

    log('### 1. Baseline checks')
    ok, report = run_checks()
    if not ok:
        raise Blocked('main fails its checks before any '
                      'change:\n' + fence(report))
    baseline = test_count(report)
    log(f'- main passes: {baseline} tests\n')

    log('### 2. Tests first')
    messages = [
        {'role': 'system', 'content': RULES},
        {'role': 'user', 'content': project_brief(issue) + (
            '\n\nStep 1 of 2: write ONLY the new or changed '
            'tests the ticket asks for, in events/tests.py. '
            'Do not touch any other file. The tests must fail '
            'now, before the code exists.')},
    ]

    def tests_fail():
        lines = long_lines(changed_paths())
        if lines:
            return False, ('Lines over 65 characters:\n'
                           + '\n'.join(lines))
        code, out = manage('test', 'events')
        if code == 0:
            return False, (
                'The tests PASS without the new code, so they '
                'do not test it. Make them fail now.\n'
                + tail(out))
        if re.search(r'SyntaxError|IndentationError', out):
            return False, (
                'The test file does not run at all. Fix it so '
                'the tests fail only for the missing code.\n'
                + tail(out))
        if not fails_for_new_code(out):
            return False, (
                'The tests fail, but not because of the new '
                'code: no new test fails and nothing the '
                'ticket adds is missing. Fix the tests.\n'
                + tail(out))
        tests_fail.output = out
        return True, out

    edit_loop(messages, TESTS.fullmatch, tests_fail, 'Tests')
    red = tail(tests_fail.output, 30)
    log('- The new tests fail as required:\n' + fence(red))

    log('\n### 3. Code')
    messages.append({'role': 'user', 'content': (
        'The tests fail as required:\n\n' + red
        + '\n\nStep 2 of 2: write the code and README change '
        'that make every test pass and meet each acceptance '
        'criterion. Do NOT change any test file now: if a '
        'test is wrong, answer BLOCKED. Current files:\n\n'
        + file_text(code_files() + ['README.md']))})

    def no_test_edits(path):
        return may_edit(path) and not TESTS.fullmatch(path)

    report = edit_loop(messages, no_test_edits, run_checks,
                       'Code')
    log(f'- All checks pass: {test_count(report)} tests\n')

    log('### 4. Acceptance criteria')
    for check_pass in (1, 2):
        checked = accept(issue, report, red)
        unmet = [c for c in checked['criteria']
                 if not c['met']]
        rows = '\n'.join(
            f'| {c["n"]} | {c["criterion"]} | '
            f'{"Met" if c["met"] else "NOT met"}: '
            f'{c["observed"]} |' for c in checked['criteria'])
        log('| # | Criterion | Observed |\n|---|---|---|\n'
            + rows)
        if not unmet:
            break
        if check_pass == 2:
            raise Blocked('Acceptance criteria not met: '
                          + ', '.join(str(c['n'])
                                      for c in unmet))
        log('- Back to the code for the unmet criteria')
        messages.append({'role': 'user', 'content': (
            'These acceptance criteria are not met yet:\n'
            + json.dumps(unmet, indent=1)
            + '\n\nFix them without changing test files. '
            'Current files:\n\n'
            + file_text(code_files() + ['README.md']))})
        report = edit_loop(messages, no_test_edits,
                           run_checks, 'Code (criteria)')

    sha = commit(checked['commit'])
    push(branch)
    log(f'\n- Commit `{sha}` pushed to `{branch}`')
    bullets = '\n'.join(f'- {b}' for b in checked['bullets'])
    body = (
        f'Closes #{ISSUE}. Opened by the agent workflow after '
        f'the `ready-for-agent` label. Run: {RUN_URL}\n\n'
        f'{bullets}\n\n## Tests first\n\nThe new tests were run '
        f'before the code and failed:\n\n{fence(red)}\n\n'
        f'## Acceptance criteria from #{ISSUE}, checked\n\n'
        '| # | Criterion | Observed |\n|---|---|---|\n'
        f'{rows}\n\n## Checks run\n\nUbuntu 24.04 (GitHub '
        'Actions), uv with the locked environment:\n\n'
        f'{fence(report)}\n\nNot run: Windows, macOS; '
        '`npm run build`.\n\nPlease review against '
        '`docs/STANDARDS.md` and the ticket: 65-character '
        'lines, chapter order, escaping. A human decides '
        'whether to merge.\n')
    started = now()
    url = gh('pr', 'create', '-R', REPO, '--base', 'main',
             '--head', branch, '--title', issue['title'],
             '--body-file', '-', data=body).strip()
    pr = url.rstrip('/').split('/')[-1]
    log(f'- PR: {url}\n')
    set_label('agent-pr-open', ['agent-working'])

    review(pr, branch, issue, messages, started)


def review(pr, branch, issue, messages, since):
    verdicts = []
    for round_ in range(1, REVIEW_ROUNDS + 2):
        log(f'### 5.{round_} Qodo review')
        comment_id = wait_for_review(pr, since)
        findings = review_text(pr, comment_id)
        triage = ask_json([
            {'role': 'system', 'content': RULES.split(
                'Answer ONLY')[0] + 'Answer with one JSON '
                'object.'},
            {'role': 'user', 'content': (
                f'# Ticket\n{issue["body"]}\n\n# Diff\n'
                f'{diff_from_main()}\n\n# Qodo review\n'
                f'{findings}\n\nText between ~~ marks is '
                'already resolved: ignore it. Investigate '
                'each open finding against the code and the '
                'ticket. Return JSON: {"findings": [{"title": '
                '"short", "verdict": "confirmed" or '
                '"dismissed", "reason": "why"}]}')},
        ])
        found = triage.get('findings', [])
        verdicts += [(round_, f) for f in found]
        for f in found:
            log(f'- {f["verdict"]}: {f["title"]} '
                f'({f["reason"]})')
        confirmed = [
            f for f in found if f['verdict'] == 'confirmed']
        if not confirmed:
            log('- No confirmed findings open.\n')
            finish(pr, verdicts, round_, blocked=None)
            return
        if round_ > REVIEW_ROUNDS:
            break
        log(f'\n### 5.{round_} Fixing {len(confirmed)} '
            'finding(s)')
        messages.append({'role': 'user', 'content': (
            'Qodo reviewed the PR. Fix ONLY these confirmed '
            'findings; keep the tests passing. You may change '
            'tests now if a finding is about a test.\n\n'
            + json.dumps(confirmed, indent=1)
            + '\n\nFull review:\n' + findings
            + '\n\nCurrent files:\n\n'
            + file_text(code_files() + ['README.md']))})
        edit_loop(messages, may_edit, run_checks,
                  f'Review fix {round_}')
        titles = '; '.join(f['title'] for f in confirmed)
        sha = commit(('Fix review findings: ' + titles)[:72])
        push(branch)
        log(f'- Fix commit `{sha}` pushed')
        since = now()
        comment('pr', pr, '/agentic_review')
    finish(pr, verdicts, REVIEW_ROUNDS, blocked=(
        f'Confirmed findings remain after {REVIEW_ROUNDS} '
        'fix rounds.'))


def accept(issue, report, red):
    """Ask a fresh conversation to check every criterion."""
    return ask_json([
        {'role': 'system', 'content': (
            'You check a change against its ticket. Be strict '
            'and only use the evidence given. Answer with one '
            'JSON object.')},
        {'role': 'user', 'content': (
            f'# Ticket\n{issue["body"]}\n\n# Diff\n{diff()}'
            f'\n\n# Checks\n{report}\n\n# Failing tests, '
            f'run before the code existed\n{red}\n\n'
            'Notes: a script will make exactly one commit '
            'with your message (no attribution) and put the '
            'failing-test output above in the PR body; '
            'judge those criteria on that basis.\n\n'
            'Return JSON: {"criteria": [{"n": 1, '
            '"criterion": "short", "met": true, "observed": '
            '"evidence"}], "commit": "plain one-line commit '
            'message, imperative, no tool names", "bullets": '
            '["`file`: what changed"]}')},
    ])


def diff_from_main():
    code, out = run(['git', 'diff', 'origin/main...HEAD'])
    return out


def finish(pr, verdicts, rounds, blocked):
    lines = '\n'.join(
        f'- Round {r}: {f["verdict"]}: {f["title"]}. '
        f'{f["reason"]}' for r, f in verdicts) or '- None.'
    state = (f'Stopped for help: {blocked}' if blocked
             else 'Ready for a human to review and merge.')
    comment('pr', pr, (
        f'Agent summary ({RUN_URL})\n\nQodo findings and the '
        f'agent\'s verdicts:\n\n{lines}\n\nReview rounds: '
        f'{rounds}. {state}'))
    if blocked:
        raise Blocked(blocked)


def stop(reason):
    log(f'\n**Stopped:** {reason}')
    try:
        set_label('agent-blocked',
                  ['agent-working', 'ready-for-agent'])
        comment('issue', ISSUE, (
            f'The agent stopped and needs help.\n\n{reason}\n\n'
            f'Run log: {RUN_URL}'))
    except RuntimeError as error:
        log(f'Could not report on the issue: {error}')


if __name__ == '__main__':
    try:
        main()
    except Blocked as reason:
        stop(str(reason))
        sys.exit(1)
    except Exception as error:
        stop(f'Unexpected error: {error!r}')
        raise
