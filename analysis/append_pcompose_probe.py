"""Append the P-compose probe schedule (144 runs) to results/runs.db.

The probe from docs/10-evaluation-plan.md section 9 ("P-compose probe" row):
EXPLORATORY, publicly labeled a probe, no preregistration. It compares the
deterministic export block against an LLM-composed packet on the same 48
short T-real cards W1.5/E10 used (preregistration/card-manifest-v1.txt),
vague prompts, Haiku:

  compose-vague@haiku   48 cards x reps 7-9 = 144 runs (this append).
                        A pre-run Haiku call reads the vague prompt + the
                        full .pylgrim ledger and composes the workspace
                        CLAUDE.md; the composed artifact is persisted per
                        run (composed-claude-md.md, compose-result.json,
                        compose-transcript.jsonl) for audit. Compose
                        failure = run error; no fallback to the export.

  export-vague@haiku    the comparator. NOT re-run: the probe reuses the
                        E10 cell (r1-r3, drained earlier) descriptively.
                        DISCLOSED CAVEAT: the comparator cells predate the
                        probe cells (temporal gap, possible CLI/model
                        drift), which is one reason the readout is
                        insight-grade only, never confirmatory.

Rep indices 7-9 are a fresh range: r1-r3 belong to Wave 1.5/E10 and r4-r6
to E13 Stage 2 (prereg-v5-tiercross). compose-vague is a new arm, so its
run_ids cannot collide regardless, but the fresh range keeps "probe rows
are new rows" mechanically checkable, the same discipline Stage 2 used.

The mechanism is the house append motion (Wave 1.5 / E8 / E9 / E10 / E13):
schedule.generate's rep-blocked shuffle reproduced with frozen rep indices,
inserted with order_key_start strictly past every existing row. Master
seed 42 (house constant); per-run seeds via sha256("42:" + run_id).

Usage (from harness/):  uv run python ../analysis/append_pcompose_probe.py
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

SEED = 42  # house constant; per-run seeds are fresh via new r7-r9 run ids
REPS = (7, 8, 9)  # fresh range: r1-r3 = W1.5/E10, r4-r6 = E13 Stage 2

# The probe's single new cell; export-vague@haiku r1-r3 is the comparator
# and already exists (see module docstring for the temporal-gap caveat).
CELLS: list[tuple[str, str]] = [
    ("compose-vague", "haiku"),
]

EXPECTED_ROWS = 144  # 1 cell x 48 cards x 3 reps


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

    # generate()'s structure verbatim, with frozen rep indices 7-9:
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
        f"appended {len(rows)} P-compose probe runs to {DB}: "
        f"order keys {order_key_start}-{order_key - 1}, reps {REPS[0]}-{REPS[-1]}, seed {SEED}"
    )
    for arm, model in CELLS:
        n = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE arm=? AND model=? AND rep>=7", (arm, model)
        ).fetchone()[0]
        print(f"  {arm}@{model}: {n}")


if __name__ == "__main__":
    main()
