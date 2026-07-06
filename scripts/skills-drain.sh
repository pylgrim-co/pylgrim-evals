#!/usr/bin/env bash
# Parallel drain for the skills stress queue (results/skills.db).
#
# Usage: bash scripts/skills-drain.sh [--workers N] [--batch M]
#   --workers N   parallel run-skills processes per round (default 3)
#   --batch M     max runs each worker claims per round (default 4)
#
# Why parallel claiming is safe here:
#   queue.claim_next runs SELECT + UPDATE ... WHERE status='pending' inside
#   one SQLite transaction (WAL mode) and checks rowcount, so two workers can
#   never claim the same run_id; a worker that loses the race simply finds no
#   eligible row and ends its batch. Skill runs are also fully isolated per
#   run_id (results/zoo-runs/<run_id>/workspace); there are no shared
#   workspace slots.
#
# The one hazard, found live: queue.reset_stale at worker STARTUP flips
# 'running' rows back to 'pending', which under parallel start resets a
# sibling's in-flight claim and duplicates the run (three workers collided
# in one workspace). So this script resets stale rows exactly once, up
# front, and every worker runs with --no-stale-reset.
#
# Limits, read before scaling up:
#   * Parallelism helps only until the subscription usage cap bites; when it
#     does, every worker hits the same rate limit, marks its current run
#     pending with the same resume_after gate, and exits. The outer loop then
#     backs off on the shared gate, so the drain degrades to waiting, not to
#     burning attempts.
#   * Coding-task runs (`harness run`, NOT `run-skills`) must NOT be
#     parallelized this way: they use repo-pinned workspace slots
#     (slot = repo round-robin), so two workers on the same repo would
#     collide in one slot directory. They would need per-worker slot ranges
#     first.
#
# Safe to kill and restart; resumes from the queue.
set -u
cd "$(dirname "$0")/../harness" || exit 1

WORKERS=3
BATCH=4
while [ $# -gt 0 ]; do
  case "$1" in
    --workers) WORKERS="$2"; shift 2 ;;
    --batch)   BATCH="$2";   shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

py() {
  uv run python -c "import pathlib; from harness import queue; c = queue.connect(pathlib.Path('..', 'results', 'skills.db').resolve()); $1"
}

remaining() {
  py "print(c.execute(\"SELECT COUNT(*) c FROM runs WHERE status IN ('pending','running')\").fetchone()['c'])"
}

# Single up-front stale reset (a previous process may have died mid-run).
# Workers below never reset: see the header hazard note.
stale=$(py "print(queue.reset_stale(c))")
[ "$stale" != "0" ] && echo "$(date -Is) reset $stale stale running row(s) to pending"

while :; do
  left=$(remaining)
  echo "$(date -Is) skills remaining: $left (workers: $WORKERS, batch: $BATCH)"
  [ "$left" = "0" ] && break
  pids=()
  for i in $(seq 1 "$WORKERS"); do
    {
      echo "=== round starting $(date -Is) ==="
      uv run harness run-skills --root .. --batch "$BATCH" --no-stale-reset
    } >> "../results/drain-worker-$i.log" 2>&1 &
    pids+=($!)
  done
  wait "${pids[@]}"
  now=$(remaining)
  if [ "$now" = "$left" ]; then
    # No progress: everything eligible is gated by resume_after. Back off.
    echo "$(date -Is) no progress (rate-limit gate?); sleeping 600s"
    sleep 600
  fi
done
echo "$(date -Is) skills queue drained"
