"""Continuous-claim drain for the coding queue (`harness drain2`).

Replaces the outer-loop shell drain for NEW studies; `harness run` and
scripts/coding-drain.sh are left untouched so past studies stay exactly
reproducible. One process, N claimer threads: each claims one run, executes
it, marks it, and claims the next until the queue is empty or a rate-limit
gate closes.

Why threads, not subprocesses:
  * The heavy work is the claude CLI child process; a claimer just blocks on
    it, so the GIL is irrelevant to throughput.
  * One OS process means one lifecycle: session exit, machine sleep, or a
    kill affects the whole drain at once. There are no backgrounded or
    detached trees to orphan — the failure classes that silently killed the
    E13/P-compose shell drains (session-exit killing backgrounded trees,
    sleep/wake killing detached trees, PowerShell Start-Process of git bash
    dying on spawn: a documented dead end).
  * A rate-limit gate in any claimer stops all siblings cleanly through a
    shared in-process Event; no pid files, no process groups.

Crash-safety is heartbeat-based. Every claim stamps runs.heartbeat_at and a
pump thread refreshes it every heartbeat_s while the run executes. A killed
or slept process simply stops heartbeating; on the next start, reclaim_stale
returns only rows whose heartbeat crossed the threshold to pending — never a
live sibling's claim (the all-or-nothing reset_stale hazard). A process
resumed after sleep just continues claiming; its stale-but-still-running
claim keeps heartbeating and is left alone.

Each claimer owns the same disjoint repo partition (and therefore disjoint
workspace slots) as `harness run --workers N --worker-index k`, so no two
claimers ever share a worktree.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

from harness import queue, runner
from harness.taskcards import TaskCard

DEFAULT_HEARTBEAT_S = 60


def worker_repos(all_repos: list[str], workers: int, index: int) -> list[str]:
    """Deterministic repo partition for parallel drains.

    Sorted repos striped by position (never hash(): Python string hashing is
    randomized per process). Partitions are disjoint and cover every repo;
    workers=1 returns everything, reproducing single-worker behavior.
    """
    return [r for i, r in enumerate(sorted(all_repos)) if i % workers == index]


class HeartbeatPump:
    """Background thread stamping a claim's heartbeat while its run executes.

    Owns its own SQLite connection (sqlite3 connections are per-thread).
    Context-managed so the pump never outlives its run's claim.
    """

    def __init__(self, db_path: Path | str, run_id: str, interval_s: float) -> None:
        self._db_path = db_path
        self._run_id = run_id
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, name=f"heartbeat-{run_id}", daemon=True
        )

    def _loop(self) -> None:
        conn = queue.connect(self._db_path)
        try:
            while not self._stop.wait(self._interval_s):
                queue.heartbeat(conn, self._run_id)
        finally:
            conn.close()

    def __enter__(self) -> "HeartbeatPump":
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._stop.set()
        self._thread.join(timeout=10)


def claimer_loop(
    db_path: Path | str,
    results_dir: Path | str,
    cards_by_id: dict[str, TaskCard],
    repos_cfg: dict[str, dict],
    worker_index: int,
    workers: int,
    slot_count: int,
    timeout_s: int,
    heartbeat_s: float,
    stop: threading.Event,
    execute: Callable[..., dict[str, Any]] = runner.execute_run,
    echo: Callable[[str], None] = print,
) -> dict[str, Any]:
    """One claimer: claim -> execute -> mark -> claim next, until exhausted.

    Exits when: no eligible pending run remains in its partition, the shared
    stop event is set (a sibling hit the rate-limit gate), or it hits the
    gate itself (marks the run pending with resume_after, sets stop).
    Returns per-claimer stats including any resume_after gate seen.
    """
    conn = queue.connect(db_path)
    results_dir = Path(results_dir)
    mine = worker_repos(sorted(repos_cfg), workers, worker_index)
    # Same repo-pinned, worker-offset slot mapping as `harness run`.
    repo_slots = {
        name: worker_index * slot_count + (i % slot_count)
        for i, name in enumerate(mine)
    }
    claim_repos = mine if workers > 1 else None

    stats: dict[str, Any] = {
        "done": 0, "error": 0, "skipped": 0, "resume_after": None,
    }
    while not stop.is_set():
        row = queue.claim_next(conn, repos=claim_repos)
        if row is None:
            break
        run_id = row["run_id"]
        task = cards_by_id.get(row["task_id"])
        repo_cfg = repos_cfg.get(row["repo"])
        if task is None or repo_cfg is None:
            queue.mark_skipped(conn, run_id, "task card or repo config missing")
            echo(f"{run_id}: skipped (missing task card or repo config)")
            stats["skipped"] += 1
            continue
        slot = repo_slots[row["repo"]]
        preserve = tuple(repo_cfg.get("preserve") or ("node_modules", ".venv", "target"))
        echo(f"{run_id}: running in slot {slot} (claimer {worker_index})")
        try:
            with HeartbeatPump(db_path, run_id, heartbeat_s):
                record = execute(
                    row,
                    task,
                    repo_cfg["url"],
                    results_dir,
                    slot,
                    preserve=preserve,
                    timeout_s=timeout_s,
                )
        except runner.RateLimited as exc:
            queue.mark_rate_limited(conn, run_id, exc.resume_after)
            stats["resume_after"] = exc.resume_after
            stop.set()  # siblings finish their current run, then exit
            echo(f"{run_id}: rate limited, resume after {exc.resume_after}; "
                 f"gating all claimers")
            break
        except Exception as exc:  # keep the loop crash-safe: record and continue
            queue.mark_error(conn, run_id, str(exc))
            echo(f"{run_id}: error: {exc}")
            stats["error"] += 1
            continue
        queue.mark_done(
            conn,
            run_id,
            session_id=record["run"].get("session_id"),
            transcript_path=record["run"].get("transcript_path"),
            workspace_slot=slot,
        )
        echo(f"{run_id}: done")
        stats["done"] += 1
    conn.close()
    return stats


def run_drain(
    db_path: Path | str,
    results_dir: Path | str,
    cards_by_id: dict[str, TaskCard],
    repos_cfg: dict[str, dict],
    workers: int = 1,
    slot_count: int = 2,
    timeout_s: int = runner.RUN_TIMEOUT_S,
    heartbeat_s: float = DEFAULT_HEARTBEAT_S,
    stale_after_s: int = queue.HEARTBEAT_STALE_S,
    execute: Callable[..., dict[str, Any]] = runner.execute_run,
    echo: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Reclaim stale claims, run N claimer threads to exhaustion, aggregate.

    Startup reclaims ONLY heartbeat-stale rows (threshold stale_after_s), so
    launching a second drain2 process next to a live one is safe: the live
    process's claims keep heartbeating and are never touched.
    """
    conn = queue.connect(db_path)
    queue.init_db(conn)
    reclaimed = queue.reclaim_stale(conn, stale_after_s)
    if reclaimed:
        echo(f"reclaimed {reclaimed} heartbeat-stale running row(s) to pending")

    stop = threading.Event()
    results: list[dict[str, Any]] = [{} for _ in range(workers)]

    def _target(k: int) -> None:
        results[k] = claimer_loop(
            db_path, results_dir, cards_by_id, repos_cfg,
            worker_index=k, workers=workers, slot_count=slot_count,
            timeout_s=timeout_s, heartbeat_s=heartbeat_s, stop=stop,
            execute=execute, echo=echo,
        )

    threads = [
        threading.Thread(target=_target, args=(k,), name=f"claimer-{k}")
        for k in range(workers)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    totals = {
        "reclaimed": reclaimed,
        "done": sum(r.get("done", 0) for r in results),
        "error": sum(r.get("error", 0) for r in results),
        "skipped": sum(r.get("skipped", 0) for r in results),
        "resume_after": min(
            (r["resume_after"] for r in results if r.get("resume_after")),
            default=None,
        ),
    }
    if totals["resume_after"] is None:
        gated = conn.execute(
            "SELECT MIN(resume_after) AS ra FROM runs "
            "WHERE status = 'pending' AND resume_after IS NOT NULL"
        ).fetchone()
        totals["resume_after"] = gated["ra"] if gated else None
    totals["summary"] = queue.status_summary(conn)
    conn.close()
    return totals
