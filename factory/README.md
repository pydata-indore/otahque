# The agent workflow

Adding the label `ready-for-agent` to an issue starts
[`.github/workflows/agent.yml`](../.github/workflows/agent.yml),
which runs [`agent_runner.py`](agent_runner.py) on one ticket. It
can also be started by hand: Actions, Agent, Run workflow, with
the issue number.

## What the run does

1. Labels the issue `agent-working` and links the run.
2. Runs the checks on `main` first; a failing `main` stops it.
3. Tests first: the model may change only the test modules of
   the apps in `APPS` (`events/`, `accounts/`), plus the empty
   `__init__.py` files of a new app so its tests are found.
   The script runs the tests and accepts them only if they fail.
4. Code: the model may change those apps (not migrations, except
   an empty `migrations/__init__.py`), `config/settings.py`,
   `templates/`, `README.md`, and `docs/`, but not the tests.
   In `config/settings.py` it may only add or remove an
   `INSTALLED_APPS` entry and set `AUTH_USER_MODEL` (with
   comments above it); any other settings line fails the checks,
   so secrets, `DEBUG`, and hosts stay out of reach.
5. After every edit the script itself runs the checks:
   allowed paths, the settings guard, at most 65 characters per
   line, `manage.py check`, and `manage.py test` (every app).
   `makemigrations --check --dry-run` is recorded only.
6. A separate model call checks each acceptance criterion
   against the diff and the check output. Unmet criteria go
   back to the code step once.
7. One commit, a pushed branch, and a PR that closes the issue,
   with the failing-test output, the criteria table, and the
   checks.
8. It waits for Qodo's review, sorts each open finding into
   confirmed or dismissed, fixes the confirmed ones in a new
   commit, runs the checks, and posts `/agentic_review`. A
   Qodo comment that shows only resolved findings counts as a
   finished review: the run then logs that nothing is open and
   writes its summary.
9. A summary comment on the PR lists every verdict. A human
   reviews and merges.

## Reference code

The published book repository, `SamChawla/otahque-web-book`, is
ahead of this one, so a run uses only the chapter named in the
ticket title ("Chapter 16: ..."). It fetches that chapter's
section pages and keeps the project-file listings the chapter
prints (`events/models.py`, `events/tests.py`, and so on), and
adds them to the model's brief as read-only reference. Listings
marked "not part of the project", practice scripts, and other
chapters are left out. The model uses them to match names,
structure and style; it never edits them, and the ticket,
`AGENTS.md` and the 65-character limit come first. A title with
no chapter number gets no reference. The brief marks the
reference as untrusted data, and the source is pinned to a
reviewed book commit, not `main`. To change it, set the Actions
variables `REFERENCE_REPO` and `REFERENCE_REF` (Settings,
Secrets and variables, Actions, Variables); unset, the pinned
defaults apply, and the pin is moved by a reviewed change. The
fetch has a 2 minute budget. If it fails or runs out, the run
logs it and continues without the rest.

## Limits and stopping

- Up to 3 attempts per step (`MAX_ATTEMPTS`).
- Up to 2 rounds of review fixes (`REVIEW_ROUNDS`).
- 20 minutes to wait for Qodo (`QODO_WAIT_MINUTES`).
- 75 minutes for the runner (`RUN_MINUTES`), inside the job's
  90 minutes; a cancelled or timed-out job still labels the
  issue `agent-blocked`.
- The new tests must fail for the missing code: a syntax
  error, or a failure in tests that existed before, is sent
  back to the model.

When a limit is hit, the model answers `BLOCKED`, or Qodo does
not reply, the issue gets `agent-blocked` and a comment with the
reason: no Qodo reply at all points to the PR or comments not
coming from a user account (`AGENT_GH_TOKEN`), while a Qodo
comment the run cannot read is reported separately. The run
never force-pushes, never merges, and never
reuses an existing branch.

## Testing the runner

The runner's own tests are not part of the book, so
`manage.py test` does not find them. From the repository root:

```
python -m unittest factory/test_agent_runner.py
```

They cover how edits are applied: every block or none, and a
clear error for a missing file.

## Settings

Under Settings, Secrets and variables, Actions:

| Kind | Name | Use |
|---|---|---|
| Secret | `EURI_API_KEY` | Key for the model API |
| Variable | `EURI_MODEL` | Model name |
| Variable | `EURI_BASE_URL` | OpenAI-compatible base URL |
| Secret, optional | `AGENT_GH_TOKEN` | Token used instead of the workflow token |

Without `AGENT_GH_TOKEN`, PRs and comments come from
`github-actions[bot]`. The checks run without any token or key
in their environment, and the checkout keeps no credentials.
Git runs with hooks turned off, and the run refuses to commit
or push if `.git/config` or `.git/hooks` changed while the
generated code ran.
