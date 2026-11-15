# The agent workflow

Adding the label `ready-for-agent` to an issue starts
[`.github/workflows/agent.yml`](../.github/workflows/agent.yml),
which runs [`agent_runner.py`](agent_runner.py) on one ticket. It
can also be started by hand: Actions, Agent, Run workflow, with
the issue number.

## What the run does

1. Labels the issue `agent-working` and links the run.
2. Runs the checks on `main` first; a failing `main` stops it.
3. Tests first: the model may change only `events/tests*.py`.
   The script runs the tests and accepts them only if they fail.
4. Code: the model may change `events/` (not migrations),
   `templates/`, `README.md`, and `docs/`, but not the tests.
5. After every edit the script itself runs the checks:
   allowed paths, at most 65 characters per line,
   `manage.py check`, and `manage.py test events`.
   `makemigrations --check --dry-run` is recorded only.
6. A separate model call checks each acceptance criterion
   against the diff and the check output. Unmet criteria go
   back to the code step once.
7. One commit, a pushed branch, and a PR that closes the issue,
   with the failing-test output, the criteria table, and the
   checks.
8. It waits for Qodo's review, sorts each open finding into
   confirmed or dismissed, fixes the confirmed ones in a new
   commit, runs the checks, and posts `/agentic_review`.
9. A summary comment on the PR lists every verdict. A human
   reviews and merges.

## Limits and stopping

- Up to 3 attempts per step (`MAX_ATTEMPTS`).
- Up to 2 rounds of review fixes (`REVIEW_ROUNDS`).
- 20 minutes to wait for Qodo (`QODO_WAIT_MINUTES`), and
  90 minutes for the whole job.

When a limit is hit, the model answers `BLOCKED`, or Qodo does
not reply, the issue gets `agent-blocked` and a comment with the
reason. The run never force-pushes, never merges, and never
reuses an existing branch.

## Settings

Under Settings, Secrets and variables, Actions:

| Kind | Name | Use |
|---|---|---|
| Secret | `EURI_API_KEY` | Key for the model API |
| Variable | `EURI_MODEL` | Model name |
| Variable | `EURI_BASE_URL` | OpenAI-compatible base URL |
| Secret, optional | `AGENT_GH_TOKEN` | Token used instead of the workflow token |

Without `AGENT_GH_TOKEN`, PRs and comments come from
`github-actions[bot]`. The checks run without any token or key
in their environment, and the checkout keeps no credentials.
