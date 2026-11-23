# Code standards

These rules come from the book's editorial rules. Code here is printed
in the book exactly as committed, so a rule that looks cosmetic is
usually about the page. Reviewers, human or automated, should flag any
change that breaks one.

## Shape of every change

1. **One capability per pull request**, matching one planned book step.
   Do not bundle work from later chapters.
2. **Tests first.** Add or change the test, run it, and see it fail for
   the expected reason before writing the code. From Chapter 9 onward,
   every new behaviour gets a small meaningful test, including its
   failure case (404, empty state, escaping).
3. **Runnable from the previous checkpoint.** Every merge to `main`
   passes `uv run python manage.py check` and
   `uv run python manage.py test` (every app) from a fresh
   `uv sync --locked`.
   Inside a pull request, the first commit may hold failing tests.
4. **Chapter order.** Use only what the book has taught by that chapter.
   For example: no models before Chapter 15, no custom user before
   Chapter 17, no migrations applied before the custom user exists, no
   class-based views before Chapter 35, no static files before
   Chapter 13.

## Formatting

- **At most 65 characters per line**, indentation included, in Python,
  templates, settings, and shown commands. Split with parentheses or
  implicit string concatenation, as `config/settings.py` does.
  Generated migrations are exempt: they keep the layout
  `makemigrations` gives them, as the book prints them (Chapter 18).
- Four-space indentation in Python; two spaces in templates.
- Single-quoted strings in Python, as Django's generated files use.

## Docstrings and comments

Code follows [PEP 257](https://peps.python.org/pep-0257/), as Django's
own code does.

- Every module in `events/`, `accounts/`, and `config/` starts with a
  one-line docstring saying what it holds.
- Every class and every public function or method has a docstring: one
  summary line ending in a full stop, then, only when needed, a blank
  line and a short paragraph (why, limits, or the chapter that changes
  it). No Args or Returns sections.
- A function or method summary is a command in the imperative mood:
  "Return the zone to show times in.", not "The zone to show times
  in." It never ends in a question mark: "Return whether ...". Module
  and class summaries stay descriptions.
- Exempt: inner `Meta` classes, `__str__`, the test hooks `setUp` and
  `setUpTestData`, a decorator's inner wrapper (`functools.wraps` gives
  it the view's docstring), and test methods whose names already say
  what they check. Every test class has a docstring.
- Files from `startproject` keep Django's docstrings, generated
  migrations keep Django's header, and `startapp` stubs that no chapter
  fills in stay as generated. Functions in data migrations have
  docstrings.
- Comments explain why, not what, in full sentences above the line
  they explain.
- Code added for a chapter carries its docstrings in the same pull
  request, within the 65-character limit.

## Versions and dependencies

- Python 3.14.9, Django 6.1.2, python-decouple 3.8, locked in `uv.lock`
  and managed with uv 0.13.5. See [VERSION_BASELINE.md](VERSION_BASELINE.md).
- From Chapter 14: Node.js 26.13.0 builds the stylesheet with Tailwind
  CSS 4.3.4 and daisyUI 5.7.50, pinned exactly in `package-lock.json`.
  `site.css` is generated: change `source.css` or a template, then run
  `npm run build`.
- No new dependency, and no upgrade, without the author's decision.
- Never use an API from a later Django version than the pinned one.

## Reviewing against the chapter plan

Judge a change by its own ticket and the chapter it belongs to. The
code is incomplete on purpose, so a finding that asks for work a later
chapter teaches is answered by naming that chapter, and the code stays
as it is. It becomes a finding on that chapter's pull request. If no
later chapter covers it, it is a finding now.

Always findings, whatever the chapter: a security defect, a failing
test, and a line over 65 characters.

A pull request that applies one book-wide change across several
chapters, such as a docstring pass, is one capability.

### Where later work lands

| Topic | Chapter |
|---|---|
| Custom user model | 17 |
| Migrations | 18 |
| ORM queries | 19 |
| Relationships between models | 20 |
| Validation, constraints, `clean()`, `CheckConstraint` | 21 |
| QuerySets and managers | 22 |
| Django admin | 23 |
| Forms, and validation in forms | 24 to 25 |
| Sign-in and accounts | 27 |
| Sessions, cookies, and time zones | 28 |
| Permissions, ownership, and roles | 30 |
| PostgreSQL | 32 |
| Transactions and concurrency | 33 |
| Class-based views | 35 |
| Email | 43 |
| Background tasks | 44 |
| APIs and Django REST framework | 47 to 49 |

The full contents are on the book site; this table lists the topics
reviews ask for most.

## Security

- No secret in Git. Settings read values through python-decouple;
  `DJANGO_SECRET_KEY` has no default and a missing key stops Django.
- `DEBUG` is on only for the exact text `True`.
- Keep Django's automatic escaping. `mark_safe`, `|safe`, and
  `{% autoescape off %}` need a stated reason and a test that proves
  untrusted input is still escaped. Build HTML in Python with
  `format_html`, not string concatenation.
- Sample data is fictional. No real people, emails, or attendance.

## Recovery advice

Any instruction in docs or comments that tells a reader how to recover
from a mistake must never reset, overwrite, or delete their work. Compare
with a separate reference copy instead.

## Commits

Plain messages that describe the change. No tool or AI attribution lines.
