"""Queue semantics: claim ordering, rate-limit resume, stale reset.

These are the crash-safety guarantees the whole subscription-bounded study
rests on, so they get the most direct tests.
"""

import sqlite3

import pytest

from harness import queue, schedule


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    connection = queue.connect(tmp_path / "runs.db")
    queue.init_db(connection, meta={"schedule_seed": "7"})
    return connection


def _rows():
    tasks = [{"task_id": "demo-t01", "repo": "demo"}, {"task_id": "demo-t02", "repo": "demo"}]
    return schedule.generate(tasks, ["vanilla", "claudemd"], ["sonnet"], reps=2, seed=7)


def test_insert_and_count(conn):
    rows = _rows()
    queue.insert_schedule(conn, rows)
    assert queue.run_count(conn) == 8


def test_claim_follows_order_key_and_marks_running(conn):
    rows = _rows()
    queue.insert_schedule(conn, rows)
    first_expected = min(rows, key=lambda r: r["order_key"])["run_id"]

    claimed = queue.claim_next(conn)
    assert claimed is not None
    assert claimed["run_id"] == first_expected
    assert claimed["status"] == "running"
    assert claimed["attempt"] == 1
    assert claimed["started_at"] is not None


def test_claim_returns_none_when_exhausted(conn):
    queue.insert_schedule(conn, _rows())
    seen = set()
    while (row := queue.claim_next(conn)) is not None:
        seen.add(row["run_id"])
        queue.mark_done(conn, row["run_id"])
    assert len(seen) == 8
    assert queue.claim_next(conn) is None


def test_rate_limit_returns_to_pending_with_unconsumed_attempt(conn):
    queue.insert_schedule(conn, _rows())
    row = queue.claim_next(conn)
    assert row["attempt"] == 1

    queue.mark_rate_limited(conn, row["run_id"], resume_after="2099-01-01T00:00:00+00:00")
    stored = conn.execute(
        "SELECT * FROM runs WHERE run_id = ?", (row["run_id"],)
    ).fetchone()
    assert stored["status"] == "pending"
    assert stored["attempt"] == 0  # the rate-limited attempt is unconsumed
    assert stored["resume_after"] == "2099-01-01T00:00:00+00:00"


def test_resume_after_gates_claiming(conn):
    queue.insert_schedule(conn, _rows())
    row = queue.claim_next(conn)
    queue.mark_rate_limited(conn, row["run_id"], resume_after="2030-06-01T12:00:00+00:00")

    # Before the gate: this run is skipped, the next order_key is claimed instead.
    next_claim = queue.claim_next(conn, now="2030-06-01T11:00:00+00:00")
    assert next_claim is not None
    assert next_claim["run_id"] != row["run_id"]
    queue.mark_done(conn, next_claim["run_id"])

    # Drain everything else that is not gated.
    while (other := queue.claim_next(conn, now="2030-06-01T11:00:00+00:00")) is not None:
        assert other["run_id"] != row["run_id"]
        queue.mark_done(conn, other["run_id"])

    # After the gate passes, the rate-limited run becomes claimable again.
    reclaimed = queue.claim_next(conn, now="2030-06-01T12:00:00+00:00")
    assert reclaimed is not None
    assert reclaimed["run_id"] == row["run_id"]
    assert reclaimed["attempt"] == 1


def test_reset_stale_returns_running_to_pending_keeping_attempt(conn):
    queue.insert_schedule(conn, _rows())
    row = queue.claim_next(conn)

    reset = queue.reset_stale(conn)
    assert reset == 1
    stored = conn.execute("SELECT * FROM runs WHERE run_id = ?", (row["run_id"],)).fetchone()
    assert stored["status"] == "pending"
    assert stored["attempt"] == 1  # crashed attempt really consumed quota
    assert stored["started_at"] is None

    # And it is claimable again.
    reclaimed = queue.claim_next(conn)
    assert reclaimed["run_id"] == row["run_id"]
    assert reclaimed["attempt"] == 2


def test_mark_done_error_and_summary(conn):
    queue.insert_schedule(conn, _rows())
    first = queue.claim_next(conn)
    queue.mark_done(conn, first["run_id"], session_id="sess-1", transcript_path="t.jsonl")
    second = queue.claim_next(conn)
    queue.mark_error(conn, second["run_id"], "boom")

    summary = queue.status_summary(conn)
    assert summary["total"] == 8
    assert summary["by_status"]["done"] == 1
    assert summary["by_status"]["error"] == 1
    assert summary["by_status"]["pending"] == 6
    assert summary["meta"]["schedule_seed"] == "7"

    done = conn.execute("SELECT * FROM runs WHERE run_id = ?", (first["run_id"],)).fetchone()
    assert done["session_id"] == "sess-1"
    assert done["transcript_path"] == "t.jsonl"
    errored = conn.execute("SELECT * FROM runs WHERE run_id = ?", (second["run_id"],)).fetchone()
    assert errored["error"] == "boom"
