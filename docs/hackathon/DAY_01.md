# Day 1: first delivery, 2 November 2026

Capability: Chapter 12 of the book. Every page shares one layout and
navigation, the event list row is a reusable partial, and a tested
`sample_label` filter marks fictional titles without giving up escaping.

Branch: `day-01-ch12-layout`, based on `chapters-06-11-baseline` (the
Chapter 11 code, written before the hackathon). That branch was
squash-merged into `main` as #1, and `main` was then merged into this
branch, so this pull request shows only the Chapter 12 changes.

Pull request: <https://github.com/pydata-indore/otahque/pull/2>

## Commits

1. `b227321` Failing tests for the layout, navigation, row partial, and
   filter.
2. `ebeef34` The implementation.
3. `fc21e28` This log.
4. `61a31ca` Merge of `main` after #1. The five conflicting files took
   this branch's version; no code changed.

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
| After the merge commit | `check` no issues; 14 tests, OK |
| Browser (headless Chromium, Playwright) | `/`, `/events/`, `/events/1/` render with navigation; screenshot below |

Not run: macOS, Linux, or WSL.

![The sample events list with Home and Events links above the heading
and the row "Sample: Python meetup"](screenshots/day-01-list.png)

The pages have no styling yet; Chapter 12 adds none.

## Qodo review

[Code review](https://github.com/pydata-indore/otahque/pull/2#issuecomment-6583563246):
0 bugs, 0 rule violations, 0 requirement gaps. The
[summary](https://github.com/pydata-indore/otahque/pull/2#issuecomment-6583554709)
judged the project-level layout, the inline row partial, and
`format_html` for untrusted titles to be the right choices. Details in
[the review note](../reviews/qodo/day-01-ch12-layout.md).

The Chapter 6 to 11 code reviewed in
[#1](https://github.com/pydata-indore/otahque/pull/1) also had no
findings
([review note](../reviews/qodo/chapters-06-11-baseline.md)).

This log's review results, links, and screenshot were recorded after
#2 was reviewed, so they arrive with the Day 2 branch.

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

## Pull request description (as posted)

> **Chapter 12: shared layout, navigation, row partial, sample label**
>
> Day 1 of the Qodo Hackathon 2026. Adds the Chapter 12 code of the
> Otahque book on top of the Chapter 11 code merged in #1.
>
> Tests were written first: commit `b227321` adds 5 tests that fail for
> the expected reasons (7 failures and 3 errors across the 14 tests).
> Commit `ebeef34` makes all 14 pass. The merge commit brings in `main`
> after #1 was squash-merged and changes no code.
>
> - `templates/base.html` with `title` and `content` blocks, found
>   through `TEMPLATES['DIRS']`
> - `templates/includes/site_nav.html`, included by the layout
> - Home, list, and detail pages extend the layout; home uses `render()`
> - `event-row` inline partial, rendered on its own in a test
> - `sample_label` filter built on `format_html`, with escaping tests
> - Day 1 log (`docs/hackathon/DAY_01.md`) and an empty review note
>
> No new dependency, model, or migration.
>
> Checked locally on Windows (uv 0.13.5, Python 3.14.9, Django 6.1.2):
> `manage.py check` finds no issues and `manage.py test events` runs
> 14 tests OK. Not run: macOS, Linux, or WSL, and a browser session.
>
> Please review against `docs/STANDARDS.md`: 65-character lines,
> chapter order, and escaping.

## Day 1 comment draft (for the hackathon discussion)

Posted in the event's template. Attach the screenshot as an image.

## My project

What I plan to build: Otahque, the Django codebase of a
beginner-first book I am writing (draft at https://otahque.tech).
Otahque helps volunteer-led communities run recurring events. The book
builds it one chapter at a time, and the opening chapters are done.
During this hackathon I plan to finish it, with every chapter's code
going through a pull request and a Qodo review before it reaches the
book.

Who it will help: people learning Django from zero, and community
organizers who need a simple event site.

One small capability I'll work on today: Chapter 12. One shared layout
and navigation for every page, a reusable event row partial, and a
tested filter that labels sample events while keeping titles escaped.

## My first delivery

Repository or PR link: https://github.com/pydata-indore/otahque/pull/2
(repository: https://github.com/pydata-indore/otahque)

Screenshot or short demo: the sample events list with the shared
navigation (`docs/hackathon/screenshots/day-01-list.png`).

One lesson or decision from the Qodo review: Qodo found no issues,
here or in the Chapter 6 to 11 code reviewed before it. That fits: the
code had already been through several rounds of review while the
chapters were written, and it was test-first. The review's value today
was an independent check of the design: it agreed the layout belongs
at project level, the row partial can stay inline, and `format_html`
is right for untrusted titles. Reviews should find more as the code
grows past what the book has already checked.
