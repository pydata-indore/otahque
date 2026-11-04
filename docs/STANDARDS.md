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
   `uv run python manage.py test events` from a fresh `uv sync --locked`.
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
- Four-space indentation in Python; two spaces in templates.
- Single-quoted strings in Python, as Django's generated files use.
- Comments explain why, briefly. Do not add comments that repeat the code.

## Versions and dependencies

- Python 3.14.9, Django 6.1.2, python-decouple 3.8, locked in `uv.lock`
  and managed with uv 0.13.5. See [VERSION_BASELINE.md](VERSION_BASELINE.md).
- From Chapter 14: Node.js 26.13.0 builds the stylesheet with Tailwind
  CSS 4.3.4 and daisyUI 5.7.50, pinned exactly in `package-lock.json`.
  `site.css` is generated: change `source.css` or a template, then run
  `npm run build`.
- No new dependency, and no upgrade, without the author's decision.
- Never use an API from a later Django version than the pinned one.

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
