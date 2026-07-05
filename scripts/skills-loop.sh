#!/usr/bin/env bash
# Skills stress-matrix trickle: drains results/skills.db, then the 36 trigger probes.
# Safe to kill and restart. Resume after reboot: bash scripts/skills-loop.sh
cd "$(dirname "$0")/../harness" || exit 1
while :; do
  uv run harness run-skills --root .. --batch 20
  left=$(uv run python -c "import pathlib; from harness import queue; c = queue.connect(pathlib.Path('..', 'results', 'skills.db').resolve()); print(c.execute(\"SELECT COUNT(*) c FROM runs WHERE status IN ('pending','running')\").fetchone()['c'])")
  echo "$(date -Is) skills remaining: $left"
  [ "$left" = "0" ] && break
  sleep 600
done
uv run harness run-triggers --root ..
uv run harness report-skills --root ..
echo "skills stress matrix drained; report regenerated"
