"""Confirm the quality gate in Qodo's review records.

The agent job ends with "Gate met on Qodo's comment", but Qodo's
comment names the head commit even when Qodo skipped it (#44).
This script runs in a separate job, on a fresh machine where no
generated code has run, so the Qodo key is never on a machine the
model's code could reach. It reads Qodo's records of the PR and
decides whether a complete review covers the head (AGENTS.md,
"Quality gate").
"""

import hashlib
import json
import os
import posixpath
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def is_docs(path):
    """Say whether a changed file counts as documentation.

    Markdown counts, except AGENTS.md: it holds the rules the
    reviewers and agents follow, so a change needs a review.
    """
    return (path.endswith('.md')
            and posixpath.basename(path) != 'AGENTS.md')


def qodo_runs(pr, repo):
    """Return Qodo's recorded review runs for the PR, or None.

    None when the key or the pinned CLI is missing, the CLI does
    not match its pinned hash, or the records cannot be read.
    The CLI gets the Qodo key and no GitHub token, and runs
    outside the checkout.
    """
    key = os.environ.get('QODO_API_KEY', '')
    cli = os.environ.get('QODO_CLI_JS', '')
    if not key or not cli:
        return None
    try:
        digest = hashlib.sha256(
            Path(cli).read_bytes()).hexdigest()
    except OSError:
        return None
    if digest != os.environ.get('QODO_SHA256', ''):
        print('Qodo CLI does not match its pinned hash.')
        return None
    env = {k: v for k, v in os.environ.items()
           if not any(w in k for w in ('TOKEN', 'KEY',
                                       'SECRET'))}
    env.update(QODO_API_KEY=key,
               QODO_BASE_URL=os.environ.get('QODO_BASE_URL', ''),
               QODO_DISABLE_AUTOUPDATE='1',
               QODO_DISABLE_SKILLS_AUTOUPDATE='1',
               QODO_NO_KEYCHAIN='1')
    url = f'https://github.com/{repo}/pull/{pr}'
    try:
        done = subprocess.run(
            ['node', cli, 'read', 'pr-review-session',
             'findings', '--pr-url', url, '--extended',
             '--json'],
            cwd=tempfile.gettempdir(), env=env,
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace')
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f'Qodo CLI failed: {error!r}')
        return None
    return parse_runs(done.returncode, done.stdout or '')


def parse_runs(code, out):
    """Return the review runs from the CLI's output, or None.

    Anything but a list of run records counts as unreadable.
    """
    if code:
        return None
    try:
        data = json.loads(out[out.find('{'):])
    except ValueError:
        return None
    if (not isinstance(data, dict)
            or data.get('qar_operation_result_truncated')):
        return None
    runs = data.get('review_runs')
    if (not isinstance(runs, list)
            or not all(isinstance(r, dict) for r in runs)):
        return None
    return runs


def git(*args):
    """Run git in the checkout; return (code, output)."""
    done = subprocess.run(['git', *args], cwd=ROOT,
                          capture_output=True, text=True,
                          encoding='utf-8', errors='replace')
    return done.returncode, done.stdout


def changed_since(base, head):
    """List the files changed from base to head, or None.

    None when base is not an ancestor of head, or a commit is
    unknown here: then the gate cannot pass on docs alone.
    """
    code, _ = git('merge-base', '--is-ancestor', base, head)
    if code:
        return None
    # A rename is listed under both names, so AGENTS.md or a
    # code file moved to a .md name still counts as changed.
    # -z keeps names such as docs/résumé.md unquoted.
    code, out = git('diff', '--name-only', '--no-renames',
                    '-z', base, head)
    if code:
        return None
    return [p for p in out.split('\0') if p]


