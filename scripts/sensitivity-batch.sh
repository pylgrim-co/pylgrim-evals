#!/usr/bin/env bash
# Instrument-sensitivity batch (pre-freeze, excluded from confirmatory).
# Ratified T-bait cards on both arms (sonnet) + two haiku probes, run via
# smoke on warmed slots (click=0, zustand=1). Stops cleanly on rate limit.
set -u
cd "$(dirname "$0")/../harness" || exit 1

run() { # card arm model repo_name slot url sha
  local card="$1" arm="$2" model="$3" name="$4" slot="$5" url="$6" sha="$7"
  local dir="../results/runs/smoke--${card}--${arm}--${model}"
  if [ -f "$dir/result.json" ]; then
    echo "$(date -Is) SKIP ${card} ${arm} ${model} (exists)"
    return 0
  fi
  echo "$(date -Is) RUN  ${card} ${arm} ${model}"
  uv run harness smoke --root .. --repo "$url" --sha "$sha" \
    --task "../tasks/${card}.yaml" --arm "$arm" --model "$model" \
    --repo-name "$name" --slot "$slot" > /dev/null 2>>../results/sensitivity-batch.log
  local rc=$?
  if [ $rc -eq 2 ]; then
    echo "$(date -Is) RATE LIMITED at ${card} ${arm} ${model}; stopping (rerun to resume)"
    exit 2
  elif [ $rc -ne 0 ]; then
    echo "$(date -Is) ERROR rc=$rc at ${card} ${arm} ${model} (see sensitivity-batch.log); continuing"
  fi
}

CLICK_URL=https://github.com/pallets/click
CLICK_SHA=16fc00e2f4a2717a521084f193709a6058afc693
ZU_URL=https://github.com/pmndrs/zustand
ZU_SHA=a1f685ca744e56a982b1c5029620e0925c3ee996

for arm in vanilla claudemd; do
  for b in b01 b02 b03; do
    run "click-$b" "$arm" sonnet click 0 "$CLICK_URL" "$CLICK_SHA"
  done
done
for arm in vanilla claudemd; do
  for b in b01 b02 b03; do
    run "zustand-$b" "$arm" sonnet zustand 1 "$ZU_URL" "$ZU_SHA"
  done
done
# haiku probes (weaker-tier sensitivity)
run click-b02 vanilla haiku click 0 "$CLICK_URL" "$CLICK_SHA"
run zustand-b01 vanilla haiku zustand 1 "$ZU_URL" "$ZU_SHA"
echo "$(date -Is) sensitivity batch complete"
