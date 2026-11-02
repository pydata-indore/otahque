# Version baseline

Decided by the author on 23 October 2026: teach on the Django 6.1
series now, then upgrade to 6.2 LTS after its release as its own
verified checkpoint.

| Tool | Version | Where it is pinned |
|---|---|---|
| uv | 0.13.5 | Stated in README and the book |
| Python | 3.14.9 (regular CPython build) | `.python-version`, `pyproject.toml` |
| Django | 6.1.2 | `pyproject.toml`, `uv.lock` |
| python-decouple | 3.8 | `pyproject.toml`, `uv.lock` |

Sources checked when the pins were chosen:
<https://www.djangoproject.com/download/>,
<https://docs.djangoproject.com/en/6.1/faq/install/>, and
<https://www.python.org/downloads/release/python-3149/>.

No other upgrade happens without the author's decision. Dependency
update suggestions from bots or reviewers are recorded and deferred,
not merged.
