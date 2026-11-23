# Instructions for coding agents and reviewers

## Project

Otahque is a Django 6.1.2 application that helps volunteer-led
communities run recurring events. This repository is the code of the
Otahque Django book: every merged change is printed in the book, so a
beginner must be able to follow it. The code covers Chapters 6 to 19
(project, settings, URLs, views, templates, static files, Tailwind CSS,
daisyUI, the proposed data model in `docs/design/erd.md`, the `Event`
model, the custom user `accounts.User`, their first migrations, and
the ORM queries behind the event pages).
Data lives only in each reader's local `db.sqlite3`, never in Git;
the event pages show the published events saved there, and test
events are fictional.

Full detail: [docs/STANDARDS.md](docs/STANDARDS.md),
[docs/VERSION_BASELINE.md](docs/VERSION_BASELINE.md), and
[docs/BOOK_SYNC.md](docs/BOOK_SYNC.md) (how merged code becomes book
content). Where the project stands: the "Where the code is now" table
in [README.md](README.md).

## Setup

```
uv sync --locked
```

Create `.env` beside `manage.py` with the names in `.env.example` and
your own `DJANGO_SECRET_KEY`. Only to change styles, with Node.js
26.13.0:

```
npm ci
npm run build
```

## Verify

Run before opening a pull request, and report the commands actually
run:

```
uv run python manage.py check
uv run python manage.py test
```

`test` with no app name runs the tests of every app (`events`,
and `accounts` from Chapter 17).

If a template or `static/otahque/source.css` changed, also run
`npm run build` and commit the rebuilt `static/otahque/site.css`.

## Rules

### 1. At most 65 characters per line

- Applies to: Python files, `templates/` and `events/templates/`,
  `config/settings.py`, and commands shown in docs. Indentation counts.
- Exempt: migrations that `makemigrations` writes keep
  Django's own layout, as the book prints them (Chapter 18).
  Only the agent runner makes them; nobody hand-wraps them.
- Why: the code is printed in the book. A longer line wraps on the
  page, looks like two statements, and is retyped wrongly. Split with
  parentheses or implicit string concatenation instead.

### 2. Tests first, including the failure case

- Applies to: every new or changed view, URL, template, filter, or
  setting in `events/` and `config/`.
- Why: each step must run from the previous checkpoint, and the reader
  sees the test fail before the code makes it pass. Cover the failure
  case too: a 404, an empty state, or escaped input. The first commit
  of a pull request may hold the failing tests; every merge to `main`
  passes.

### 3. Security: escaping and secrets

- Applies to: templates, `events/templatetags/`, any HTML built in
  Python, `config/settings.py`, and sample data.
- Why: event text will come from users. `|safe`, `mark_safe`, and
  `{% autoescape off %}` need a stated reason and a test that proves
  untrusted input is still escaped. Build HTML with `format_html`, not
  string concatenation.
- Why: readers copy these settings. No secret in Git;
  `DJANGO_SECRET_KEY` has no default, so a missing key stops Django;
  `DEBUG` is on only for the exact text `True`. Sample data is
  fictional: no real people, emails, or attendance.

### 4. Use only what the book has taught by that chapter

- Applies to: all code, one planned capability per pull request.
- Why: the reader can follow only what has been taught. No models
  before Chapter 15, no custom user before Chapter 17, no migrations
  applied before the custom user exists, and no class-based views before
  Chapter 35. Do not bundle work from later chapters. If a change alters
  code that an existing chapter already prints, say so in the pull
  request; the author decides the chapter revision.

### 5. Pinned versions and generated CSS

- Applies to: `pyproject.toml`, `uv.lock`, `package.json`,
  `package-lock.json`, and `static/otahque/site.css`.
- Why: the book's commands must give every reader the same result. Do
  not add or upgrade a dependency without the author's decision, and do
  not use an API newer than the pinned version. `site.css` is
  generated: edit `source.css` or a template, never `site.css`.

### 6. Docstrings follow PEP 257

- Applies to: Python files in `events/`, `accounts/`, and `config/`.
- What: every module starts with a one-line docstring saying what it
  holds. Every class and every public function or method has a
  docstring: one summary line ending in a full stop, then, only when
  needed, a blank line and a short paragraph (why, limits, or the
  chapter that changes it). A function or method summary is a command,
  "Return the zone to show times in.", and never ends in a question
  mark. No Args or Returns sections. Comments explain why, not what, in
  full sentences above the line they explain.
- Exempt: inner `Meta` classes, `__str__`, `setUp`, `setUpTestData`, a
  decorator's inner wrapper, and test methods whose names already say
  what they check; every test class still has a docstring. Files from
  `startproject` keep Django's docstrings, generated migrations keep
  Django's header, and `startapp` stubs that no chapter fills in stay
  as generated.
- Why: the book prints these files, and Django's own code follows PEP
  257. The docstring is where a beginner reads what the code is for,
  so code added for a chapter carries its docstrings in that same pull
  request, within rule 1's 65 characters.

### 7. Review against the chapter plan

- Applies to: every review finding, from Qodo, an agent, or a person,
  and to the answer it gets.
- What: judge a change by its own ticket and the chapter it belongs
  to. A finding that asks for something a later chapter teaches is not
  a defect of this change: the answer names that chapter (see "Where
  later work lands" in `docs/STANDARDS.md`) and the code stays as it
  is. If no later chapter covers it, it is a finding now. A security
  defect (rule 3), a failing test, and a broken rule 1 are always
  findings, whatever the chapter. A pull request that applies one
  book-wide change across several chapters, such as a docstring pass,
  is one capability.
- Why: the code grows one chapter at a time and is incomplete on
  purpose. Chapter 16's `Event` accepts an `ends_at` before `starts_at`
  because validation and constraints are taught in Chapter 21; adding
  them earlier would print code the reader has not been taught
  (rule 4).

## Quality gate

A coding task is done only when this gate is met. It applies to any
agent working here (the factory's runner, or a coding agent in an
editor) and uses Qodo's severity labels and finding types (Bug, Rule
violation, Requirement gap).

- Fix every valid High or Medium finding, of any type, Bugs
  included, then run the checks above and review again until none is
  left.
- A High or Medium finding may be disputed only with evidence from
  the code, the ticket, or these rules (rule 7 names the later
  chapter). A disputed finding goes to a human, and the task is not
  done until that person decides.
- Leave Low findings unchanged, Low Rule violations included, and
  list every Low finding in the final report for a human.
- A finding whose severity cannot be read counts as High.
- The final report lists each finding with its type, severity, and
  what was done; the checks run; and the commit the latest completed
  review covers, which must be the head commit.
- Report the task as not done, with the reason, if a High or Medium
  finding is still open or disputed, a check failed, the latest
  review does not cover the head commit, or fix rounds stop making
  progress.

## Commits

Do not commit `.env`, `db.sqlite3`, `.venv/`, or `node_modules/`.
Commit messages are plain and describe the change, with no tool or AI
attribution.
