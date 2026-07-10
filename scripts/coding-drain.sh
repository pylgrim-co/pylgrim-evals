#!/usr/bin/env bash
# Parallel drain for the coding-task queue (results/runs.db).
#
# Usage: bash scripts/coding-drain.sh [--workers N] [--batch M]
#   --workers N   parallel `harness run` workers per round (default 2)
#   --batch M     max runs each worker claims per round (default 4)
#
# Why parallel coding runs are safe HERE (and only here):
#   * Repo partition: worker k runs `harness run --workers N --worker-index k`,
#     which claims only runs whose repo falls in its stripe of the sorted repo
#     list (queue.claim_next repo filter). Disjoint repos -> disjoint
#     repo-pinned workspace slots (each worker's slots are also offset by
#     worker_index * slot_count), so no two workers ever share a worktree.
#   * Disjoint claims: queue.claim_next's SELECT+UPDATE transaction already
#     prevents double-claiming; the partition makes it moot anyway.
#
# The stale-reset hazard (found live in the skills drain) applies identically:
# a startup reset flips 'running' rows back to 'pending' and would resurrect a
# sibling's in-flight claim. Reset ONCE up front; workers use --no-stale-reset.
#
# Rate limits: when the subscription cap bites, every worker hits it, marks
# its current run pending with the same resume_after gate, and exits; the
# outer loop backs off instead of burning attempts.
#
# Safe to kill and restart; resumes from the queue.
set -u
cd "$(dirname "$0")/../harness" || exit 1

WORKERS=2
BATCH=4
while [ $# -gt 0 ]; do
  case "$1" in
    --workers) WORKERS="$2"; shift 2 ;;
    --batch)   BATCH="$2";   shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

py() {
  uv run python -c "import pathlib; from harness import queue; c = queue.connect(pathlib.Path('..', 'results', 'runs.db').resolve()); $1"
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
  echo "$(date -Is) coding runs remaining: $left (workers: $WORKERS, batch: $BATCH)"
  [ "$left" = "0" ] && break
  pids=()
  for k in $(seq 0 $((WORKERS - 1))); do
    {
      echo "=== round starting $(date -Is) ==="
      uv run harness run --root .. --batch "$BATCH" \
        --workers "$WORKERS" --worker-index "$k" --no-stale-reset
    } >> "../results/coding-drain-worker-$k.log" 2>&1 &
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
echo "$(date -Is) coding queue drained"
