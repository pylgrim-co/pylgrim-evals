"""drain2: continuous claiming, heartbeat pump, heartbeat-based startup
reclaim, rate-limit gate, and the worker partition — with claude mocked."""

import threading
import time

from harness import drain2, queue
from harness.headless import RateLimited
from harness.taskcards import TaskCard


def make_task(task_id="alpha-t01"):
    return TaskCard(
        id=task_id,
        kind="real",
        title="t",
        base_sha="a" * 40,
        prompt="Fix the bug.",
        constraints=[],
        criteria=["It works."],
        scope_paths=["src/*"],
        out_of_scope=[],
    )


REPOS_CFG = {
    "alpha": {"url": "https://example.invalid/alpha.git", "preserve": ["node_modules"]},
    "beta": {"url": "https://example.invalid/beta.git"},
}


def seed_db(tmp_path, runs):
    """runs: list of (run_id, repo, task_id) tuples, order_key by position."""
    db_path = tmp_path / "runs.db"
    conn = queue.connect(db_path)
    queue.init_db(conn)
    queue.insert_schedule(
        conn,
        [
            {
                "run_id": rid, "repo": repo, "task_id": tid, "arm": "vanilla",
                "model": "sonnet", "rep": 1, "seed": 1, "order_key": i,
            }
            for i, (rid, repo, tid) in enumerate(runs)
        ],
    )
    return db_path, conn


def ok_execute(calls=None):
    def execute(row, task, url, results_dir, slot, preserve=(), timeout_s=0):
        if calls is not None:
            calls.append({"run_id": row["run_id"], "slot": slot, "url": url,
                          "timeout_s": timeout_s})
        return {"run": {"session_id": "sess", "transcript_path": None}}
    return execute


def cards_for(*task_ids):
    return {tid: make_task(tid) for tid in task_ids}


# --- continuous claim ---------------------------------------------------------

def test_run_drain_drains_queue_to_done(tmp_path):
    db_path, conn = seed_db(
        tmp_path,
        [
            ("alpha-t01--vanilla--sonnet--r1", "alpha", "alpha-t01"),
            ("alpha-t01--vanilla--sonnet--r2", "alpha", "alpha-t01"),
            ("beta-t01--vanilla--sonnet--r1", "beta", "beta-t01"),
        ],
    )
    calls = []
    totals = drain2.run_drain(
        db_path, tmp_path, cards_for("alpha-t01", "beta-t01"), REPOS_CFG,
        workers=1, timeout_s=123, heartbeat_s=60,
        execute=ok_execute(calls), echo=lambda _msg: None,
    )
    assert totals["done"] == 3 and totals["error"] == 0
    assert totals["resume_after"] is None
    assert all(c["timeout_s"] == 123 for c in calls)
    statuses = [r["status"] for r in conn.execute("SELECT status FROM runs")]
    assert statuses == ["done", "done", "done"]


def test_run_drain_marks_error_and_continues(tmp_path):
    db_path, conn = seed_db(
        tmp_path,
        [
            ("alpha-t01--vanilla--sonnet--r1", "alpha", "alpha-t01"),
            ("alpha-t01--vanilla--sonnet--r2", "alpha", "alpha-t01"),
        ],
    )
    fails = {"alpha-t01--vanilla--sonnet--r1"}

    def execute(row, task, url, results_dir, slot, preserve=(), timeout_s=0):
        if row["run_id"] in fails:
            raise RuntimeError("workspace exploded")
        return {"run": {"session_id": "sess"}}

    totals = drain2.run_drain(
        db_path, tmp_path, cards_for("alpha-t01"), REPOS_CFG,
        execute=execute, echo=lambda _msg: None,
    )
    assert totals["done"] == 1 and totals["error"] == 1
    row = conn.execute(
        "SELECT * FROM runs WHERE run_id = 'alpha-t01--vanilla--sonnet--r1'"
    ).fetchone()
    assert row["status"] == "error" and "exploded" in row["error"]


def test_run_drain_skips_missing_card(tmp_path):
    db_path, conn = seed_db(
        tmp_path, [("ghost-t01--vanilla--sonnet--r1", "alpha", "ghost-t01")]
    )
    totals = drain2.run_drain(
        db_path, tmp_path, {}, REPOS_CFG,
        execute=ok_execute(), echo=lambda _msg: None,
    )
    assert totals["skipped"] == 1
    assert conn.execute("SELECT status FROM runs").fetchone()["status"] == "skipped"


# --- rate-limit gate ----------------------------------------------------------

def test_rate_limit_gates_cleanly_with_resume_after(tmp_path):
    db_path, conn = seed_db(
        tmp_path,
        [
            ("alpha-t01--vanilla--sonnet--r1", "alpha", "alpha-t01"),
            ("alpha-t01--vanilla--sonnet--r2", "alpha", "alpha-t01"),
        ],
    )

    def execute(row, task, url, results_dir, slot, preserve=(), timeout_s=0):
        raise RateLimited("cap hit", resume_after="2999-01-01T00:00:00+00:00")

    totals = drain2.run_drain(
        db_path, tmp_path, cards_for("alpha-t01"), REPOS_CFG,
        execute=execute, echo=lambda _msg: None,
    )
    # clean exit: nothing done, nothing errored, the gate is reported
    assert totals["done"] == 0 and totals["error"] == 0
    assert totals["resume_after"] == "2999-01-01T00:00:00+00:00"
    first = conn.execute(
        "SELECT * FROM runs WHERE run_id = 'alpha-t01--vanilla--sonnet--r1'"
    ).fetchone()
    assert first["status"] == "pending"  # returned, attempt unconsumed
    assert first["attempt"] == 0
    assert first["resume_after"] == "2999-01-01T00:00:00+00:00"
    # the sibling run was never claimed after the gate closed
    second = conn.execute(
        "SELECT * FROM runs WHERE run_id = 'alpha-t01--vanilla--sonnet--r2'"
    ).fetchone()
    assert second["status"] == "pending" and second["attempt"] == 0


