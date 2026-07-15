"""X1 content-drift ratio (analysis-plan-addendum-1.md §6, exploratory, labeled).

Per T-real run: in-scope churn ÷ ground-truth PR churn. The ground truth is
the merged PR each card was sourced from (`source.ground_truth_pr`), fetched
once via `gh api` and cached (analysis/x1_ground_truth.json) — a one-off
metadata fetch, no agent runs. Distribution published; outliers (>3× the
ground-truth footprint) listed for judge/manual review over stored diffs,
with a mechanical triage column (dominant in-scope file by churn).

Usage (from harness/):  uv run python ../analysis/x1_content_drift.py
Writes: results/reports/x1-content-drift-1.md
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness" / "src"))

from harness import taskcards  # noqa: E402

RUNS_DIR = ROOT / "results" / "runs"
CACHE = ROOT / "analysis" / "x1_ground_truth.json"
OUT = ROOT / "results" / "reports" / "x1-content-drift-1.md"
ARMS = ("vanilla", "claudemd")
MODEL = "sonnet"


def gt_churn_for(pr_url: str) -> int:
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        raise ValueError(f"unparseable PR url: {pr_url}")
    owner, repo, num = m.groups()
    out = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}/pulls/{num}",
         "--jq", "{additions: .additions, deletions: .deletions}"],
        capture_output=True, text=True, check=True,
    ).stdout
    d = json.loads(out)
    return int(d["additions"]) + int(d["deletions"])


def dominant_file(run_id: str, task) -> str:
    """Mechanical triage: the in-scope file with the most churn in the diff."""
    p = RUNS_DIR / run_id / "diff.patch"
    if not p.exists():
        return "-"
    from harness.metrics import scope as scope_m
    counts: dict[str, int] = {}
    current = None
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith("+++ b/"):
            current = ln[6:].strip()
        elif current and (ln.startswith("+") or ln.startswith("-")) and not ln.startswith(("+++", "---")):
            if scope_m.is_in_scope(current, task):
                counts[current] = counts.get(current, 0) + 1
    if not counts:
        return "-"
    f, n = max(counts.items(), key=lambda kv: kv[1])
    return f"{f} ({n} lines)"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cards, errs = taskcards.load_all(ROOT / "tasks")
    if errs:
        raise SystemExit(errs)
    reals = {c.id: c for c in cards if c.kind == "real" and not c.control}

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    for cid, card in sorted(reals.items()):
        if cid in cache:
            continue
        pr = (card.raw.get("source") or {}).get("ground_truth_pr")
        if not pr:
            cache[cid] = None
            continue
        try:
            cache[cid] = gt_churn_for(pr)
            print(f"fetched {cid}: {cache[cid]} lines")
        except Exception as e:  # noqa: BLE001
            cache[cid] = None
            print(f"FAILED {cid}: {e}")
    CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    rows = []
    for cid, card in sorted(reals.items()):
        gt = cache.get(cid)
        if not gt:
            continue
        for arm in ARMS:
            for rep in (1, 2, 3):
                rid = f"{cid}--{arm}--{MODEL}--r{rep}"
                rj = RUNS_DIR / rid / "result.json"
                if not rj.exists():
                    continue
                m = json.loads(rj.read_text(encoding="utf-8"))["metrics"]["scope"]
                in_scope = int(m["total_churn_lines"] or 0) - int(m["out_of_scope_churn_lines"] or 0)
                rows.append({
                    "run": rid, "card": cid, "arm": arm,
                    "in_scope": in_scope, "gt": gt, "ratio": in_scope / gt,
                })

    o = ["# X1 · content-drift ratio (exploratory, labeled)\n"]
    o.append("Per T-real run: in-scope churn ÷ ground-truth merged-PR churn "
             "(additions+deletions from the GitHub API, one-off metadata fetch, "
             "cached in analysis/x1_ground_truth.json). This is the pre-declared "
             "exploratory pass for in-scope-CONTENT drift, which M1–M3 cannot see: "
             "a ratio well above 1 means the agent wrote far more inside scope than "
             "the human fix needed. Never confirmatory.\n")
    missing = [cid for cid in reals if not cache.get(cid)]
    o.append(f"Coverage: {len(reals) - len(missing)}/{len(reals)} T-real cards "
             f"({', '.join(missing) if missing else 'no gaps'}).\n")

    o.append("| arm | n runs | median | mean | p90 | max | share >3x |\n|---|---|---|---|---|---|---|")
    for arm in ARMS:
        rs = sorted(r["ratio"] for r in rows if r["arm"] == arm)
        if not rs:
            continue
        p90 = rs[min(len(rs) - 1, int(0.9 * len(rs)))]
        over = sum(1 for r in rs if r > 3)
        o.append(f"| {arm} | {len(rs)} | {median(rs):.2f} | {mean(rs):.2f} | "
                 f"{p90:.2f} | {max(rs):.2f} | {over}/{len(rs)} ({over/len(rs)*100:.1f}%) |")

    outliers = sorted((r for r in rows if r["ratio"] > 3), key=lambda r: -r["ratio"])
    o.append(f"\n## Outliers (>3x ground-truth footprint): {len(outliers)} runs, "
             "listed for judge/manual review over stored diffs\n")
    o.append("| run | ratio | in-scope lines | ground truth | dominant in-scope file |\n|---|---|---|---|---|")
    for r in outliers:
        dom = dominant_file(r["run"], reals[r["card"]])
        o.append(f"| {r['run']} | {r['ratio']:.1f}x | {r['in_scope']} | {r['gt']} | {dom} |")

    by_arm_out = {arm: sum(1 for r in outliers if r["arm"] == arm) for arm in ARMS}
    o.append(f"\nOutliers by arm: vanilla {by_arm_out['vanilla']}, claudemd {by_arm_out['claudemd']}.\n")
    o.append("Interpretation guardrails: T-real prompts sometimes legitimately ask for "
             "tests the human PR lacked; a high ratio flags volume, not necessarily "
             "waste. Manual-review dispositions belong in the interim writeup.\n")

    OUT.write_text("\n".join(o) + "\n", encoding="utf-8")
    print(f"written: {OUT} | rows {len(rows)} | outliers {len(outliers)}")


if __name__ == "__main__":
    main()
