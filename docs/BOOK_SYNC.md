# How code reaches the book

This repository is the source of truth for the Otahque code. The book
is written from it: chapter listings must match the files here.

## Direction

- **Code** flows from this repository to the book. After a pull request
  merges, its files are copied into the book's checkpoint folder and
  the book's listing check runs.
- **Checkpoint notes and verification records** stay in the book
  workspace. They are not kept in this repository.
- Files that exist only for this repository (this folder's hackathon
  logs and review notes, `LICENSE`, `AGENTS.md`, the top README) are not
  copied into the book.

## When a merge changes code a chapter already shows

If a review leads to a change in code that an existing chapter prints,
the book's listing check fails on purpose. The change is then logged as
a proposed revision of that chapter for the author's decision. Delivered
prose is never edited silently.

## When code comes before its chapter

For a chapter not yet written (Chapter 12 onward at the start of the
hackathon), the reviewed code is the endpoint the chapter is written
towards. Drafting the chapter may still find something to change; that
goes back through a pull request here first.

## Status words

Merged code is reviewed and tested, not approved book content. Chapter
approval is a separate decision by the author.
