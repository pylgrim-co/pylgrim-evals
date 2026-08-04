#!/usr/bin/env bash
# scenario-check.sh — mechanical pre-freeze verification of E-coord PILOT
# scenarios against the four binding authoring rules of
# preregistration/design-e-coord-draft-3.md §3.
#
# For each scenario in scenarios/pilot/:
#   1. Existence proof (rule 1): applies both reference diffs
#      (reference-solutions/<scenario_id>/card-{a,b}.diff) to branches off
#      the pinned SHA in a scratch clone and asserts `git merge-tree
#      --write-tree` produces a CLEAN merge.
#   2. Wall-time floor (rule 4) + determinism (M6): runs each card's outcome
#      command once on its own branch tree (grounds C3/C5), then k=3 times on
#      the merged tree; every run must exit 0, the three merged-tree exit
#      codes must be identical, and every run must complete in <=120 s
#      (WALL_LIMIT) on this host.
#   3. Symmetry (rule 3): computes churn (added+deleted) per reference diff
#      and asserts the ratio is within 3x.
#   4. Pressure floor (rule 2): computes the overlap-pressure score = number
#      of files in the intersection of the two reference solutions'
#      read-plus-write neighborhoods (touched files plus their direct
#      importers/importees at the pinned SHA), and reports co-written files.
#      The score is REPORTED for stratum ratification, not asserted (strata
#      thresholds are pinned at freeze from these measurements).
#
# The script only READS scenario and solution files; all work happens in a
# mktemp scratch directory. Run it on the pinned VM host (docs/ops/vm-setup.md):
# the 120 s wall-time bound is defined ON THAT HOST, so timings measured
# anywhere else are advisory only.
#
# Usage:
#   scripts/scenario-check.sh <mirrors-dir> [scenario_id ...]
#     <mirrors-dir>  directory containing bare mirrors named <repo>.git
#                    (e.g. results/repos)
#     scenario_id    optional subset; default = every scenarios/pilot/*.yaml
#
# Exit status: 0 iff every checked scenario passes every asserted rule.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCENARIO_DIR="${SCENARIO_DIR:-$REPO_ROOT/scenarios/pilot}"
SOLUTION_DIR="$REPO_ROOT/reference-solutions"
WALL_LIMIT=120
K_RUNS=3

if [ $# -lt 1 ]; then
  echo "usage: $0 <mirrors-dir> [scenario_id ...]" >&2
  exit 2
fi

MIRRORS="$(cd "$1" && pwd)" || exit 2
shift

# Per-repo dependency install commands (corpus.yaml pins).
install_cmd() {
  case "$1" in
    zustand) echo "pnpm install --silent" ;;
    click) echo "uv sync" ;;
    *) echo "" ;;
  esac
}

yaml_scalar() { # yaml_scalar <file> <key>  — first "key: value" at any indent
  sed -n "s/^[[:space:]]*$2:[[:space:]]*//p" "$1" | head -1 | tr -d '"'
}

yaml_nth_test_command() { # <file> <n>
  sed -n "s/^[[:space:]]*test_command:[[:space:]]*//p" "$1" | sed -n "$2p" | sed 's/^"//; s/"$//'
}

FAILURES=0
fail() {
  echo "  FAIL: $*"
  FAILURES=$((FAILURES + 1))
}

timed_run() { # timed_run <workdir> <command>  — echoes "exit_code seconds"
  local dir="$1" cmd="$2" start end rc
  start=$(date +%s)
  (cd "$dir" && timeout "$((WALL_LIMIT + 30))" bash -c "$cmd") >/dev/null 2>&1
  rc=$?
  end=$(date +%s)
  echo "$rc $((end - start))"
}

