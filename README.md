# Otahque

Otahque is a Django application that helps volunteer-led communities run
recurring events: event pages, registration, event-day coordination,
attendance history, and sponsor reporting.

This repository is the codebase of the Otahque book I am writing: a
beginner-first Django book that builds this one project from requirements
to production, one chapter at a time. The draft book is published at
<https://otahque.tech>. The opening chapters are written; during the
[Qodo Hackathon 2026](https://hackathon.qodo.ai/) (2 November to
2 December 2026) I plan to keep building it here, with every change
going through a pull request and a Qodo review before it reaches the book.

## Where the code is now

| Stage | Chapters | State |
|---|---|---|
| Project, apps, settings, Git | 6 to 8 | Written before the hackathon; in review |
| URLs, views, templates | 9 to 11 | Written before the hackathon; in review |
| Template inheritance, includes, partials | 12 | Day 1 of the hackathon; chapter drafted |
| Static files, Tailwind, daisyUI | 13 to 14 | Planned |
| Models, users, migrations, ORM, admin | 15 to 23 | Planned |
| Forms, accounts, permissions, registration | 24 to 34 | Planned |

The full 75-chapter contents are on the book site. There are no event
models, accounts, stored data, or deployed server yet. Sample events are
fictional and held in memory.

`main` holds only this README and the working docs. All code arrives
through reviewed pull requests, one branch each.

### Work that existed before the hackathon

The code for Chapters 6 to 11 was written before the event. It comes in
unchanged, exactly as it stood on 1 November 2026, through its own pull
request from the branch `chapters-06-11-baseline`, so that it is
reviewed too. Everything after it was built during the hackathon and is
listed in [docs/hackathon/](docs/hackathon/).

## Run it

Once the code is merged, you need [uv](https://docs.astral.sh/uv/) 0.13.5. uv installs Python
3.14.9 and the locked Django 6.1.2 and python-decouple 3.8.

```
uv sync --locked
```

Create a `.env` file beside `manage.py`. [.env.example](.env.example)
lists the names. Generate your own secret key with Django's
`get_random_secret_key()`; Chapter 8, Step 3 of the book gives a command
that writes `.env` and refuses to overwrite an existing one. Never commit
`.env` or reuse another computer's key.

Then check and test:

```
uv run python manage.py check
uv run python manage.py test events
```

`uv run python manage.py runserver` serves the site on loopback only.
Leave migrations unapplied: the custom user model comes first, in its
planned chapter.

## How changes are made

- One small capability per pull request, tests written first.
- Every pull request is reviewed by Qodo. Each comment is accepted,
  rejected, or deferred, with the reason, in
  [docs/reviews/qodo/](docs/reviews/qodo/).
- Code rules are in [docs/STANDARDS.md](docs/STANDARDS.md). The main one:
  no line longer than 65 characters, so every file prints in the book
  as it is.
- Merged code becomes the book's code for that chapter. See
  [docs/BOOK_SYNC.md](docs/BOOK_SYNC.md).

## Licence

The code is under the [MIT licence](LICENSE). The book's text and
figures are not part of this repository and are not covered by it.
