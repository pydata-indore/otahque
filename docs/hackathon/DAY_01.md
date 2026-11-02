# Day 1: first delivery, 2 November 2026

Capability: Chapter 12 of the book. Every page shares one layout and
navigation, the event list row is a reusable partial, and a tested
`sample_label` filter marks fictional titles without giving up escaping.

Branch: `day-01-ch12-layout`, based on `chapters-06-11-baseline` (the
Chapter 11 code, written before the hackathon), so this pull request
shows only the Chapter 12 changes.

## Commits

1. Failing tests for the layout, navigation, row partial, and filter.
2. The implementation.
3. This log.

The book's Chapter 12 was written from this code on the same day and
prints these files exactly.

## Verified locally (Windows, uv 0.13.5, Python 3.14.9, Django 6.1.2)

Every listing in the chapter was applied in printed order to a fresh copy
of the Chapter 11 checkpoint, and every command run in PowerShell 5.1 and
Git Bash.

| Check | Result |
|---|---|
| Chapter 11 starting point | 9 tests, OK |
| Tests before the implementation | 14 run; 7 failures and 3 errors, each for the expected reason |
| After each chapter step | Failures fall as planned: layout, then navigation, then partial, then filter |
| `uv run python manage.py check` | No issues |
| `uv run python manage.py test events` | 14 tests, OK (9 from Chapter 11, 5 new) |
| Loopback requests | `/`, `/events/`, `/events/1/` 200 with navigation and titles; `/events/999/`, `/events/abc/` 404 |
| Seven deliberate template mistakes | Each produced the error the chapter documents |
| Filter rewritten with `mark_safe` and `+` | 4 tests failed as intended (3 escaping tests and the partial test) |
| Inclusion-tag challenge, separate copy | Failed first, then 15 tests OK |
| Line length in Python and templates | All lines at most 65 characters |

Not run: macOS, Linux, or WSL, and a browser session against the app.

## Decisions taken for this pull request

- The shared layout lives in a project `templates/` folder through
  `DIRS`, because accounts and registrations will need it too and it
  belongs to no single app.
- The filter labels titles (`Sample:`), so it handles untrusted text and
  escaping matters. No date field is added to the sample data.
- Jinja2 is not used.
- The detail page test now checks the labelled heading as HTML. The
  visible text, "Sample: Python meetup", is unchanged.
- The filter is tested through a template that loads it, the same way
  pages use it, rather than by importing the function.

## Pull request description

> **Chapter 12: shared layout, navigation, row partial, sample label**
>
> Based on `chapters-06-11-baseline` (the Chapter 11 code). Tests were written first
> (commit 1 fails for the expected reasons); commit 2 makes all 14 pass.
>
> - `templates/base.html` with `title` and `content` blocks, found
>   through `TEMPLATES['DIRS']`
> - `templates/includes/site_nav.html`, included by the layout
> - home, list, and detail extend the layout; home uses `render()`
> - `event-row` inline partial, rendered alone in a test
> - `sample_label` filter built on `format_html`, with escaping tests
>
> No new dependency, model, or migration. Review against
> `docs/STANDARDS.md`: 65-character lines, chapter order, escaping.

## Day 1 comment draft (for the hackathon discussion)

> **My project**
>
> Otahque, the Django codebase of a beginner-first book I am writing
> (draft at https://otahque.tech). Otahque helps volunteer-led
> communities run recurring events. The book builds it one chapter at a
> time, and the opening chapters are done. During this hackathon I plan
> to finish it, with every chapter's code going through a pull request
> and a Qodo review before it reaches the book.
>
> Who it helps: people learning Django from zero, and community
> organizers who need a simple event site.
>
> Today's capability: Chapter 12. One shared layout and navigation for
> every page, a reusable event row partial, and a tested filter that
> labels sample events while keeping titles escaped.
>
> **My first delivery**
>
> Repository: (link)
> Pull request: (link)
> Screenshot: (list page with navigation)
> Lesson from the review: (to fill in after the Qodo review)
