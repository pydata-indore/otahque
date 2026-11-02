# Instructions for coding agents and reviewers

This is the codebase of the Otahque Django book. Code here is printed in
the book, so the reader must be able to follow every change.

Read before changing anything:

- [docs/STANDARDS.md](docs/STANDARDS.md): the rules every change follows,
  including the 65-character line limit and tests first.
- [docs/VERSION_BASELINE.md](docs/VERSION_BASELINE.md): pinned versions;
  do not add or upgrade dependencies.
- [docs/BOOK_SYNC.md](docs/BOOK_SYNC.md): how merged code becomes book
  content.
- The "Where the code is now" table in [README.md](README.md): where the
  project stands.

Work one planned capability at a time, on a branch, through a pull
request. Run `uv run python manage.py check` and
`uv run python manage.py test events` before opening it, and report the
commands actually run. Do not use anything a later chapter introduces.
Do not commit `.env`, a database file, or `.venv/`. Commit messages are
plain, with no tool or AI attribution.
