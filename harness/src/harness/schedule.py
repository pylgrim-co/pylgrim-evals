"""Randomized, rep-blocked run schedule generation.

The full study schedule is generated once, up front, and frozen into the
queue database. Randomization is blocked by rep index: every rep-1 run across
all (task, arm, model) cells gets contiguous order_keys (shuffled within the
block), then every rep-2 run, and so on. A subscription-bounded study that
gets truncated partway through is therefore still balanced across cells.

Deterministic: the same seed always produces the identical schedule.
"""

from __future__ import annotations

import hashlib
from typing import Any

import random


def run_id_for(task_id: str, arm: str, model: str, rep: int) -> str:
    return f"{task_id}--{arm}--{model}--r{rep}"


def _run_seed(master_seed: int, run_id: str) -> int:
    """Stable per-run seed derived from the master seed and run id."""
    digest = hashlib.sha256(f"{master_seed}:{run_id}".encode()).hexdigest()
    return int(digest[:8], 16)


def generate(
    tasks: list[dict[str, str]],
    arms: list[str],
    models: list[str],
    reps: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Build the full schedule as queue-insertable row dicts.

    tasks: list of {"task_id": ..., "repo": ...} mappings.
    Returns rows with run_id, repo, task_id, arm, model, rep, seed, order_key.
    """
    rng = random.Random(seed)
    cells = [
        (task["task_id"], task["repo"], arm, model)
        for task in tasks
        for arm in arms
        for model in models
    ]
    rows: list[dict[str, Any]] = []
    order_key = 0
    for rep in range(1, reps + 1):
        block = list(cells)
        rng.shuffle(block)
        for task_id, repo, arm, model in block:
            rid = run_id_for(task_id, arm, model, rep)
            rows.append(
                {
                    "run_id": rid,
                    "repo": repo,
                    "task_id": task_id,
                    "arm": arm,
                    "model": model,
                    "rep": rep,
                    "seed": _run_seed(seed, rid),
                    "order_key": order_key,
                }
            )
            order_key += 1
    return rows
