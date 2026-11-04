# Day 3: static files and a design system, 4 November 2026

Capability: Chapters 13 and 14 of the book. Chapter 13 serves one
project stylesheet through Django's static files and gives the pages
their first styling. Chapter 14 builds that stylesheet with Tailwind CSS
and daisyUI from pinned Node.js tools, with a small Otahque theme.

Branch: `day-03-ch13-14-static-tailwind`, from `main` after #2 was
rebase-merged. Both chapters come in one pull request at the author's
request. This departs from "one capability per pull request" in
`docs/STANDARDS.md`, so each chapter keeps its own test-first pair of
commits. Day 2 had no delivery.

## Commits

1. `132d985` Day 1 review results, links, and screenshot (held back
   from #2, as its log says).
2. `6901952` Chapter 13: failing tests for the stylesheet finder and
   link.
3. `8ab6c73` Chapter 13: `STATICFILES_DIRS`, the linked `site.css`, and
   semantic classes in the templates.
4. `9cc8362` Chapter 14: failing tests for the `navbar` class and its
   compiled rule.
5. `d74e98f` Chapter 14: the npm files, `source.css` with the theme, the
   compiled `site.css`, and utility and component classes in the
   templates.
6. This log, the README, and the version baseline.

The book's Chapters 13 and 14 were written from this code and print
these files exactly. Each code file matches the book's verified
checkpoint, ignoring line endings.

## Verified locally (Windows, uv 0.13.5, Python 3.14.9, Django 6.1.2, Node.js 26.13.0, npm 11.20.0)

| Check | Result |
|---|---|
| Chapter 12 starting point (`main`) | 14 tests, OK |
| Chapter 13 tests before the code | 16 run; 4 failures, each for the expected reason |
| After Chapter 13 | `check` no issues; 16 tests, OK; `findstatic` finds `site.css` |
| Chapter 14 tests before the code | 18 run; 2 failures: no `navbar` class, no `.navbar` rule |
| `npm ci`, then `npm run build` | 0 vulnerabilities; output byte-identical to the book's `site.css` |
| After Chapter 14 | `check` no issues; 18 tests, OK |
| Second build | `git diff --exit-code` on `site.css`: no change |
| `node_modules/` | Ignored; not committed |
| Line length | Python, templates, `source.css`, and `package.json` at most 65 characters |
| Loopback requests (headless Chromium) | `/`, `/events/`, `/events/1/`, and `site.css` 200; `/events/999/` 404; navy navigation applied |

The book's own check of the same code also covered both shells
(PowerShell 5.1 and Git Bash), keyboard focus, and widths from 320 to
1440 pixels. Not run: macOS, Linux, WSL, Firefox, and Safari.

![The sample events list styled with a navy navigation bar and a white
card holding "Sample: Python meetup"](screenshots/day-03-list.png)

## Decisions taken for this pull request

- Chapter 13 adds a project `static/` folder through
  `STATICFILES_DIRS`, because the stylesheet belongs to no single app.
- Chapter 14 pins Node.js, Tailwind CSS, and daisyUI exactly, at the
  author's decision of 3 November 2026. `docs/VERSION_BASELINE.md`
  records them.
- The compiled `site.css` is committed, so Django runs without Node.js.
  `npm ci` and `npm run build` reproduce it byte for byte.
- `allowScripts` denies the one install script, `@parcel/watcher`'s.
  Ready-made builds exist for Windows, macOS, and Linux.
- Cards use `border border-base-300` instead of daisyUI's `card-border`,
  which draws the border in the page background colour.
- Links stay underlined, because the link blue against body text is
  2.40:1, below the 3:1 that colour alone needs.
- `.gitignore` keeps GitHub's Python template and gains only the
  `node_modules/` lines.
