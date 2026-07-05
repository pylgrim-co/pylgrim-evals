"""pylgrim evaluation harness.

Runs controlled experiments on AI coding agents. One run is one
(repo, task, arm, model, rep) cell: a headless Claude Code (`claude -p`)
invocation on a pinned checkout of a public repo. Drift, rule violations,
and token waste are measured deterministically from the resulting git diff
and session transcript.

All runs are subscription-bounded (founder's Claude Max plan, zero API
budget), so the harness is built around a crash-safe resumable SQLite queue:
batches trickle over weeks, and any process death or rate limit resumes with
zero lost state.
"""

__version__ = "0.1.0"
