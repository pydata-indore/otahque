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
   for lack of them also counts. If the ticket names its tests
   (`test_...` in backticks), every one must be written before
   the step is accepted, since the code step cannot add tests.
4. Code: the model may change the local apps (not migrations,
   except an empty `migrations/__init__.py`), the template
   folders, the settings and URL modules, `README.md`, and
   `docs/`, but not the tests. In the settings it may change
   only the settings the Runner section names (see "The ticket's
   Runner section").
5. The model edits with FILE/SEARCH/REPLACE blocks, or with an
   APPEND block that adds lines at the end of a file (a new test
   class) without quoting the file. Each file's blocks apply
   together or not at all; a file with a bad block stays as it
   was, while the other files' edits are kept and the model is
   told which, so it resends only the rest. A label line copied
   from the reference or a file heading (`--- … ---`) is dropped
   from code for a Python or template file; a SEARCH that held
   only such a label becomes an APPEND, which is what it meant.
   After every edit the script itself runs the checks: allowed
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
7. A Qodo local review of the uncommitted change, before the
   first commit (see "The local Qodo review"). Confirmed High
   or Medium findings are fixed and the change is reviewed
   again; disputed ones and Lows are listed for a human.
8. One commit, a pushed branch, and a PR that closes the issue,
   with the failing-test output, the criteria table, the
   checks, and the local review.
9. It waits for Qodo's review of the PR's head commit on GitHub
   (the review comment names the commit it covers) and applies
   the quality gate in `AGENTS.md`. It reads every open finding
   from the review comment: its severity group, type, and file.
   The model judges each High or Medium finding as confirmed or
   disputed, with evidence, and sees the current text of the
   files the findings name. Confirmed ones are fixed in a new
   commit, the checks run, and it posts `/agentic_review` for
   the next round. Low findings are never changed. A finding
   whose severity it cannot read counts as High.
10. The run ends with a gate report on the PR: every High or
   Medium finding with its type, severity and verdict, the Low
   findings flagged for a human, and the reviewed commit against
   the PR head. "Gate met" only when no High or Medium finding is
   open and the latest review covers the head. The run itself
   can only say "Gate met on Qodo's comment": the comment names
   the head even when Qodo skipped it, so a second job confirms
   the gate in Qodo's review records (see "Qodo's review
   records"). Otherwise the
   report says the task is not done and why (a disputed finding,
   findings left after `REVIEW_ROUNDS`, or a stale review), and
   the issue gets `agent-blocked`. A human reviews and merges.

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

- Up to 3 attempts per step (`MAX_ATTEMPTS`). A settings guard
  refusal ends the step at once, since no retry can make a
  setting the ticket does not open pass. In the code steps that
  stops the run, and that part goes to a person; in a local
  review fix the round is undone and the run goes on with the
  code that passed. When a step runs out of attempts, the issue
  comment names the last failure.
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

## Qodo's review records

When the run ends with "Gate met on Qodo's comment", it hands the
PR number and head commit to a second job, `confirm`, which runs
[`confirm_gate.py`](confirm_gate.py). That job reads Qodo's
records of the PR with the Qodo CLI (`qodo read
pr-review-session findings --extended`). Each run there says
whether it was complete or skipped. The gate is confirmed when a
complete run covers the head, or when the head was skipped and
only Markdown other than `AGENTS.md` changed since the last
complete run, on the same branch. Records it cannot read, a
missing `QODO_API_KEY`, a CLI that does not match its pinned
hash, or a head that moved after the agent job all count as "not
met": the job comments on the PR, labels the issue
`agent-blocked`, and fails.

`confirm` runs on a fresh machine with code from `main`. Nothing
from the PR is executed there, only `git diff` on its commits.
The agent job also holds the Qodo key, for its local review,
but there the generated code runs as the sandbox user (see "The
sandbox user"), which cannot read the runner's environment.

The CLI is pinned, the same way in both jobs. Each downloads
one release,
`https://get.qodo.ai/releases/<version>/qodo.mjs`, and refuses it
unless its SHA-256 matches the hash Qodo publishes for that release
(`releases/<version>/release.json`). Qodo's installer script is
never run, and auto-update is off. The CLI gets the Qodo key and
no GitHub token, and the runner checks its hash again before each
call. To move the pin, change `QODO_VERSION` and `QODO_SHA256`
together, in both jobs, in a reviewed PR.

## The local Qodo review

Before its first commit, the runner reviews its own change the
way a person does locally: `qodo review --base <main's commit>
--ticket <issue> --async`, collected with `qodo review status`.
It runs on a private copy of the working tree, in a folder only
the runner can open, because the CLI holds the Qodo key and reads
files such as `.qodo/session-context.json` by itself, and the
sandbox user can write the checkout.
Qodo's levels are read as the gate's severities:
`action_required` is High, `remediation_recommended` is Medium,
`informational` is Low, and an unknown level counts as High.
High and Medium findings go through the same triage as the PR
review, judged against the working-tree diff. Confirmed ones are
fixed with the usual checks, then the change is reviewed again,
for up to `LOCAL_REVIEW_ROUNDS` rounds (2). Lows are never
changed. The PR description lists every finding, its verdict,
and anything left open or disputed for a human.

The local review helps; it does not decide. If it cannot run
(no key, a CLI that fails its hash, an error, a timeout, or
incomplete coverage), the run says so in the PR and carries on.
The PR review and the `confirm` job are still the gate.

## The sandbox user

Every `manage.py` command runs the code the model wrote, so in
Actions the runner runs them as a separate user,
`otahque-sandbox`, which `agent.yml` creates. The runner holds
`EURI_API_KEY` and the GitHub token in its environment, and any
process of the same user can read that through
`/proc/<pid>/environ`; a different user cannot. The commands
start through `sudo -n -u otahque-sandbox` with an empty
environment and the checkout's `.venv` Python. Without
`SANDBOX_USER`, a run in Actions stops at the start.

The sandbox user can write the checkout but cannot read or
write `.git/`, `factory/` or `.github/`, and can only read
`.venv/`. The checkout's top folder is sticky, like `/tmp`: the
sandbox can add a new app there but cannot rename or remove the
runner's folders to swap in its own. Before every commit the
runner checks the changed paths again, since the generated code
ran after the last check, and stops if anything outside the
allowed paths changed. `git push`
gets the token from a credential helper that reads it from the
push's own environment, because any user can read a process's
command line. The sandbox can still reach the network; it holds
nothing secret to send. `checks.yml` runs the Django checks as
the same user and checks that it cannot read the job's
environment, so every pull request shows the sandbox works.

## Checks on every pull request

[`checks.yml`](../.github/workflows/checks.yml) runs on every pull
request into `main`, the runner's included: `manage.py check`,
`manage.py test`, `makemigrations --check --dry-run`, the runner's
own tests, and the 65-character limit (rule 1). Branch protection
requires it to pass before a merge. The runner opens its pull
requests with `AGENT_GH_TOKEN`, so the checks start on them. A pull
request opened with the plain workflow token would not start them,
so the runner refuses to run without that secret.

## Testing the runner

The runner's own tests are not part of the book, so
`manage.py test` does not find them. From the repository root:

```
python -m unittest factory/test_agent_runner.py
```

They cover how edits are applied (each file's blocks or none
of that file's, APPEND blocks, and a clear error for a missing
file), the paths built from the
layout, the Runner section, the settings guard, and the
migration step.

## Settings

Under Settings, Secrets and variables, Actions:

| Kind | Name | Use |
|---|---|---|
| Secret | `EURI_API_KEY` | Key for the model API |
| Variable | `EURI_MODEL` | Model name |
| Variable | `EURI_BASE_URL` | OpenAI-compatible base URL |
| Secret | `AGENT_GH_TOKEN` | Token for the PR and comments; the run stops without it |
| Secret | `QODO_API_KEY` | Qodo key for the local review and the `confirm` job; without it the gate is never confirmed |
| Variable | `QODO_BASE_URL` | Qodo API address, `https://sdk.qodo.ai` |

Without `AGENT_GH_TOKEN`, the run stops at the start with that
reason: a PR from `github-actions[bot]` would never start the
required checks, and Qodo would not review it. The checks run
without any token or key in their environment, and the checkout
keeps no credentials.
Git runs with hooks turned off, and the run refuses to commit
or push if `.git/config` or `.git/hooks` changed while the
generated code ran.
