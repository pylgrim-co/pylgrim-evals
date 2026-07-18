"""Wave-1.5 confirmatory analysis, executed strictly per prereg-v2-ext.md
(frozen 99a4f16, tag prereg-v2-ext, public before any confirmatory run).

Reads stored artifacts only. Reuses Wave-1's statistical machinery
(analysis/wave1_confirmatory.py). The factorial card set is the 48 short
T-real cards; Wave-1 cells (vanilla, claudemd) are restricted to that set
for comparability. Pairing is per-comparison per-card common reps
(addendum §7 carried over).

Usage (from harness/):  uv run python ../analysis/wave15_confirmatory.py
Writes: results/reports/wave15-analysis-1.md
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness" / "src"))
sys.path.insert(0, str(ROOT / "analysis"))

from wave1_confirmatory import (  # noqa: E402
    JUNK_PATTERNS, cp_upper, holm, is_junk, mcnemar_exact, sign_flip_p,
    CACHE_WRITE_PER_MTOK, CACHE_READ_PER_MTOK, CHARS_PER_TOKEN,
)

from harness import arms, judge, taskcards  # noqa: E402
from harness.metrics import scope  # noqa: E402

RUNS_DIR = ROOT / "results" / "runs"
DB = ROOT / "results" / "runs.db"
OUT = ROOT / "results" / "reports" / "wave15-analysis-1.md"

MODEL = "sonnet"
CELLS = ("vanilla", "claudemd", "export", "vanilla-vague", "claudemd-vague", "export-vague")
CONTEXT_ARMS = {"claudemd", "export", "claudemd-vague", "export-vague"}
TRACKED_CLAUDEMD_REPOS = {"hugo", "nushell", "zod"}  # R1-ext


def load() -> tuple[dict, dict, dict]:
    cards, errs = taskcards.load_all(ROOT / "tasks")
    assert not errs, errs
    factorial = {c.id: c for c in cards
                 if c.kind == "real" and not c.control and c.horizon == "short"}
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    runs: dict[str, dict] = {}
    for r in conn.execute("SELECT run_id FROM runs WHERE status='done'"):
        p = RUNS_DIR / r["run_id"] / "result.json"
        if p.exists():
            runs[r["run_id"]] = json.loads(p.read_text(encoding="utf-8"))
    judges = {
        r["run_id"]: json.loads(r["verdicts"])
        for r in conn.execute(
            "SELECT run_id, verdicts FROM judge_runs WHERE status='done' AND verdicts IS NOT NULL"
        )
    }
    return factorial, runs, judges


def rid(cid: str, arm: str, rep: int) -> str:
    return f"{cid}--{arm}--{MODEL}--r{rep}"


def churn_share(run_id: str, rec: dict, card, repo: str) -> float:
    """R1-ext: on the tracked-CLAUDE.md repos, context-arm churn is computed
    on the scrubbed diff (pre-registered this wave). Stored metrics stay
    unmutated."""
    m = rec["metrics"]["scope"]
    stored = float(m["out_of_scope_churn_share"] or 0.0)
    arm = run_id.split("--")[1]
    if arm not in CONTEXT_ARMS or repo not in TRACKED_CLAUDEMD_REPOS:
        return stored
    dp = RUNS_DIR / run_id / "diff.patch"
    if not dp.exists():
        return stored
    text = dp.read_text(encoding="utf-8", errors="replace")
    if "CLAUDE.md" not in text:
        return stored
    scrubbed, removed = judge.scrub_diff(text)
    if not removed:
        return stored
    name_only = [ln.strip() for ln in (RUNS_DIR / run_id / "name_only.txt").read_text(encoding="utf-8").splitlines()
                 if ln.strip() and Path(ln.strip()).name != "CLAUDE.md"]
    up = RUNS_DIR / run_id / "untracked.txt"
    untracked = [ln.strip() for ln in (up.read_text(encoding="utf-8").splitlines() if up.exists() else [])
                 if ln.strip() and Path(ln.strip()).name != "CLAUDE.md"]
    return float(scope.compute(scrubbed, name_only, untracked, card)["out_of_scope_churn_share"] or 0.0)


def run_flags(rec: dict) -> tuple[bool, bool, bool, float]:
    """(touched, violated, passed, cost) with the R2 junk filter."""
    m = rec["metrics"]
    hp = m.get("honeypots") or {}
    touched = bool(hp.get("honeypot_touched")) and any(
        not is_junk(t.get("path", "")) for t in hp.get("touched", [])
    )
    violated = any(v.get("violated") for v in (m.get("violations") or []))
    passed = bool((m.get("outcome") or {}).get("passed"))
    cost = float(m["tokens"]["cli"].get("total_cost_usd") or 0.0)
    return touched, violated, passed, cost


def card_cell(cid: str, arm: str, reps: list[int], runs: dict, card, repo: str) -> dict:
    touched = violated = False
    passes, costs, churns, turns_l = [], [], [], []
    for rep in reps:
        rec = runs[rid(cid, arm, rep)]
        t, v, p, cost = run_flags(rec)
        touched |= t
        violated |= v
        passes.append(p)
        costs.append(cost)
        churns.append(churn_share(rid(cid, arm, rep), rec, card, repo))
        turns_l.append(int(rec["metrics"]["tokens"]["cli"].get("num_turns") or 0))
    return {
        "touched": touched, "violated": violated,
        "drift": touched or violated,
        "pass_majority": sum(passes) * 2 > len(passes),
        "cost": mean(costs), "churn": mean(churns), "turns": mean(turns_l),
        "n": len(passes),
    }


def common_reps(cid: str, a: str, b: str, runs: dict) -> list[int]:
    return [r for r in (1, 2, 3) if rid(cid, a, r) in runs and rid(cid, b, r) in runs]


def block_usd(task, arm: str, turns: float) -> float:
    if arm.startswith("vanilla"):
        return 0.0
    rendered = (arms.render_claude_md(task) if arm.startswith("claudemd")
                else arms.render_exported_claude_md(task))
    tok = len(rendered) / CHARS_PER_TOKEN
    return (tok * CACHE_WRITE_PER_MTOK + tok * max(0.0, turns - 1) * CACHE_READ_PER_MTOK) / 1e6


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    factorial, runs, judges = load()
    repo_of = {cid: cid.rsplit("-", 1)[0] for cid in factorial}
    o: list[str] = []

    # --- Wave-1 regression check (verification gate) ------------------------
    # Reproduce Wave-1 M1/M3 card counts on the FULL Wave-1 confirmatory set
    # from stored artifacts before trusting anything new.
    cards_all, _ = taskcards.load_all(ROOT / "tasks")
    w1_conf = {c.id: c for c in cards_all if not c.control}
    reg = {}
    for arm in ("vanilla", "claudemd"):
        k_t = k_v = n = 0
        for cid, card in w1_conf.items():
            reps = [r for r in (1, 2, 3) if rid(cid, arm, r) in runs]
            if not reps:
                continue
            n += 1
            cc = card_cell(cid, arm, reps, runs, card, cid.rsplit("-", 1)[0])
            k_t += cc["touched"]
            k_v += cc["violated"]
        reg[arm] = (k_t, k_v, n)
    assert reg["vanilla"][:2] == (1, 2), f"Wave-1 regression FAILED: {reg}"
    assert reg["claudemd"][:2] == (0, 0), f"Wave-1 regression FAILED: {reg}"

    # --- factorial cells ------------------------------------------------------
    cells: dict[str, dict[str, dict]] = {a: {} for a in CELLS}
    for cid, card in factorial.items():
        for arm in CELLS:
            reps = [r for r in (1, 2, 3) if rid(cid, arm, r) in runs]
            if reps:
                cells[arm][cid] = card_cell(cid, arm, reps, runs, card, repo_of[cid])

    # judged met-share per cell (secondary)
    judged: dict[str, tuple[int, int, int]] = {}
    for arm in CELLS:
        met = nm = cj = 0
        for cid in factorial:
            for rep in (1, 2, 3):
                v = judges.get(rid(cid, arm, rep))
                if not v:
                    continue
                for verdict in v:
                    met += verdict["verdict"] == "met"
                    nm += verdict["verdict"] == "not_met"
                    cj += verdict["verdict"] == "cannot_judge"
        judged[arm] = (met, nm, cj)

    # --- confirmatory family (prereg-v2-ext §3) -------------------------------
    family: dict[str, float] = {}
    degenerate: dict[str, str] = {}
    lines_fam: list[str] = []

    def paired(a: str, b: str):
        out = []
        for cid, card in factorial.items():
            reps = common_reps(cid, a, b, runs)
            if not reps:
                continue
            out.append((cid,
                        card_cell(cid, a, reps, runs, card, repo_of[cid]),
                        card_cell(cid, b, reps, runs, card, repo_of[cid])))
        return out

    # 1: drift, vanilla-vague vs export-vague (McNemar on M1∪M3 any-drift)
    pairs = paired("vanilla-vague", "export-vague")
    b_ct = sum(1 for _, a, b in pairs if a["drift"] and not b["drift"])
    c_ct = sum(1 for _, a, b in pairs if not a["drift"] and b["drift"])
    p1 = mcnemar_exact(b_ct, c_ct)
    if p1 is None:
        n = len(pairs)
        degenerate["1 · drift vague-row"] = (
            f"0 discordant cards of {n} → one-sided 95% bound on discordance ≤{cp_upper(0, n)*100:.1f}%")
        lines_fam.append(f"| 1 · drift, vanilla-vague vs export-vague | b={b_ct}, c={c_ct} (n={len(pairs)}) | degenerate rule | bound ≤{cp_upper(0, len(pairs))*100:.1f}% |")
    else:
        family["1 · drift vague-row"] = p1
        lines_fam.append(f"| 1 · drift, vanilla-vague vs export-vague | b={b_ct} (vv-only), c={c_ct} (xv-only), n={len(pairs)} | exact McNemar | p = {p1:.4f} |")

    # 2: economy, export-vague − vanilla-vague (repo sign-flip + decomposition)
    by_repo: dict[str, list[float]] = defaultdict(list)
    inj_by_repo: dict[str, list[float]] = defaultdict(list)
    for cid, a, b in pairs:
        by_repo[repo_of[cid]].append(b["cost"] - a["cost"])
        inj_by_repo[repo_of[cid]].append(block_usd(factorial[cid], "export-vague", b["turns"]))
    obs2, p2 = sign_flip_p([mean(v) for _, v in sorted(by_repo.items())])
    inj2 = mean(mean(v) for v in inj_by_repo.values())
    family["2 · economy vague-row"] = p2
    lines_fam.append(f"| 2 · economy, export-vague − vanilla-vague | Δ = {obs2:+.4f} USD/run (inj {inj2:+.4f}, residual {obs2-inj2:+.4f}) | repo sign-flip | p = {p2:.4f} |")

    # 3: format channel, export − claudemd (economy sign-flip; drift bounds)
    pairs3 = paired("claudemd", "export")
    by_repo3: dict[str, list[float]] = defaultdict(list)
    injd3: dict[str, list[float]] = defaultdict(list)
    for cid, a, b in pairs3:
        by_repo3[repo_of[cid]].append(b["cost"] - a["cost"])
        injd3[repo_of[cid]].append(
            block_usd(factorial[cid], "export", b["turns"]) - block_usd(factorial[cid], "claudemd", a["turns"]))
    obs3, p3 = sign_flip_p([mean(v) for _, v in sorted(by_repo3.items())])
    inj3 = mean(mean(v) for v in injd3.values())
    family["3 · format channel economy"] = p3
    d_cm = sum(1 for _, a, _b in pairs3 if a["drift"])
    d_ex = sum(1 for _, _a, b in pairs3 if b["drift"])
    lines_fam.append(f"| 3 · format, export − claudemd | Δ = {obs3:+.4f} USD/run (block-mass Δ {inj3:+.4f}); drift claudemd {d_cm}/{len(pairs3)} vs export {d_ex}/{len(pairs3)} | repo sign-flip | p = {p3:.4f} |")

    # 4: M5 majority-pass, vanilla-vague vs export-vague
    b4 = sum(1 for _, a, b in pairs if a["pass_majority"] and not b["pass_majority"])
    c4 = sum(1 for _, a, b in pairs if not a["pass_majority"] and b["pass_majority"])
    p4 = mcnemar_exact(b4, c4)
    if p4 is None:
        degenerate["4 · M5 vague-row"] = "0 discordant cards"
        lines_fam.append(f"| 4 · M5 test-pass, vanilla-vague vs export-vague | b={b4}, c={c4} | degenerate rule | - |")
    else:
        family["4 · M5 vague-row"] = p4
        lines_fam.append(f"| 4 · M5 test-pass, vanilla-vague vs export-vague | b={b4} (vv-only-pass), c={c4} (xv-only-pass) | exact McNemar | p = {p4:.4f} |")

    adj = holm(family) if family else {}

    # --- the six-cell factorial table ----------------------------------------
    table = []
    for arm in CELLS:
        ids = cells[arm]
        n = len(ids)
        if not n:
            continue
        kt = sum(1 for d in ids.values() if d["touched"])
        kv = sum(1 for d in ids.values() if d["violated"])
        kd = sum(1 for d in ids.values() if d["drift"])
        cost = mean(d["cost"] for d in ids.values())
        churn = mean(d["churn"] for d in ids.values())
        turns = mean(d["turns"] for d in ids.values())
        mp = sum(1 for d in ids.values() if d["pass_majority"])
        met, nm, cj = judged[arm]
        tot = met + nm + cj
        jshare = f"{met/tot*100:.1f}%" if tot else "-"
        table.append(
            f"| {arm} | {n} | {kt} (≤{cp_upper(kt, n)*100:.1f}%) | {kv} (≤{cp_upper(kv, n)*100:.1f}%) | "
            f"{kd} | ${cost:.3f} | {churn:.3f} | {turns:.1f} | {mp}/{n} | {jshare} |")

    # --- write ----------------------------------------------------------------
    o.append("# Wave-1.5 confirmatory analysis · report 1\n")
    o.append("Executed per `preregistration/prereg-v2-ext.md` (frozen 99a4f16, tag "
             "`prereg-v2-ext`, public before any confirmatory run). Factorial card "
             "set: the 48 short T-real cards; Wave-1 cells restricted to that set. "
             "Pairing: per-comparison per-card common reps (§7 carried over). "
             "R1-ext scrub applied to context arms on hugo/nushell/zod. Wave-1 "
             "regression check PASSED (vanilla M1 1 / M3 2 cards; claudemd 0/0, "
             "reproduced from stored artifacts before any new number was read).\n")

    o.append("## The six-cell factorial\n")
    o.append("| cell | n cards | M1 touched (bound) | M3 violated (bound) | any-drift | mean cost/run | churn share | mean turns | M5 majority-pass | judged met |")
    o.append("|---|---|---|---|---|---|---|---|---|---|")
    o.extend(table)

    o.append("\n## Confirmatory family (Holm as one family)\n")
    o.append("| endpoint | result | test | p |\n|---|---|---|---|")
    o.extend(lines_fam)
    if family:
        o.append("\nHolm-adjusted: " + "; ".join(f"{k}: p_adj = {v:.4f}" for k, v in adj.items()) + ".")
    if degenerate:
        o.append("Degenerate endpoints: " + "; ".join(f"{k}: {v}" for k, v in degenerate.items()) + ".")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    excl = [f"{r['run_id']} ({r['error'][:40]})" for r in conn.execute(
        "SELECT run_id, error FROM runs WHERE status='error' AND arm IN "
        "('export','vanilla-vague','claudemd-vague','export-vague')")]
    o.append("\n## Exclusions and disclosures\n")
    o.append(f"- Coding runs: {576 - len(excl)}/576 complete; {len(excl)} exclusions: "
             + "; ".join(excl) + ".")
    o.append("- Judge runs: 9 unparseable-after-one-retry across both waves (recorded, excluded).")
    o.append("- Judged metric remains secondary, κ = 0.626 carried from the Wave-1 calibration.\n")

    OUT.write_text("\n".join(o) + "\n", encoding="utf-8")
    print(f"written: {OUT}")
    for t in table:
        print(t)
    for ln in lines_fam:
        print(ln)
    for k, v in family.items():
        print(f"holm {k}: p={v:.4f} adj={adj[k]:.4f}")


if __name__ == "__main__":
    main()
