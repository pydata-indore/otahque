# The agent workflow

Adding the label `ready-for-agent` to an issue starts
[`.github/workflows/agent.yml`](../.github/workflows/agent.yml),
which runs [`agent_runner.py`](agent_runner.py) on one ticket. It
can also be started by hand: Actions, Agent, Run workflow, with
the issue number.

## What the run does

1. Labels the issue `agent-working` and links the run.
2. Reads where the code lives from the settings on `main` (see
   "Where the agent may work"), reads the ticket's Runner
   section, then runs the checks on `main`; a failing `main`
   stops it. It runs `startapp` for each app the Runner section
   names.
3. Tests first: the model may change only the test modules of
   the local apps and of the project package (`config/`), plus
   the empty `__init__.py` files of a new app so its tests are
   found. The script runs the tests and accepts them only if
   they fail for the missing code. When the ticket has the
   runner make migrations, a test database that cannot be built
   for lack of them also counts.
4. Code: the model may change the local apps (not migrations,
   except an empty `migrations/__init__.py`), the template
   folders, the settings and URL modules, `README.md`, and
   `docs/`, but not the tests. In the settings it may change
   only the settings the Runner section names (see "The ticket's
   Runner section").
5. After every edit the script itself runs the checks: allowed
   paths, the settings guard, at most 65 characters per line,
   then `makemigrations` if the ticket asks for it,
   `manage.py check`, and `manage.py test` (every app). If a
   path is refused, a `migrations/__init__.py` is not empty, or
   the settings guard fails, Django is not run at all. Last,
   `makemigrations --check --dry-run`: a model change with no
   migration fails the checks when the ticket makes migrations
   or once `main` has migrations, and is only recorded before
   that (Chapters 15 to 17 write models with no migration on
   purpose). Once `main` has migrations, a model change on
   `main` itself with no migration stops the run at the
   baseline.
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

## Where the agent may work

Nothing about the project's folders is written into the runner.
Before the agent changes anything, the runner asks Django, on
`main`, for:

- the local apps: `INSTALLED_APPS` entries whose folder is in
  this repository, so `django.contrib` and other installed
  packages drop out;
- the template folders: `TEMPLATES` `DIRS`;
- the settings module and the `ROOT_URLCONF` module; the folder
  that holds the settings is the project package, whose
  `tests*.py` files count as tests.

Those are read once. An edit to the settings during the run
never widens the agent's reach, so a new app comes only from a
`startapp` line in the ticket. Some places stay closed whatever
the settings say: `factory/`, any path with a part that starts
with a dot (`.env`, `.github/`, `.venv/`), `node_modules/`,
`build/`, and `static/`. `static/` stays closed until the run
can rebuild `site.css` with `npm run build`.

## The ticket's Runner section

What the runner itself does for a ticket is written in the
ticket, in a `## Runner` section with one item a line:

```
## Runner

- startapp accounts
- makemigrations
- settings: INSTALLED_APPS, AUTH_USER_MODEL
```

- `startapp <app>`: the runner creates the app before the
  tests step, as the book does, and the agent then edits the
  files it made.
- `makemigrations [<app> ...] [--name <name>]`: after every
  code edit the runner removes the migrations it made earlier
  in the run and runs this command again, so the migrations
  always match the models. The agent can never write or edit a
  migration. Generated migrations keep Django's layout, as the
  book prints them, so the 65-character check skips them. Every
  code, criteria and review-fix prompt tells the model this,
  and the review triage dismisses a finding that asks to
  reformat a generated migration, under rule 1.
- `settings: NAME, NAME`: the settings the agent may change.
  A changed line must belong to a top-level `NAME = ...` (or
  the comment lines directly above it), or be a blank line
  between statements. The value must be a plain literal
  (strings, lists, numbers and so on): a call or a walrus in a
  value could quietly set another setting, and so could a
  second statement on the same line, so those lines belong to
  no setting. `SECRET_KEY`, `DEBUG`, and
  `ALLOWED_HOSTS` can never be named, and imports, docstrings,
  and the `try` block that reads the secret key are never open.

A ticket without the section gets none of these. Any other line
stops the run before the first model call, with the line and
the forms allowed, so the ticket can be fixed and labelled
again.

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

They cover how edits are applied (every block or none, and a
clear error for a missing file), the paths built from the
layout, the Runner section, the settings guard, and the
migration step.

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
