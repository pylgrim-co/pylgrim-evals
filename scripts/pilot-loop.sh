#!/usr/bin/env bash
# Pilot trickle loop: runs queued batches until the schedule is drained.
# Safe to kill and restart at any time (the queue is the source of truth;
# a killed run is reset to pending on the next invocation).
# Resume after reboot: bash scripts/pilot-loop.sh
cd "$(dirname "$0")/../harness" || exit 1
while :; do
  uv run harness run --root .. --batch 48 --slot-count 2 --timeout-min 30
  left=$(uv run python -c "import pathlib; from harness import queue; c = queue.connect(pathlib.Path('..', 'results', 'runs.db').resolve()); print(c.execute(\"SELECT COUNT(*) c FROM runs WHERE status IN ('pending','running')\").fetchone()['c'])")
  echo "$(date -Is) remaining: $left"
  [ "$left" = "0" ] && break
  sleep 600
done
echo "pilot schedule drained"
uv run harness status --root ..
