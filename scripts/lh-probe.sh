#!/usr/bin/env bash
# Long-horizon probe (pre-freeze, excluded from confirmatory): 2 LH cards x
# both arms on sonnet. Slots are re-warmed at each card's base SHA first
# (l01 bases differ from the corpus pins; deps must match the era).
set -u
cd "$(dirname "$0")/../harness" || exit 1

warm() { # name url sha slot install
  uv run python -c "
from harness import workspace
import subprocess
slot_dir = workspace.prepare('../results', $4, '$1', '$2', '$3')
r = subprocess.run('$5', shell=True, cwd=str(slot_dir), capture_output=True, text=True, timeout=1800)
print('$1 warm at $3:', 'OK' if r.returncode == 0 else 'FAIL ' + (r.stdout + r.stderr)[-300:])
raise SystemExit(r.returncode)
" || exit 1
}

probe() { # card arm name slot url sha timeout
  local dir="../results/runs/smoke--$1--$2--sonnet"
  if [ -f "$dir/result.json" ]; then echo "$(date -Is) SKIP $1 $2"; return 0; fi
  echo "$(date -Is) RUN  $1 $2 (timeout $7 min)"
  uv run harness smoke --root .. --repo "$5" --sha "$6" --task "../tasks/$1.yaml" \
    --arm "$2" --model sonnet --repo-name "$3" --slot "$4" --timeout-min "$7" \
    > /dev/null 2>>../results/lh-probe.log
  local rc=$?
  [ $rc -eq 2 ] && { echo "$(date -Is) RATE LIMITED; stopping (rerun to resume)"; exit 2; }
  [ $rc -ne 0 ] && echo "$(date -Is) ERROR rc=$rc at $1 $2 (see lh-probe.log); continuing"
}

CLICK_URL=https://github.com/pallets/click
CLICK_SHA=$(python -c "import yaml;print(yaml.safe_load(open('../tasks/click-l01.yaml',encoding='utf-8'))['base_sha'])" 2>/dev/null || uv run python -c "import yaml;print(yaml.safe_load(open('../tasks/click-l01.yaml',encoding='utf-8'))['base_sha'])")
ZU_URL=https://github.com/pmndrs/zustand
ZU_SHA=$(uv run python -c "import yaml;print(yaml.safe_load(open('../tasks/zustand-l01.yaml',encoding='utf-8'))['base_sha'])")

echo "$(date -Is) warming click slot 0 at $CLICK_SHA"
warm click "$CLICK_URL" "$CLICK_SHA" 0 "uv sync"
probe click-l01 vanilla  click 0 "$CLICK_URL" "$CLICK_SHA" 45
probe click-l01 claudemd click 0 "$CLICK_URL" "$CLICK_SHA" 45

echo "$(date -Is) warming zustand slot 1 at $ZU_SHA"
warm zustand "$ZU_URL" "$ZU_SHA" 1 "pnpm install"
probe zustand-l01 vanilla  zustand 1 "$ZU_URL" "$ZU_SHA" 60
probe zustand-l01 claudemd zustand 1 "$ZU_URL" "$ZU_SHA" 60

echo "$(date -Is) LH probe complete"