def coverage_problem(runs, head, changed):
    """Return (problem, note) from Qodo's records of the head.

    problem is None when the gate may pass, and note then says
    why a skipped head was accepted. changed(base) lists the
    files changed from base to the head, or None.
    """
    if not runs:
        return ("Qodo's review records could not be read, so "
                'a complete review of the head cannot be '
                'confirmed.', '')
    done = sorted(
        (r for r in runs if r.get('status') == 'completed'),
        key=lambda r: str(r.get('started_at') or ''),
        reverse=True)
    if any(r.get('commit_sha') == head
           and r.get('review_complete') is True for r in done):
        return None, ''
    if not any(r.get('commit_sha') == head for r in done):
        return (f'Qodo has no completed review run of the head '
                f'`{head[:7]}`.', '')
    full = next((r for r in done
                 if r.get('review_complete') is True), None)
    if not full:
        return (f'Qodo has no complete review of this PR; the '
                f'head `{head[:7]}` was skipped.', '')
    base = str(full.get('commit_sha') or '')
    files = changed(base)
    if files is None:
        return (f'Qodo skipped the head `{head[:7]}`, and its '
                f'last complete review (`{base[:7]}`) is not '
                'an earlier commit of this branch.', '')
    other = [p for p in files if not is_docs(p)]
    if other:
        return (f'Qodo skipped the head `{head[:7]}`, and '
                'files other than docs changed since its last '
                f'complete review (`{base[:7]}`): '
                + ', '.join(other[:10]) + '.', '')
    return None, (f'Qodo skipped the head `{head[:7]}`; only '
                  'docs changed since its last complete review '
                  f'(`{base[:7]}`): '
                  + (', '.join(files) or 'none') + '.')


def verdict(runs, handed, heads, changed):
    """Return (met, text) for the confirm job's report.

    handed is the head the agent job saw; heads are the PR head
    read before and after Qodo's records. A push at any point
    means the gate was checked on old code.
    """
    current = heads[-1] if heads else None
    if not current or any(h != handed for h in heads):
        return False, (
            f'The PR head moved from `{handed[:7]}` to '
            f'`{(current or "unknown")[:7]}` after the agent '
            'job, so its gate does not cover the head.')
    problem, note = coverage_problem(runs, current, changed)
    if problem:
        return False, problem
    return True, note or (
        f'Qodo completed a review of the head `{current[:7]}`.')


def gh(*args):
    """Run the GitHub CLI with the job's token; fail loudly."""
    done = subprocess.run(['gh', *args], cwd=ROOT,
                          capture_output=True, text=True,
                          encoding='utf-8')
    if done.returncode:
        raise RuntimeError(f'gh {args[0]}: {done.stderr}')
    return done.stdout


def pr_head(pr, repo):
    """Return the PR's head commit on GitHub."""
    return gh('pr', 'view', pr, '-R', repo, '--json',
              'headRefOid', '-q', '.headRefOid').strip()


def confirm(pr, repo, handed):
    """Return (met, text): Qodo's records against the head."""
    before = pr_head(pr, repo)
    git('fetch', '--no-tags', 'origin', f'pull/{pr}/head')
    runs = qodo_runs(pr, repo)
    # Read again: a push while the records were read would
    # leave the newest commit unchecked.
    after = pr_head(pr, repo)
    return verdict(runs, handed, [before, after],
                   lambda base: changed_since(base, after))


def checked(pr, repo, handed):
    """Run confirm(); any error is a gate not met, with why."""
    try:
        return confirm(pr, repo, handed)
    except Exception as error:  # noqa: BLE001
        return False, ('The records check itself failed, so '
                       'the gate is not confirmed: '
                       f'{error!r}'[:500])


def main():
    """Check the records and post the result on the PR."""
    repo, pr = os.environ['REPO'], os.environ['PR']
    issue = os.environ['ISSUE']
    run_url = os.environ.get('RUN_URL', '')
    met, text = checked(pr, repo, os.environ['HEAD'])
    if met:
        body = ('**Gate confirmed in Qodo\'s records.** '
                f'{text} Ready for a human to review and merge.')
    else:
        body = ('**Gate not met: the task is not done.** '
                + text)
    gh('pr', 'comment', pr, '-R', repo, '--body',
       f'Records check ({run_url})\n\n{body}')
    if not met:
        gh('issue', 'edit', issue, '-R', repo,
           '--add-label', 'agent-blocked')
        gh('issue', 'comment', issue, '-R', repo, '--body',
           'The agent stopped and needs help.\n\n'
           f'Quality gate not met: {text}\n\nRun: {run_url}')
        sys.exit(1)


if __name__ == '__main__':
    main()
