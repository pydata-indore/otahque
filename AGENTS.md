# Instructions for coding agents and reviewers

## Project

Otahque is a Django 6.1.2 application that helps volunteer-led
communities run recurring events. This repository is the code of the
Otahque Django book: every merged change is printed in the book, so a
beginner must be able to follow it. The code covers Chapters 6 to 14
(project, settings, URLs, views, templates, static files, Tailwind CSS,
and daisyUI). There are no models or accounts yet; sample events are
fictional and held in memory.

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
uv run python manage.py test events
```

If a template or `static/otahque/source.css` changed, also run
`npm run build` and commit the rebuilt `static/otahque/site.css`.

## Rules

### 1. At most 65 characters per line

- Applies to: Python files, `templates/` and `events/templates/`,
  `config/settings.py`, and commands shown in docs. Indentation counts.
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

## Commits

Do not commit `.env`, `db.sqlite3`, `.venv/`, or `node_modules/`.
Commit messages are plain and describe the change, with no tool or AI
attribution.