# --- heartbeat + reclaim ------------------------------------------------------

def test_startup_reclaims_only_stale_claims(tmp_path):
    """A dead process's cold claim is reclaimed and executed; a live
    sibling's fresh claim is left running (never the all-or-nothing reset)."""
    db_path, conn = seed_db(
        tmp_path,
        [
            ("alpha-t01--vanilla--sonnet--r1", "alpha", "alpha-t01"),
            ("alpha-t01--vanilla--sonnet--r2", "alpha", "alpha-t01"),
        ],
    )
    stale = queue.claim_next(conn, now="2020-01-01T00:00:00+00:00")
    fresh = queue.claim_next(conn)  # heartbeat = now: a live sibling's claim
    assert stale and fresh

    totals = drain2.run_drain(
        db_path, tmp_path, cards_for("alpha-t01"), REPOS_CFG,
        stale_after_s=600, execute=ok_execute(), echo=lambda _msg: None,
    )
    assert totals["reclaimed"] == 1
    assert totals["done"] == 1  # the reclaimed row ran; the live claim did not
    stale_row = conn.execute(
        "SELECT * FROM runs WHERE run_id = ?", (stale["run_id"],)
    ).fetchone()
    assert stale_row["status"] == "done"
    fresh_row = conn.execute(
        "SELECT * FROM runs WHERE run_id = ?", (fresh["run_id"],)
    ).fetchone()
    assert fresh_row["status"] == "running"  # untouched


def test_heartbeat_pump_refreshes_claim_while_running(tmp_path):
    db_path, conn = seed_db(
        tmp_path, [("alpha-t01--vanilla--sonnet--r1", "alpha", "alpha-t01")]
    )
    row = queue.claim_next(conn, now="2020-01-01T00:00:00+00:00")
    with drain2.HeartbeatPump(db_path, row["run_id"], interval_s=0.02):
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            hb = conn.execute(
                "SELECT heartbeat_at FROM runs WHERE run_id = ?", (row["run_id"],)
            ).fetchone()["heartbeat_at"]
            if hb != "2020-01-01T00:00:00+00:00":
                break
            time.sleep(0.02)
    assert hb != "2020-01-01T00:00:00+00:00"  # refreshed while "executing"


def test_killed_claimers_claims_become_reclaimable(tmp_path):
    """Sleep/wake resilience, end to end at queue level: a claim whose owner
    stopped heartbeating crosses the threshold and any sibling reclaims it."""
    db_path, conn = seed_db(
        tmp_path, [("alpha-t01--vanilla--sonnet--r1", "alpha", "alpha-t01")]
    )
    queue.claim_next(conn, now="2026-08-01T00:00:00+00:00")
    # heartbeats stopped an hour ago; threshold is 10 minutes
    assert queue.reclaim_stale(conn, 600, now="2026-08-01T01:00:00+00:00") == 1
    assert queue.claim_next(conn) is not None  # a sibling picks it up


# --- worker partition ---------------------------------------------------------

def test_worker_repos_partition_disjoint_and_complete():
    repos = ["gamma", "alpha", "beta"]
    p0 = drain2.worker_repos(repos, 2, 0)
    p1 = drain2.worker_repos(repos, 2, 1)
    assert p0 == ["alpha", "gamma"] and p1 == ["beta"]
    assert set(p0) | set(p1) == set(repos) and not set(p0) & set(p1)
    assert drain2.worker_repos(repos, 1, 0) == sorted(repos)


def test_two_workers_drain_disjoint_partitions_with_offset_slots(tmp_path):
    db_path, conn = seed_db(
        tmp_path,
        [
            ("alpha-t01--vanilla--sonnet--r1", "alpha", "alpha-t01"),
            ("beta-t01--vanilla--sonnet--r1", "beta", "beta-t01"),
        ],
    )
    lock = threading.Lock()
    calls = []

    def execute(row, task, url, results_dir, slot, preserve=(), timeout_s=0):
        with lock:
            calls.append({"repo": row["repo"], "slot": slot})
        return {"run": {"session_id": "sess"}}

    totals = drain2.run_drain(
        db_path, tmp_path, cards_for("alpha-t01", "beta-t01"), REPOS_CFG,
        workers=2, slot_count=2, execute=execute, echo=lambda _msg: None,
    )
    assert totals["done"] == 2
    slots = {c["repo"]: c["slot"] for c in calls}
    # sorted repos striped: worker 0 owns alpha (slot 0), worker 1 owns beta,
    # offset by worker_index * slot_count (slot 2) — never a shared worktree
    assert slots == {"alpha": 0, "beta": 2}
