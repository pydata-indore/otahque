# The book behind this code

This repository is the code of the Otahque Django book, one chapter
at a time. Reviewers and agents use this page to judge a change
against its chapter: what that chapter teaches, what earlier
chapters already print, and which later chapter fills a gap.

- The published book: https://otahque.tech. Chapters 6 to 35 are
  online; each page prints the files that chapter changes.
- The chapter a pull request belongs to is in its title
  ("Chapter 23: ...") and its ticket.
- A gap that a later chapter fills is not a defect of this pull
  request (AGENTS.md, rule 7). Find the chapter below or in
  "Where later work lands" in docs/STANDARDS.md. A later chapter
  covers a gap only when the book or this repository names it for
  that topic: its title, its row in that table, or a published
  chapter that hands the topic to it (Chapter 21 hands SQLite's
  `LOWER()` limit to Chapter 32).
- A bug in code this change adds (a wrong result, a crash, lost
  or corrupted data) is a finding now, whatever later chapter
  improves that area. So are security defects, failing tests,
  and lines over 65 characters.
- Code that uses something before its chapter, or changes code
  an earlier chapter prints, is a finding (rules 4 and 7).

| Chapter | Title | Book page |
|---|---|---|
| 6 | Creating the project and understanding its files | https://otahque.tech/chapters/chapter06/ |
| 7 | Django apps and application boundaries | https://otahque.tech/chapters/chapter07/ |
| 8 | Settings, environments, dependencies, and Git | https://otahque.tech/chapters/chapter08/ |
| 9 | URLs and routing | https://otahque.tech/chapters/chapter09/ |
| 10 | Function-based views and request/response objects | https://otahque.tech/chapters/chapter10/ |
| 11 | Templates, context, and escaping | https://otahque.tech/chapters/chapter11/ |
| 12 | Template inheritance, includes, and partials | https://otahque.tech/chapters/chapter12/ |
| 13 | Static files and CSS fundamentals | https://otahque.tech/chapters/chapter13/ |
| 14 | Tailwind, daisyUI, and Otahque’s design system | https://otahque.tech/chapters/chapter14/ |
| 15 | Relational databases and our first ERD | https://otahque.tech/chapters/chapter15/ |
| 16 | Django models and field choices | https://otahque.tech/chapters/chapter16/ |
| 17 | Choosing and creating our user model | https://otahque.tech/chapters/chapter17/ |
| 18 | Migrations and schema evolution | https://otahque.tech/chapters/chapter18/ |
| 19 | ORM fundamentals | https://otahque.tech/chapters/chapter19/ |
| 20 | Relationships between models | https://otahque.tech/chapters/chapter20/ |
| 21 | Validation, constraints, and data integrity | https://otahque.tech/chapters/chapter21/ |
| 22 | QuerySets, managers, and query composition | https://otahque.tech/chapters/chapter22/ |
| 23 | Django admin fundamentals | https://otahque.tech/chapters/chapter23/ |
| 24 | Django forms | https://otahque.tech/chapters/chapter24/ |
| 25 | Editing an event, and the validation lifecycle | https://otahque.tech/chapters/chapter25/ |
| 26 | Publishing, cancelling, and deleting an event | https://otahque.tech/chapters/chapter26/ |
| 27 | Authentication and account workflows | https://otahque.tech/chapters/chapter27/ |
| 28 | Sessions, cookies, and time zones | https://otahque.tech/chapters/chapter28/ |
| 29 | Account security: passwords, sign-in codes, and two factors | https://otahque.tech/chapters/chapter29/ |
| 30 | Permissions, ownership, and roles | https://otahque.tech/chapters/chapter30/ |
| 31 | Event registration and cancellation | https://otahque.tech/chapters/chapter31/ |
| 32 | Moving to PostgreSQL | https://otahque.tech/chapters/chapter32/ |
| 33 | Transactions, concurrency, and the last available seat | https://otahque.tech/chapters/chapter33/ |
| 34 | Testing fundamentals and first-release acceptance | https://otahque.tech/chapters/chapter34/ |
| 35 | Class-based views and dispatch | https://otahque.tech/chapters/chapter35/ |
| 36 | Generic display views and pagination | Planned |
| 37 | Generic editing views and access mixins | Planned |
| 38 | Advanced admin and formsets | Planned |
| 39 | Middleware and context processors | Planned |
| 40 | Signals, application lifecycle, and system checks | Planned |
| 41 | Management commands and data import/export | Planned |
| 42 | File uploads and storage | Planned |
| 43 | Email delivery and templates | Planned |
| 44 | Background tasks, scheduling, and retries | Planned |
| 45 | HTMX and progressive enhancement | Planned |
| 46 | Waitlists, check-in, and registration state transitions | Planned |
| 47 | API design and HTTP contracts | Planned |
| 48 | DRF serializers and validation | Planned |
| 49 | API views, generic views, viewsets, and routers | Planned |
| 50 | API authentication and permissions | Planned |
| 51 | Filtering, pagination, throttling, and API documentation | Planned |
| 52 | Webhooks and reliable external integrations | Planned |
| 53 | Async Django, ASGI, and sync/async boundaries | Planned |
| 54 | Channels and real-time updates | Planned |
| 55 | Advanced ORM and database expressions | Planned |
| 56 | Search, indexes, and query plans | Planned |
| 57 | Caching and application performance | Planned |
| 58 | Advanced testing and failure scenarios | Planned |
| 59 | Security review, threat modelling, and hardening | Planned |
| 60 | Preventing web and API attacks | Planned |
| 61 | Accessibility, localization, timezones, and discoverability | Planned |
| 62 | Production architecture and Docker | Planned |
| 63 | Deployment, static/media delivery, and HTTPS | Planned |
| 64 | CI/CD, safe migrations, and rollback | Planned |
| 65 | Logging, monitoring, backups, and recovery | Planned |
| 66 | Load testing, capacity planning, and scaling decisions | Planned |
| 67 | Multi-community requirements and tenancy alternatives | Planned |
| 68 | Implementing and testing tenant isolation | Planned |
| 69 | Billing, subscriptions, and entitlements | Planned |
| 70 | Volunteer management and organizer planning | Planned |
| 71 | Teams, hackathon submissions, and judging | Planned |
| 72 | Job board, reusable content, and moderation | Planned |
| 73 | Adding an AI feature safely | Planned |
| 74 | AI guardrails and adversarial testing | Planned |
| 75 | Final product review, UI refinement, upgrades, and maintenance | Planned |
