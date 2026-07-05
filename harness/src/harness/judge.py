"""LLM-judge scoring (stub, reserved for a later wave).

Deterministic metrics (scope, violations, tokens, tests) carry the headline
results. A judge pass may later grade softer qualities (solution approach,
criteria satisfaction where tests are weak) from the diff and transcript.

Reserved design decisions, so nothing downstream has to change later:
  - Judge scoring is itself a queued unit of work: judge rows will live in
    the same runs.db (a `judge_runs` table keyed by run_id + judge model +
    judge rep) so they inherit the same crash-safe resume semantics.
  - Judge inputs are exactly the stored artifacts under results/runs/<run_id>/
    (diff.patch, transcript, result.json), never a live workspace.
"""

from __future__ import annotations

from typing import Any


def score_run(run_id: str, results_dir: Any = None) -> dict[str, Any]:
    """Grade one completed run's artifacts with an LLM judge. Not implemented."""
    raise NotImplementedError("judge scoring is a later wave; see module docstring")


def enqueue_judge_runs(conn: Any, judge_model: str, reps: int = 1) -> int:
    """Insert judge work items for all done runs. Not implemented."""
    raise NotImplementedError("judge scoring is a later wave; see module docstring")