pressure_score() { # <clone> <repo-name> <base-sha> <diff-a> <diff-b>
  python3 - "$@" <<'PYEOF'
import os
import re
import subprocess
import sys

repo_dir, repo_name, base_sha, diff_a, diff_b = sys.argv[1:6]


def git(*args):
    return subprocess.run(
        ["git", "-C", repo_dir, *args],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


ALL_FILES = set(git("ls-tree", "-r", "--name-only", base_sha).split("\n")) - {""}

TS_IMPORT = re.compile(r"""(?:^|\n)\s*(?:import|export)[^'"\n]*['"]([^'"\n]+)['"]""")
PY_FROM = re.compile(r"^\s*from\s+([.\w]+)\s+import", re.M)
PY_IMPORT = re.compile(r"^\s*import\s+([\w.]+)", re.M)


def touched(diff_path):
    files = set()
    with open(diff_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("+++ b/"):
                files.add(line[6:].strip())
    return files


def added_content(diff_path, path):
    out, inside = [], False
    with open(diff_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("+++ b/"):
                inside = line[6:].strip() == path
            elif inside and line.startswith("+") and not line.startswith("+++"):
                out.append(line[1:])
    return "".join(out)


def content(path, diffs):
    if path in ALL_FILES:
        return git("show", f"{base_sha}:{path}")
    for d in diffs:
        text = added_content(d, path)
        if text:
            return text
    return ""


def resolve(spec, importer):
    cands = []
    if repo_name == "zustand":
        if spec.startswith("."):
            base = os.path.normpath(
                os.path.join(os.path.dirname(importer), spec)
            ).replace("\\", "/")
            cands = [base, base + ".ts", base + ".tsx"]
        elif spec == "zustand":
            cands = ["src/index.ts"]
        elif spec.startswith("zustand/"):
            base = "src/" + spec[len("zustand/") :]
            cands = [base, base + ".ts", base + ".tsx"]
    elif repo_name == "click":
        if spec.startswith("."):
            base = "src/click/" + spec.lstrip(".").replace(".", "/")
            cands = [base + ".py", "src/click/__init__.py" if not spec.lstrip(".") else ""]
        elif spec == "click":
            cands = ["src/click/__init__.py"]
        elif spec.startswith("click."):
            cands = ["src/click/" + spec[len("click.") :].replace(".", "/") + ".py"]
    for cand in cands:
        if cand and cand in ALL_FILES:
            return cand
    return None


def import_specs(text):
    if repo_name == "zustand":
        return TS_IMPORT.findall(text)
    return PY_FROM.findall(text) + PY_IMPORT.findall(text)


def neighborhood(diff_path):
    t = touched(diff_path)
    hood = set(t)
    # direct importees of touched files
    for path in t:
        for spec in import_specs(content(path, [diff_path])):
            target = resolve(spec, path)
            if target:
                hood.add(target)
    # direct importers of touched files, scanned at the pinned SHA
    source_like = [
        p
        for p in ALL_FILES
        if p.endswith((".ts", ".tsx", ".py")) and (p.startswith("src") or p.startswith("tests"))
    ]
    for path in source_like:
        for spec in import_specs(content(path, [])):
            target = resolve(spec, path)
            if target and target in t:
                hood.add(path)
                break
    return t, hood


touched_a, hood_a = neighborhood(diff_a)
touched_b, hood_b = neighborhood(diff_b)
shared = sorted((hood_a & hood_b) - {p for p in hood_a & hood_b if p.startswith(".pylgrim")})
cowritten = sorted(touched_a & touched_b)
print(f"score={len(shared)}")
print(f"shared={','.join(shared) if shared else '-'}")
print(f"cowritten={','.join(cowritten) if cowritten else '-'}")
PYEOF
}

if [ $# -ge 1 ]; then
  SCENARIOS=""
  for id in "$@"; do
    SCENARIOS="$SCENARIOS $SCENARIO_DIR/$id.yaml"
  done
else
  SCENARIOS=$(ls "$SCENARIO_DIR"/ecoord-*.yaml)
fi

SCRATCH=$(mktemp -d)
trap 'rm -rf "$SCRATCH"' EXIT

for yaml in $SCENARIOS; do
  [ -f "$yaml" ] || { echo "missing scenario file: $yaml" >&2; FAILURES=$((FAILURES+1)); continue; }
  sid=$(yaml_scalar "$yaml" scenario_id)
  repo=$(yaml_scalar "$yaml" repo)
  sha=$(yaml_scalar "$yaml" pinned_sha)
  stratum=$(yaml_scalar "$yaml" stratum)
  cmd_a=$(yaml_nth_test_command "$yaml" 1)
  cmd_b=$(yaml_nth_test_command "$yaml" 2)
  diff_a="$SOLUTION_DIR/$sid/card-a.diff"
  diff_b="$SOLUTION_DIR/$sid/card-b.diff"
  mirror="$MIRRORS/$repo.git"

  echo "== $sid (repo=$repo stratum=$stratum sha=${sha:0:12}) =="

  for f in "$diff_a" "$diff_b"; do
    [ -f "$f" ] || { fail "missing reference diff $f"; continue 2; }
  done
  [ -d "$mirror" ] || { fail "missing mirror $mirror"; continue; }

  clone="$SCRATCH/$sid"
  git clone -q "$mirror" "$clone" || { fail "clone failed"; continue; }
  git -C "$clone" config core.autocrlf false
  git -C "$clone" checkout -q --detach "$sha" || { fail "pinned SHA not in mirror"; continue; }

  # --- rule 1: apply both diffs, assert clean merge-tree ---------------------
  git -C "$clone" branch -f ref-a "$sha"
  git -C "$clone" branch -f ref-b "$sha"
  git -C "$clone" checkout -q ref-a
  git -C "$clone" apply --index "$diff_a" || { fail "card-a.diff does not apply at pin"; continue; }
  git -C "$clone" -c user.email=check@local -c user.name=check commit -qm "ref-a" || { fail "commit ref-a"; continue; }
  git -C "$clone" checkout -q ref-b
  git -C "$clone" apply --index "$diff_b" || { fail "card-b.diff does not apply at pin"; continue; }
  git -C "$clone" -c user.email=check@local -c user.name=check commit -qm "ref-b" || { fail "commit ref-b"; continue; }

  if merged_tree=$(git -C "$clone" merge-tree --write-tree --no-messages ref-a ref-b 2>/dev/null); then
    echo "  merge: CLEAN ($merged_tree)"
  else
    fail "merge-tree reports conflicts (rule 1 violated)"
    continue
  fi
  merged_commit=$(git -C "$clone" -c user.email=check@local -c user.name=check \
    commit-tree "$merged_tree" -p "$(git -C "$clone" rev-parse ref-a)" \
    -p "$(git -C "$clone" rev-parse ref-b)" -m "merged reference pair")

  # --- rule 3: churn symmetry ------------------------------------------------
  churn_a=$(git -C "$clone" apply --numstat "$diff_a" 2>/dev/null | awk '{s+=$1+$2} END {print s+0}')
  churn_b=$(git -C "$clone" apply --numstat "$diff_b" 2>/dev/null | awk '{s+=$1+$2} END {print s+0}')
  ratio_ok=$(awk -v a="$churn_a" -v b="$churn_b" 'BEGIN {
    hi = (a > b) ? a : b; lo = (a > b) ? b : a;
    if (lo == 0) { print "no"; exit }
    printf (hi / lo <= 3.0) ? "yes" : "no" }')
  echo "  churn: a=$churn_a b=$churn_b"
  [ "$ratio_ok" = "yes" ] || fail "churn ratio exceeds 3x (rule 3 violated)"

  # --- rule 2: overlap-pressure score (reported, ratified at freeze) --------
  pressure_score "$clone" "$repo" "$sha" "$diff_a" "$diff_b" | sed 's/^/  pressure: /' \
    || fail "pressure-score computation errored"

  # --- rule 4 + M6: outcome commands, branch pass + merged k=3 --------------
  inst=$(install_cmd "$repo")
  if [ -z "$inst" ]; then
    fail "no install command known for repo $repo"
    continue
  fi
  git -C "$clone" checkout -q ref-a
  if ! (cd "$clone" && bash -c "$inst") >/dev/null 2>&1; then
    fail "install failed ($inst)"
    continue
  fi

  branch_fail=0
  for card in a b; do
    if [ "$card" = a ]; then branch=ref-a; cmd="$cmd_a"; else branch=ref-b; cmd="$cmd_b"; fi
    git -C "$clone" checkout -q "$branch"
    read -r rc secs <<<"$(timed_run "$clone" "$cmd")"
    echo "  branch-$card: exit=$rc wall=${secs}s"
    if [ "$rc" -ne 0 ]; then fail "card-$card outcome command fails on its own branch"; branch_fail=1; fi
    if [ "$secs" -gt "$WALL_LIMIT" ]; then fail "card-$card branch run exceeds ${WALL_LIMIT}s (rule 4 violated)"; fi
  done
  [ "$branch_fail" -eq 0 ] || continue

  git -C "$clone" checkout -q --detach "$merged_commit"
  for card in a b; do
    if [ "$card" = a ]; then cmd="$cmd_a"; else cmd="$cmd_b"; fi
    codes=""
    card_fail=0
    for i in $(seq 1 "$K_RUNS"); do
      read -r rc secs <<<"$(timed_run "$clone" "$cmd")"
      codes="$codes $rc"
      echo "  merged-$card run$i: exit=$rc wall=${secs}s"
      if [ "$secs" -gt "$WALL_LIMIT" ]; then fail "card-$card merged run $i exceeds ${WALL_LIMIT}s (rule 4 violated)"; card_fail=1; fi
    done
    uniq_codes=$(echo "$codes" | tr ' ' '\n' | sed '/^$/d' | sort -u | wc -l)
    first_code=$(echo "$codes" | awk '{print $1}')
    if [ "$uniq_codes" -ne 1 ]; then fail "card-$card merged runs are non-deterministic (M6 violated: exit codes$codes)"; card_fail=1; fi
    if [ "$first_code" -ne 0 ]; then fail "card-$card outcome command fails on the merged tree (rule 1 violated)"; card_fail=1; fi
    [ "$card_fail" -eq 0 ] && echo "  merged-$card: PASS (deterministic across k=$K_RUNS)"
  done
done

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "scenario-check: ALL CHECKS PASSED"
  exit 0
else
  echo "scenario-check: $FAILURES FAILURE(S)"
  exit 1
fi
