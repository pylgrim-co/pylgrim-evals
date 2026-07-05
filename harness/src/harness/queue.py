"""Crash-safe resumable run queue backed by SQLite.

This is the load-bearing piece of the harness. Runs are subscription-bounded
(Claude Max plan, no API budget), so a study trickles out over weeks of small
batches. Every state transition is a single SQLite transaction: any process
death, rate limit, or reboot leaves the queue resumable with zero lost state.

Tables:
  runs  one row per (task, arm, model, rep) cell, keyed by run_id
  meta  key/value provenance (schedule_seed, created_at, versions)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    repo            TEXT NOT NULL,
    task_id         TEXT NOT NULL,
    arm             TEXT NOT NULL,
    model           TEXT NOT NULL,
    rep             INTEGER NOT NULL,
    seed            INTEGER NOT NULL,
    order_key       INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','done','error','skipped')),
    attempt         INTEGER NOT NULL DEFAULT 0,
    session_id      TEXT,
    transcript_path TEXT,
    workspace_slot  INTEGER,
    started_at      TEXT,
    finished_at     TEXT,
    error           TEXT,
    resume_after    TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string (the queue's canonical clock format)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open the queue database, creating parent dirs as needed."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection, meta: dict[str, str] | None = None) -> None:
    """Create tables and record provenance metadata."""
    with conn:
        conn.executescript(SCHEMA)
        for key, value in (meta or {}).items():
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, str(value))
            )


def run_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]


def insert_schedule(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    """Insert the full pre-randomized schedule. Rows come from schedule.generate()."""
    with conn:
        conn.executemany(
            """
            INSERT INTO runs (run_id, repo, task_id, arm, model, rep, seed, order_key)
            VALUES (:run_id, :repo, :task_id, :arm, :model, :rep, :seed, :order_key)
            """,
            rows,
        )


def claim_next(conn: sqlite3.Connection, now: str | None = None) -> dict[str, Any] | None:
    """Atomically claim the next eligible pending run.

    Eligible: status pending and (resume_after IS NULL OR resume_after <= now).
    Order: order_key, which the schedule generator assigned as rep-blocked
    random order, so a truncated study stays balanced across cells.

    Returns the claimed row as a dict, or None when nothing is eligible.
    """
    now = now or now_iso()
    with conn:
        # BEGIN IMMEDIATE-equivalent: the UPDATE takes the write lock, and the
        # claimed run_id is selected inside the same transaction.
        row = conn.execute(
            """
            SELECT run_id FROM runs
            WHERE status = 'pending'
              AND (resume_after IS NULL OR resume_after <= ?)
            ORDER BY order_key
            LIMIT 1
            """,
            (now,),
        ).fetchone()
        if row is None:
            return None
        run_id = row["run_id"]
        cur = conn.execute(
            """
            UPDATE runs
            SET status = 'running', attempt = attempt + 1,
                started_at = ?, resume_after = NULL, error = NULL
            WHERE run_id = ? AND status = 'pending'
            """,
            (now, run_id),
        )
        if cur.rowcount != 1:  # lost a race with another process
            return None
    claimed = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return dict(claimed)


def mark_done(
    conn: sqlite3.Connection,
    run_id: str,
    session_id: str | None = None,
    transcript_path: str | None = None,
    workspace_slot: int | None = None,
) -> None:
    with conn:
        conn.execute(
            """
            UPDATE runs
            SET status = 'done', finished_at = ?, session_id = COALESCE(?, session_id),
                transcript_path = COALESCE(?, transcript_path),
                workspace_slot = COALESCE(?, workspace_slot)
            WHERE run_id = ?
            """,
            (now_iso(), session_id, transcript_path, workspace_slot, run_id),
        )


def mark_error(conn: sqlite3.Connection, run_id: str, error: str) -> None:
    with conn:
        conn.execute(
            "UPDATE runs SET status = 'error', finished_at = ?, error = ? WHERE run_id = ?",
            (now_iso(), error[:4000], run_id),
        )


def mark_rate_limited(conn: sqlite3.Connection, run_id: str, resume_after: str) -> None:
    """Return a run to pending after a rate limit.

    The attempt is 'unconsumed': claim_next incremented attempt, so we
    decrement it back. resume_after gates the run until the limit resets.
    """
    with conn:
        conn.execute(
            """
            UPDATE runs
            SET status = 'pending', attempt = attempt - 1,
                started_at = NULL, resume_after = ?
            WHERE run_id = ?
            """,
            (resume_after, run_id),
        )


def mark_skipped(conn: sqlite3.Connection, run_id: str, reason: str) -> None:
    with conn:
        conn.execute(
            "UPDATE runs SET status = 'skipped', finished_at = ?, error = ? WHERE run_id = ?",
            (now_iso(), reason, run_id),
        )


def reset_stale(conn: sqlite3.Connection) -> int:
    """On startup, return any 'running' rows to 'pending' (a previous process died).

    The consumed attempt is kept: the crashed attempt really did burn quota.
    Returns the number of rows reset.
    """
    with conn:
        cur = conn.execute(
            "UPDATE runs SET status = 'pending', started_at = NULL WHERE status = 'running'"
        )
        return cur.rowcount


def status_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Counts by status, plus per-arm and per-rep done counts for a quick balance check."""
    by_status = {
        row["status"]: row["n"]
        for row in conn.execute("SELECT status, COUNT(*) AS n FROM runs GROUP BY status")
    }
    by_arm = {
        row["arm"]: row["n"]
        for row in conn.execute(
            "SELECT arm, COUNT(*) AS n FROM runs WHERE status = 'done' GROUP BY arm"
        )
    }
    by_rep = {
        row["rep"]: row["n"]
        for row in conn.execute(
            "SELECT rep, COUNT(*) AS n FROM runs WHERE status = 'done' GROUP BY rep"
        )
    }
    total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
    return {
        "total": total,
        "by_status": by_status,
        "done_by_arm": by_arm,
        "done_by_rep": by_rep,
        "meta": meta,
    }
