"""Append the E13 Stage-2 schedule (720 runs) to results/runs.db.

Executed strictly per preregistration/prereg-v5-tiercross.md (frozen, tag
prereg-v5-tiercross) and ONLY after that document is committed, tagged and
pushed to the public origin. Freeze-before-run.

The mechanism is the house append motion (Wave 1.5 / E8 / E9 / E10):
schedule.generate's rep-blocked shuffle inserted with order_key_start
strictly past every existing row. generate() itself cannot express this
block — the five (arm, model) cells are not a full arms × models product
(vanilla-vague@haiku is deliberately absent) and the rep indices must be
4-6 (run_id is the queue's primary key; cells 1-3 already hold r1-r3 from
Wave 1.5/E10, and r4-r6 is what makes "fresh data only" mechanically
checkable) — so this script reproduces generate()'s exact structure
(same rng discipline, same run_id/seed derivations, same insert path)
with those two frozen parameters.

Deterministic: master seed 42 (house constant); per-run seeds via the
house derivation sha256("42:" + run_id) — fresh for every Stage-2 run
because every Stage-2 run_id is new.

Usage (from harness/):  uv run python ../analysis/append_e13_stage2.py
"""

from __future__ import annotations

import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness" / "src"))

from harness import queue, schedule  # noqa: E402

DB = ROOT / "results" / "runs.db"

SEED = 42  # house constant; per-run seeds are fresh via new r4-r6 run ids
REPS = (4, 5, 6)  # Stage-2 rep indices (frozen; see prereg-v5-tiercross)

# The five Stage-2 cells, in the prereg's table order.
CELLS: list[tuple[str, str]] = [
    ("export-vague", "haiku"),
    ("vanilla-vague", "sonnet"),
    ("export-vague", "sonnet"),
    ("vanilla-vague", "opus"),
    ("export-vague", "opus"),
]

EXPECTED_ROWS = 720  # 5 cells x 48 cards x 3 reps


def main() -> None:
    conn = queue.connect(DB)

    # Guard: never mutate the queue under a live worker.
    running = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE status = 'running'"
    ).fetchone()[0]
    if running:
        sys.exit(f"abort: {running} run(s) currently 'running'; no appends under a live worker")

    # The frozen 48-card list: derived from the queue itself (the E10
    # export-vague@haiku cell), the same corpus every wave has used.
    tasks = [
        {"task_id": r["task_id"], "repo": r["repo"]}
        for r in conn.execute(
            "SELECT DISTINCT task_id, repo FROM runs"
            " WHERE arm='export-vague' AND model='haiku' ORDER BY task_id"
        )
    ]
    if len(tasks) != 48:
        sys.exit(f"abort: expected 48 cards, found {len(tasks)}")

    max_key = conn.execute("SELECT MAX(order_key) FROM runs").fetchone()[0]
    order_key_start = max_key + 1  # strictly after ALL existing rows

    existing_ids = {r["run_id"] for r in conn.execute("SELECT run_id FROM runs")}

    # generate()'s structure verbatim, with frozen rep indices 4-6:
    # cells nested task-major, one shuffle per rep block, sequential keys.
    rng = random.Random(SEED)
    cells = [
        (task["task_id"], task["repo"], arm, model)
        for task in tasks
        for arm, model in CELLS
    ]
    rows = []
    order_key = order_key_start
    for rep in REPS:
        block = list(cells)
        rng.shuffle(block)
        for task_id, repo, arm, model in block:
            rid = schedule.run_id_for(task_id, arm, model, rep)
            if rid in existing_ids:
                sys.exit(f"abort: run_id collision with existing row: {rid}")
            rows.append(
                {
                    "run_id": rid,
                    "repo": repo,
                    "task_id": task_id,
                    "arm": arm,
                    "model": model,
                    "rep": rep,
                    "seed": schedule._run_seed(SEED, rid),
                    "order_key": order_key,
                }
            )
            order_key += 1

    if len(rows) != EXPECTED_ROWS:
        sys.exit(f"abort: built {len(rows)} rows, expected {EXPECTED_ROWS}")
    if len({r["run_id"] for r in rows}) != EXPECTED_ROWS:
        sys.exit("abort: duplicate run_ids inside the new block")

    queue.insert_schedule(conn, rows)

    print(
        f"appended {len(rows)} E13 Stage-2 runs to {DB}: "
        f"order keys {order_key_start}-{order_key - 1}, reps {REPS[0]}-{REPS[-1]}, seed {SEED}"
    )
    for arm, model in CELLS:
        n = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE arm=? AND model=? AND rep>=4", (arm, model)
        ).fetchone()[0]
        print(f"  {arm}@{model}: {n}")


if __name__ == "__main__":
    main()
