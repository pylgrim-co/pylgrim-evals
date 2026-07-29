"""E13 Stage-2 (tier-crossing) confirmatory analysis, executed strictly per
preregistration/prereg-v5-tiercross.md (frozen, tag prereg-v5-tiercross,
commit 2a9db33, public before any Stage-2 run).

Reads stored artifacts only; re-runs nothing; mutates nothing. Reuses the
Wave-1 statistical machinery (analysis/wave1_confirmatory.py) and follows the
E9/E10 pattern (analysis/e9_e10_confirmatory.py). Stage-2 rows are reps 4-6
ONLY (the prereg's mechanical fresh-data rule); no rep<=3 row enters the
confirmatory family.

REGRESSION GATE: before any Stage-2 number is computed, the published
Wave-1.5 Sonnet cells (vanilla-vague, export-vague) and the published E10
Haiku cells (vanilla-vague, export-vague) are re-derived from the same
database at reps 1-3 and asserted against results/reports/wave15-analysis-1.md
and e9-e10-analysis-1.md (M1/M3/any-drift/M5 counts and mean cost/run), and
the published E10 endpoint-3 discordance (b=13, c=0, n=48, p=0.0002) is
re-derived and asserted. The script aborts loudly on any mismatch and writes
no report.

Confirmatory family (prereg-v5-tiercross; Holm as ONE family of four; card =
unit; addendum-§7 pairing with the (arm, model) cell in the role §7 gives an
arm — per-card common Stage-2 reps r4-r6 per comparison; M5 binarization is
the pre-pinned majority-of-reps rule from prereg-v2-ext endpoint 4):
  1  M5 non-inferiority, margin -5pp   export-vague@haiku  vs vanilla-vague@sonnet   one-sided Tango score test of H0: d <= -0.05
  2  drift M1∪M3 any-drift             export-vague@haiku  vs vanilla-vague@sonnet   exact McNemar, two-sided
  3  M5 non-inferiority, margin -5pp   export-vague@sonnet vs vanilla-vague@opus     one-sided Tango score test of H0: d <= -0.05
  4  drift M1∪M3 any-drift             export-vague@sonnet vs vanilla-vague@opus     exact McNemar, two-sided
The NI claim holds iff the Holm-adjusted one-sided Tango score p < .05
(equivalently the one-sided Holm-level lower confidence bound for d lies
above -0.05); the two-sided 95% Tango score CI is reported alongside
regardless. Degenerate-case rule carried verbatim for the McNemar endpoints.
No other test is run.

Descriptive (registered as such; no tests): cost-per-completed-task per cell
(R4 CLI-modelUsage basis; "completed" = M5 pass; injection-mass decomposition
per addendum §3; cross-tier cost compares SPEND, not tokens), within-tier
packet effect on opus (cells 4 vs 5), capability-gap reference
(export-vague@haiku vs export-vague@sonnet), agent_committed counts, judged
criteria-satisfaction (secondary, kappa = 0.626, Sonnet judge across three
tiers — asymmetry disclosed).

R1-ext scrub (hugo/nushell/zod context arms), R2 junk patterns, R4 economy
basis, §7 truncation/pairing: carried verbatim from prereg-v2-ext.

Usage (from harness/):  uv run python ../analysis/e13_confirmatory.py
Writes: results/reports/e13-analysis-1.md
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness" / "src"))
sys.path.insert(0, str(ROOT / "analysis"))

from wave1_confirmatory import (  # noqa: E402
    cp_upper, holm, is_junk, mcnemar_exact,
    CACHE_WRITE_PER_MTOK, CACHE_READ_PER_MTOK, CHARS_PER_TOKEN,
)

from harness import arms, taskcards, judge  # noqa: E402
from harness.metrics import scope  # noqa: E402

RUNS_DIR = ROOT / "results" / "runs"
DB = ROOT / "results" / "runs.db"
OUT = ROOT / "results" / "reports" / "e13-analysis-1.md"

STAGE2_REPS = (4, 5, 6)   # the prereg's frozen Stage-2 rep indices
BASELINE_REPS = (1, 2, 3)  # regression-gate scope only

# The five Stage-2 cells, prereg table order.
CELLS = [("export-vague", "haiku"),
         ("vanilla-vague", "sonnet"),
         ("export-vague", "sonnet"),
         ("vanilla-vague", "opus"),
         ("export-vague", "opus")]

# The two tier-crossing rungs: (packet-equipped lower tier, raw higher tier).
RUNG1 = (("export-vague", "haiku"), ("vanilla-vague", "sonnet"))
RUNG2 = (("export-vague", "sonnet"), ("vanilla-vague", "opus"))

NI_MARGIN = -0.05  # pre-registered non-inferiority margin (-5pp)

# R1-ext: arms that materialize a workspace CLAUDE.md are context arms.
CONTEXT_ARMS = {"export-vague", "export-bare-vague", "export-enforce-vague",
                "claudemd-vague", "export", "claudemd",
                "stale-generic-vague", "stale-wrong-vague"}
TRACKED_CLAUDEMD_REPOS = {"hugo", "nushell", "zod"}

# Published Wave-1.5 values (results/reports/wave15-analysis-1.md):
# (M1 touched cards, M3 violated cards, any-drift cards, M5 majority), cost.
W15_PUBLISHED = {
    "vanilla-vague": ((7, 9, 9, 39), 0.854),
    "export-vague": ((1, 1, 1, 45), 0.754),
}
# Published E10 values (results/reports/e9-e10-analysis-1.md).
E10_PUBLISHED = {
    "vanilla-vague": ((13, 14, 14, 38), 0.458),
    "export-vague": ((0, 1, 1, 42), 0.382),
}
# Published E10 endpoint 3 (vanilla-vague vs export-vague, Haiku, reps 1-3).
E10_ENDPOINT3 = (13, 0, 48, "0.0002")

# Cache pricing per tier (USD per MTok; labeled estimates, same 1.25x-write /
# 0.1x-read house basis and 4 chars/token as Waves 1/1.5/E8/E9/E10).
# Sonnet constants imported from wave1_confirmatory (3.75 / 0.30, base $3).
HAIKU_CACHE_WRITE_PER_MTOK = 1.25   # base $1/MTok (as in e9_e10_confirmatory)
HAIKU_CACHE_READ_PER_MTOK = 0.10
OPUS_CACHE_WRITE_PER_MTOK = 6.25    # base $5/MTok (claude-opus-4-8)
OPUS_CACHE_READ_PER_MTOK = 0.50

CACHE_RATES = {
    "sonnet": (CACHE_WRITE_PER_MTOK, CACHE_READ_PER_MTOK),
    "haiku": (HAIKU_CACHE_WRITE_PER_MTOK, HAIKU_CACHE_READ_PER_MTOK),
    "opus": (OPUS_CACHE_WRITE_PER_MTOK, OPUS_CACHE_READ_PER_MTOK),
}

# Error-class notes for the missing-data table (ops attribution disclosed in
# the deviations section; classification from the drain log / error strings).
OPS_KILL_RUNS = {"zod-t05--vanilla-vague--opus--r6",
                 "click-t05--vanilla-vague--opus--r6"}


# --- small stats: Tango (1998) score test / CI for paired proportions --------

def _phi(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def tango_z(b: int, c: int, n: int, delta: float) -> float:
    """Tango score statistic for H0: p10 - p01 = delta on n pairs with
    discordant counts b (=n10) and c (=n01). Constrained MLE of p01 solves
    2N q^2 + B q + C = 0 with B = -b - c + (2N - b + c) d, C = -c d (1 - d)."""
    A = 2.0 * n
    B = -b - c + (2.0 * n - b + c) * delta
    C = -c * delta * (1.0 - delta)
    disc = B * B - 4.0 * A * C
    q = (math.sqrt(max(disc, 0.0)) - B) / (2.0 * A)
    var = n * (2.0 * q + delta * (1.0 - delta))
    num = b - c - n * delta
    if var <= 0.0:
        return math.inf if num > 0 else (-math.inf if num < 0 else 0.0)
    return num / math.sqrt(var)


def tango_one_sided_p(b: int, c: int, n: int, margin: float) -> float:
    """One-sided score p for H0: d <= margin vs H1: d > margin."""
    return 1.0 - _phi(tango_z(b, c, n, margin))


def _bisect_delta(b: int, c: int, n: int, target_z: float,
                  lo: float, hi: float) -> float:
    """Find delta in [lo, hi] with Z(delta) = target_z. Z is decreasing in
    delta; assumes Z(lo) >= target_z >= Z(hi)."""
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if tango_z(b, c, n, mid) > target_z:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def tango_ci(b: int, c: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Two-sided Tango score CI (invert |Z(d)| <= z_crit)."""
    zc = {0.95: 1.959963984540054}.get(conf)
    d_hat = (b - c) / n
    lower = _bisect_delta(b, c, n, zc, -1.0, d_hat)
    upper = _bisect_delta(b, c, n, -zc, d_hat, 1.0)
    return lower, upper


def tango_lower_bound(b: int, c: int, n: int, conf: float = 0.95) -> float:
    """One-sided score lower confidence bound for d."""
    zc = {0.95: 1.6448536269514722}.get(conf)
    return _bisect_delta(b, c, n, zc, -1.0, (b - c) / n)


# --- load --------------------------------------------------------------------

def connect_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def load() -> tuple[dict, dict, dict, sqlite3.Connection]:
    cards, errs = taskcards.load_all(ROOT / "tasks")
    assert not errs, errs
    factorial = {c.id: c for c in cards
                 if c.kind == "real" and not c.control and c.horizon == "short"}
    conn = connect_ro()
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
    return factorial, runs, judges, conn


def rid(cid: str, arm: str, model: str, rep: int) -> str:
    return f"{cid}--{arm}--{model}--r{rep}"


def churn_share(run_id: str, rec: dict, card, repo: str) -> float:
    """R1-ext (carried verbatim): on the tracked-CLAUDE.md repos, context-arm
    churn is computed on the scrubbed diff. Stored metrics stay unmutated."""
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
    """(touched, violated, passed, cost) with the R2 junk filter and the R4
    CLI-modelUsage economy basis (both carried verbatim)."""
    m = rec["metrics"]
    hp = m.get("honeypots") or {}
    touched = bool(hp.get("honeypot_touched")) and any(
        not is_junk(t.get("path", "")) for t in hp.get("touched", [])
    )
    violated = any(v.get("violated") for v in (m.get("violations") or []))
    passed = bool((m.get("outcome") or {}).get("passed"))
    cost = float(m["tokens"]["cli"].get("total_cost_usd") or 0.0)
    return touched, violated, passed, cost


def card_cell(cid: str, arm: str, model: str, reps: list[int],
              runs: dict, card, repo: str) -> dict:
    touched = violated = False
    passes, costs, churns, turns_l = [], [], [], []
    committed = 0
    for rep in reps:
        rec = runs[rid(cid, arm, model, rep)]
        t, v, p, cost = run_flags(rec)
        touched |= t
        violated |= v
        passes.append(p)
        costs.append(cost)
        churns.append(churn_share(rid(cid, arm, model, rep), rec, card, repo))
        turns_l.append(int(rec["metrics"]["tokens"]["cli"].get("num_turns") or 0))
        committed += bool(rec["metrics"].get("agent_committed"))
    return {
        "touched": touched, "violated": violated,
        "drift": touched or violated,
        "pass_majority": sum(passes) * 2 > len(passes),
        "cost": mean(costs), "churn": mean(churns), "turns": mean(turns_l),
        "committed_runs": committed, "n": len(passes),
    }


def block_usd(rendered: str, turns: float, write_rate: float, read_rate: float) -> float:
    """Injection mass of a rendered context block (labeled pricing estimate,
    same 4 chars/token basis as Waves 1/1.5/E8/E9/E10)."""
    tok = len(rendered) / CHARS_PER_TOKEN
    return (tok * write_rate + tok * max(0.0, turns - 1) * read_rate) / 1e6


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    factorial, runs, judges, conn = load()
    repo_of = {cid: cid.rsplit("-", 1)[0] for cid in factorial}

    def arm_cell_table(arm: str, model: str, rep_set) -> dict[str, dict]:
        out = {}
        for cid, card in factorial.items():
            reps = [r for r in rep_set if rid(cid, arm, model, r) in runs]
            if reps:
                out[cid] = card_cell(cid, arm, model, reps, runs, card, repo_of[cid])
        return out

    # --- REGRESSION GATE (before any Stage-2 number) -------------------------
    reg_lines: list[str] = []
    reg_failed = False

    def derive(arm: str, model: str):
        cellmap = arm_cell_table(arm, model, BASELINE_REPS)
        counts = (sum(1 for d in cellmap.values() if d["touched"]),
                  sum(1 for d in cellmap.values() if d["violated"]),
                  sum(1 for d in cellmap.values() if d["drift"]),
                  sum(1 for d in cellmap.values() if d["pass_majority"]))
        cost = mean(d["cost"] for d in cellmap.values())
        return counts, cost, len(cellmap)

    for (arm, model), pub, label in (
        (("vanilla-vague", "sonnet"), W15_PUBLISHED["vanilla-vague"], "W1.5"),
        (("export-vague", "sonnet"), W15_PUBLISHED["export-vague"], "W1.5"),
        (("vanilla-vague", "haiku"), E10_PUBLISHED["vanilla-vague"], "E10"),
        (("export-vague", "haiku"), E10_PUBLISHED["export-vague"], "E10"),
    ):
        want, want_cost = pub
        got, cost, n = derive(arm, model)
        ok = got == want and n == 48 and abs(cost - want_cost) < 0.0005
        line = (f"{arm} @ {model} ({label}, reps 1-3): M1 {got[0]}, M3 {got[1]}, "
                f"any-drift {got[2]}/{n}, M5 {got[3]}/{n}, mean cost/run ${cost:.3f} "
                f"(published: M1 {want[0]}, M3 {want[1]}, any-drift {want[2]}/48, "
                f"M5 {want[3]}/48, ${want_cost:.3f}) — "
                + ("REPRODUCES" if ok else "MISMATCH"))
        reg_lines.append(line)
        reg_failed |= not ok

    # E10 endpoint 3 discordance (reps 1-3, §7 pairing) re-derived.
    def paired(a: tuple[str, str], b: tuple[str, str], rep_set):
        out = []
        for cid, card in factorial.items():
            reps = [r for r in rep_set
                    if rid(cid, *a, r) in runs and rid(cid, *b, r) in runs]
            if not reps:
                continue
            out.append((cid,
                        card_cell(cid, a[0], a[1], reps, runs, card, repo_of[cid]),
                        card_cell(cid, b[0], b[1], reps, runs, card, repo_of[cid])))
        return out

    p3_pairs = paired(("vanilla-vague", "haiku"), ("export-vague", "haiku"),
                      BASELINE_REPS)
    b3 = sum(1 for _, x, y in p3_pairs if x["drift"] and not y["drift"])
    c3 = sum(1 for _, x, y in p3_pairs if not x["drift"] and y["drift"])
    p3 = mcnemar_exact(b3, c3)
    ep3_ok = (b3, c3, len(p3_pairs), f"{p3:.4f}") == E10_ENDPOINT3
    reg_lines.append(
        f"E10 endpoint 3 (drift, vanilla-vague vs export-vague @ haiku, reps 1-3): "
        f"b={b3}, c={c3}, n={len(p3_pairs)}, p={p3:.4f} "
        f"(published: b={E10_ENDPOINT3[0]}, c={E10_ENDPOINT3[1]}, "
        f"n={E10_ENDPOINT3[2]}, p={E10_ENDPOINT3[3]}) — "
        + ("REPRODUCES" if ep3_ok else "MISMATCH"))
    reg_failed |= not ep3_ok

    if reg_failed:
        print("REGRESSION CHECK FAILED — ABORTING BEFORE ANY STAGE-2 NUMBER; "
              "NO REPORT WRITTEN")
        for ln in reg_lines:
            print("  " + ln)
        raise SystemExit(1)
    print("Regression check PASSED (published W1.5 + E10 cells re-derived):")
    for ln in reg_lines:
        print("  " + ln)

    # --- coverage from the live db (Stage-2 = rep >= 4) ----------------------
    coverage: dict[tuple[str, str], tuple[int, int]] = {}
    for arm, model in CELLS:
        sched = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE arm=? AND model=? AND rep>=4",
            (arm, model)).fetchone()[0]
        done = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE arm=? AND model=? AND rep>=4 "
            "AND status='done'", (arm, model)).fetchone()[0]
        coverage[(arm, model)] = (sched, done)
    run_errors = [
        (r["run_id"], r["status"], int(r["attempt"] or 0), (r["error"] or "").strip())
        for r in conn.execute(
            "SELECT run_id, status, attempt, error FROM runs WHERE rep>=4 "
            "AND status!='done' ORDER BY run_id")
    ]
    pending_rows = [x for x in run_errors if x[1] in ("pending", "running")]
    preliminary = bool(pending_rows)

    # judge coverage for Stage-2 rows
    jstat = {r["run_id"]: (r["status"], (r["error"] or "").strip())
             for r in conn.execute("SELECT run_id, status, error FROM judge_runs")}
    judged: dict[tuple[str, str], tuple[int, int, int, int, int, int, int]] = {}
    judge_errors: list[tuple[str, str]] = []
    for arm, model in CELLS:
        met = nm = cj = j_done = j_total = j_err = j_pend = 0
        for cid in factorial:
            for rep in STAGE2_REPS:
                run_id_ = rid(cid, arm, model, rep)
                st = jstat.get(run_id_)
                if st is None:
                    continue
                j_total += 1
                if st[0] == "error":
                    j_err += 1
                    judge_errors.append((run_id_, st[1]))
                elif st[0] != "done":
                    j_pend += 1
                v = judges.get(run_id_)
                if not v:
                    continue
                j_done += 1
                for verdict in v:
                    met += verdict["verdict"] == "met"
                    nm += verdict["verdict"] == "not_met"
                    cj += verdict["verdict"] == "cannot_judge"
        judged[(arm, model)] = (met, nm, cj, j_done, j_total, j_err, j_pend)
    judge_errors.sort()

    # model snapshots per tier (recorded per-run by provenance, E10 convention)
    snaps: dict[str, list[str]] = {}
    for _, model in CELLS:
        if model in snaps:
            continue
        snaps[model] = sorted({
            s
            for (rid_,) in conn.execute(
                "SELECT run_id FROM runs WHERE model=? AND rep>=4 AND status='done'",
                (model,))
            for s in runs[rid_]["provenance"]["model_snapshots"]
        })

    # --- the Stage-2 cells ---------------------------------------------------
    cells = {(arm, model): arm_cell_table(arm, model, STAGE2_REPS)
             for arm, model in CELLS}

    def dcount(key):
        return sum(1 for d in cells[key].values() if d["drift"])

    def m5count(key):
        return sum(1 for d in cells[key].values() if d["pass_majority"])

    # --- confirmatory family (Holm as one family of four) --------------------
    family: dict[str, float] = {}
    degenerate: dict[str, str] = {}
    lines_fam: list[str] = []
    ni_stats: dict[str, dict] = {}
    mc_stats: dict[str, dict] = {}

    def ni_endpoint(short: str, label: str, low: tuple[str, str], high: tuple[str, str]):
        """M5 non-inferiority: d = p(low-tier+packet) - p(high-tier raw)."""
        pairs = paired(low, high, STAGE2_REPS)
        n = len(pairs)
        b = sum(1 for _, x, y in pairs if x["pass_majority"] and not y["pass_majority"])
        c = sum(1 for _, x, y in pairs if not x["pass_majority"] and y["pass_majority"])
        d_hat = (b - c) / n
        p = tango_one_sided_p(b, c, n, NI_MARGIN)
        lo2, hi2 = tango_ci(b, c, n)
        lb1 = tango_lower_bound(b, c, n)
        family[short] = p
        ni_stats[short] = {"pairs": pairs, "n": n, "b": b, "c": c, "d": d_hat,
                           "p": p, "ci": (lo2, hi2), "lb": lb1,
                           "low": low, "high": high}
        lines_fam.append(
            f"| {label} | Δ̂ = {d_hat*100:+.1f}pp (b={b} {low[0]}@{low[1]}-only-pass, "
            f"c={c} {high[0]}@{high[1]}-only-pass, n={n}); 95% Tango CI "
            f"[{lo2*100:+.1f}, {hi2*100:+.1f}]pp; one-sided 95% LB {lb1*100:+.1f}pp | "
            f"one-sided Tango score, H0: Δ ≤ −5pp | p = {p:.4f} |")

    def mc_endpoint(short: str, label: str, low: tuple[str, str], high: tuple[str, str]):
        """Drift M1∪M3 any-drift: exact McNemar, two-sided."""
        pairs = paired(low, high, STAGE2_REPS)
        n = len(pairs)
        b = sum(1 for _, x, y in pairs if x["drift"] and not y["drift"])
        c = sum(1 for _, x, y in pairs if not x["drift"] and y["drift"])
        p = mcnemar_exact(b, c)
        mc_stats[short] = {"pairs": pairs, "n": n, "b": b, "c": c, "p": p,
                           "low": low, "high": high}
        if p is None:
            degenerate[short] = (
                f"0 discordant cards of {n} → one-sided 95% bound on "
                f"discordance ≤{cp_upper(0, n)*100:.1f}%")
            lines_fam.append(
                f"| {label} | b={b}, c={c} (n={n}) | degenerate rule | "
                f"bound ≤{cp_upper(0, n)*100:.1f}% |")
        else:
            family[short] = p
            lines_fam.append(
                f"| {label} | b={b} ({low[0]}@{low[1]}-only-drift), "
                f"c={c} ({high[0]}@{high[1]}-only-drift), n={n} | "
                f"exact McNemar, two-sided | p = {p:.4f} |")

    ni_endpoint("1 · M5 NI haiku→sonnet",
                "1 · M5 non-inferiority (−5pp), export-vague@haiku vs vanilla-vague@sonnet",
                *RUNG1)
    mc_endpoint("2 · drift haiku→sonnet",
                "2 · drift M1∪M3, export-vague@haiku vs vanilla-vague@sonnet",
                *RUNG1)
    ni_endpoint("3 · M5 NI sonnet→opus",
                "3 · M5 non-inferiority (−5pp), export-vague@sonnet vs vanilla-vague@opus",
                *RUNG2)
    mc_endpoint("4 · drift sonnet→opus",
                "4 · drift M1∪M3, export-vague@sonnet vs vanilla-vague@opus",
                *RUNG2)

    adj = holm(family) if family else {}

    def ni_holds(short: str) -> bool:
        return adj.get(short, 1.0) < 0.05

    def mc_sig(short: str) -> bool:
        return short in family and adj.get(short, 1.0) < 0.05

    # --- descriptives --------------------------------------------------------
    # Cost-per-completed-task per cell (R4 basis; completed = M5-passing run),
    # with the mandatory injection-mass decomposition.
    rendered = {cid: arms.render_exported_claude_md(c)
                for cid, c in factorial.items()}
    econ_rows = []
    econ_cells: dict[tuple[str, str], dict] = {}
    for arm, model in CELLS:
        wr, rr = CACHE_RATES[model]
        total = passed_runs = nruns = 0
        inj_total = 0.0
        for cid in factorial:
            for rep in STAGE2_REPS:
                run_id_ = rid(cid, arm, model, rep)
                rec = runs.get(run_id_)
                if rec is None:
                    continue
                nruns += 1
                _, _, p_, cost = run_flags(rec)
                total += cost
                passed_runs += p_
                if arm.startswith("export"):
                    turns = int(rec["metrics"]["tokens"]["cli"].get("num_turns") or 1)
                    inj_total += block_usd(rendered[cid], turns, wr, rr)
        cpc = total / passed_runs if passed_runs else float("nan")
        mean_cost = total / nruns
        mean_inj = inj_total / nruns
        econ_cells[(arm, model)] = {"mean_cost": mean_cost, "mean_inj": mean_inj,
                                    "cpc": cpc, "passed_runs": passed_runs,
                                    "nruns": nruns, "total": total}
        econ_rows.append(
            f"| {arm} @ {model} | ${mean_cost:.3f} (inj ${mean_inj:.4f}, "
            f"behavioral ${mean_cost - mean_inj:.3f}) | {passed_runs}/{nruns} | "
            f"${cpc:.3f} |")

    # Cross-tier SPEND deltas over §7-paired cards (descriptive).
    def econ_delta(low, high):
        pairs = paired(low, high, STAGE2_REPS)
        wr, rr = CACHE_RATES[low[1]]
        deltas, inj_d = [], []
        for cid, x, y in pairs:
            deltas.append(x["cost"] - y["cost"])
            inj_d.append(block_usd(rendered[cid], x["turns"], wr, rr))
        return mean(deltas), mean(inj_d), len(pairs)

    d1, inj1, n1 = econ_delta(*RUNG1)
    d2, inj2, n2 = econ_delta(*RUNG2)

    # Within-tier packet effect on opus (cells 4 vs 5; descriptive bounds).
    ow = cells[("vanilla-vague", "opus")]
    ox = cells[("export-vague", "opus")]
    opus_pairs = paired(("export-vague", "opus"), ("vanilla-vague", "opus"),
                        STAGE2_REPS)
    ob = sum(1 for _, x, y in opus_pairs if x["drift"] and not y["drift"])
    oc = sum(1 for _, x, y in opus_pairs if not x["drift"] and y["drift"])
    ob5 = sum(1 for _, x, y in opus_pairs if x["pass_majority"] and not y["pass_majority"])
    oc5 = sum(1 for _, x, y in opus_pairs if not x["pass_majority"] and y["pass_majority"])

    # Capability-gap reference: export-vague@haiku vs export-vague@sonnet.
    cap_pairs = paired(("export-vague", "haiku"), ("export-vague", "sonnet"),
                       STAGE2_REPS)
    cap_b5 = sum(1 for _, x, y in cap_pairs if x["pass_majority"] and not y["pass_majority"])
    cap_c5 = sum(1 for _, x, y in cap_pairs if not x["pass_majority"] and y["pass_majority"])

    committed = {key: sum(d["committed_runs"] for d in cells[key].values())
                 for key in cells}

    # per-cell truncated cards (fewer than 3 Stage-2 reps) for disclosure
    trunc: dict[tuple[str, str], list[str]] = {}
    for arm, model in CELLS:
        short_cards = []
        for cid in factorial:
            have = [r for r in STAGE2_REPS if rid(cid, arm, model, r) in runs]
            if len(have) < 3:
                short_cards.append(f"{cid} (reps {have})")
        trunc[(arm, model)] = short_cards

    # --- cell table ----------------------------------------------------------
    def table_row(arm: str, model: str) -> str:
        ids = cells[(arm, model)]
        n = len(ids)
        kt = sum(1 for d in ids.values() if d["touched"])
        kv = sum(1 for d in ids.values() if d["violated"])
        kd = sum(1 for d in ids.values() if d["drift"])
        cost = mean(d["cost"] for d in ids.values())
        churn = mean(d["churn"] for d in ids.values())
        turns = mean(d["turns"] for d in ids.values())
        mp = sum(1 for d in ids.values() if d["pass_majority"])
        met, nm, cj, j_done, j_total, _, _ = judged[(arm, model)]
        tot = met + nm + cj
        jshare = (f"{met/tot*100:.1f}% ({j_done}/{j_total} judged)" if tot
                  else f"- (0/{j_total} judged)")
        return (f"| {arm} | {model} | {n} | {kt} (≤{cp_upper(kt, n)*100:.1f}%) | "
                f"{kv} (≤{cp_upper(kv, n)*100:.1f}%) | {kd} | ${cost:.3f} | "
                f"{churn:.3f} | {turns:.1f} | {mp}/{n} | "
                f"{committed[(arm, model)]} | {jshare} |")

    # --- plain-English readings ----------------------------------------------
    readings: list[str] = []
    s1 = ni_stats["1 · M5 NI haiku→sonnet"]
    s3 = ni_stats["3 · M5 NI sonnet→opus"]
    m2 = mc_stats["2 · drift haiku→sonnet"]
    m4 = mc_stats["4 · drift sonnet→opus"]

    def ni_reading(short, s, low_name, high_name):
        holds = ni_holds(short)
        return (
            f"M5 {m5count(s['low'])}/{len(cells[s['low']])} for {low_name} vs "
            f"{m5count(s['high'])}/{len(cells[s['high']])} for {high_name}; paired "
            f"Δ̂ = {s['d']*100:+.1f}pp (95% Tango CI {s['ci'][0]*100:+.1f} to "
            f"{s['ci'][1]*100:+.1f}pp). "
            + (f"The Holm-adjusted one-sided p ({adj[short]:.4f}) is below .05, so "
               f"the one-sided Holm-level lower bound for Δ lies above −5pp: "
               f"**non-inferiority HOLDS** at this rung."
               if holds else
               f"The Holm-adjusted one-sided p ({adj[short]:.4f}) is not below .05 "
               f"— the CI does not exclude the −5pp margin: **non-inferiority is "
               f"NOT established** at this rung, and the tier-crossing claim dies "
               f"at this boundary (published as-is, per the prereg)."))

    def mc_reading(short, m, low_name, high_name):
        if m["p"] is None:
            return (f"No discordant cards of {m['n']}; only the pre-specified "
                    f"bound is reported ({degenerate[short]}).")
        sig = mc_sig(short)
        direction = ("the packet-equipped lower tier drifts LESS"
                     if m["c"] > m["b"] else
                     "the packet-equipped lower tier drifts MORE")
        return (
            f"Drift {dcount(m['low'])}/{len(cells[m['low']])} for {low_name} vs "
            f"{dcount(m['high'])}/{len(cells[m['high']])} for {high_name}; "
            f"discordance b={m['b']} ({low_name}-only) vs c={m['c']} "
            f"({high_name}-only). "
            + (f"Survives Holm (p_adj = {adj[short]:.4f}): {direction} than the "
               f"raw next tier up — **drift superiority "
               f"{'CONFIRMED' if m['c'] > m['b'] else 'REVERSED (awkward direction)'}**."
               if sig else
               f"Not significant after Holm (p_adj = {adj.get(short, 1.0):.4f}): "
               f"no confirmed drift difference at this rung."))

    readings.append("**Endpoint 1 (M5 non-inferiority, haiku→sonnet):** "
                    + ni_reading("1 · M5 NI haiku→sonnet", s1,
                                 "export-vague@haiku", "vanilla-vague@sonnet"))
    readings.append("**Endpoint 2 (drift, haiku→sonnet):** "
                    + mc_reading("2 · drift haiku→sonnet", m2,
                                 "export-vague@haiku", "vanilla-vague@sonnet"))
    readings.append("**Endpoint 3 (M5 non-inferiority, sonnet→opus):** "
                    + ni_reading("3 · M5 NI sonnet→opus", s3,
                                 "export-vague@sonnet", "vanilla-vague@opus"))
    readings.append("**Endpoint 4 (drift, sonnet→opus):** "
                    + mc_reading("4 · drift sonnet→opus", m4,
                                 "export-vague@sonnet", "vanilla-vague@opus"))

    rung1_ok = ni_holds("1 · M5 NI haiku→sonnet") and mc_sig("2 · drift haiku→sonnet") \
        and m2["c"] > m2["b"]
    rung2_ok = ni_holds("3 · M5 NI sonnet→opus") and mc_sig("4 · drift sonnet→opus") \
        and m4["c"] > m4["b"]

    # --- write ---------------------------------------------------------------
    prelim_tag = " (PRELIMINARY)" if preliminary else ""
    o: list[str] = []
    o.append(f"# E13 Stage-2 tier-crossing confirmatory analysis · report 1{prelim_tag}\n")
    o.append("Executed per `preregistration/prereg-v5-tiercross.md` (frozen, tag "
             "`prereg-v5-tiercross`, commit 2a9db33, committed/tagged/pushed "
             "before any Stage-2 row was appended). Five fresh cells, 48 short "
             "T-real cards, vague-prompt row, Stage-2 reps r4-r6 ONLY (the "
             "prereg's mechanical fresh-data rule; no Wave-1.5/E10/Stage-1 run "
             "enters the family): `export-vague`@haiku, `vanilla-vague`@sonnet, "
             "`export-vague`@sonnet, `vanilla-vague`@opus, `export-vague`@opus. "
             "Model snapshots as recorded per-run by provenance (E10 "
             "convention; the union per tier — the CLI also invokes an "
             "auxiliary Haiku model inside sonnet/opus runs, so that snapshot "
             "appears in their unions too): "
             + "; ".join(f"{m}: {', '.join(snaps[m])}" for m in ("haiku", "sonnet", "opus"))
             + ". The opus alias resolved to `claude-opus-4-8`, matching the "
             "prereg's smoke disclosure. Card = unit; pairing per-comparison per-card common Stage-2 "
             "reps (addendum §7 carried verbatim, the (arm, model) cell in the "
             "role §7 gives an arm). M5 binarization is the pre-pinned "
             "majority-of-reps rule (prereg-v2-ext endpoint 4). R1-ext scrub on "
             "hugo/nushell/zod context arms, R2 junk filter, R4 CLI-modelUsage "
             "economy basis, degenerate-case rule: carried verbatim from "
             "prereg-v2-ext. Vague artifact unchanged "
             "(`tasks/vague/vague-prompts-v1.yaml`, sha 2e41d3aa…); vendored "
             "exporter pylgrim-repo 00ff5a1. Judged metric secondary (κ = 0.626 "
             "from the Wave-1 calibration; the same Sonnet judge scores haiku, "
             "sonnet AND opus agents — the same-judge-different-agent asymmetry "
             "now spans three tiers, disclosed wherever judged numbers appear). "
             "Database read-only (`mode=ro`, busy timeout); nothing re-run or "
             "mutated.\n")
    o.append("**Hypothesis source (disclosed):** the Stage-1 exploratory peek in "
             "`e9-e10-analysis-1.md` (haiku→sonnet direction only; sonnet→opus "
             "was unpeeked). Stage 2 confirms or kills on this fresh data alone; "
             "either outcome publishes with the same prominence.\n")
    if preliminary:
        o.append("**PRELIMINARY:** pending/running row(s) exist: "
                 + "; ".join(f"`{r}` ({s})" for r, s, _, _ in pending_rows) + ".\n")

    o.append("## Regression check (gate, computed before any Stage-2 number)\n")
    o.append("Published Wave-1.5 and E10 cells (and the published E10 "
             "endpoint-3 discordance) re-derived from the same database at reps "
             "1-3 and asserted against `wave15-analysis-1.md` / "
             "`e9-e10-analysis-1.md`: **PASSED**.\n")
    for ln in reg_lines:
        o.append(f"- {ln}")

    o.append("\n## Coverage (scheduled / done / judged per cell)\n")
    o.append("| cell | scheduled | done | runs judged | judge errors |")
    o.append("|---|---|---|---|---|")
    total_sched = total_done = total_judged = 0
    for arm, model in CELLS:
        sched, done = coverage[(arm, model)]
        _, _, _, j_done, j_total, j_err, _ = judged[(arm, model)]
        total_sched += sched
        total_done += done
        total_judged += j_done
        o.append(f"| {arm} @ {model} | {sched} | {done} | {j_done}/{j_total} | {j_err} |")
    o.append(f"| **total** | {total_sched} | {total_done} | {total_judged} | "
             f"{len(judge_errors)} |")

    o.append("\n## The cells (48 short T-real cards, vague prompts, Stage-2 reps r4-r6)\n")
    o.append("| cell | model | n cards | M1 touched (bound) | M3 violated (bound) | "
             "any-drift | mean cost/run | churn share | mean turns | "
             "M5 majority-pass | agent_committed runs | judged met |")
    o.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for arm, model in CELLS:
        o.append(table_row(arm, model))
    o.append("\nBounds are one-sided exact Clopper-Pearson 95%. Cost is NOT "
             "comparable across tiers on a per-token basis — the cross-tier "
             "economy comparison below compares SPEND, not tokens (different "
             "per-token pricing); that asymmetry is the commercial point and is "
             "stated wherever the number appears.\n")

    o.append("## Confirmatory family (prereg-v5-tiercross; Holm as ONE family of four)\n")
    o.append("| endpoint | result | test | p |\n|---|---|---|---|")
    o.extend(lines_fam)
    if family:
        o.append("\nHolm-adjusted: " + "; ".join(
            f"{k}: p_adj = {adj[k]:.4f}" for k in sorted(family, key=lambda k: family[k]))
            + ".")
    if degenerate:
        o.append("Degenerate endpoints (pre-specified rule, no improvised "
                 "statistic): " + "; ".join(f"{k}: {v}" for k, v in degenerate.items()) + ".")
    o.append("\nNon-inferiority decision rule as frozen: the claim holds iff the "
             "Holm-adjusted one-sided Tango score p < .05 — equivalently the "
             "one-sided Holm-level lower confidence bound for Δ lies above "
             "−0.05. The two-sided 95% Tango score CIs above are reported "
             "regardless. Any improvement beyond non-inferiority is exploratory, "
             "not claimed as confirmed (prereg-v1 H3 language carried over).\n")

    o.append("### Plain-English readings\n")
    for r_ in readings:
        o.append(f"- {r_}")

    o.append("\n## Descriptives (registered as such; no tests run)\n")
    o.append("### Cost-per-completed-task (R4 CLI-modelUsage basis; "
             "completed = M5-passing run)\n")
    o.append("Injection-mass decomposition per addendum §3 (labeled estimates at "
             f"{CHARS_PER_TOKEN:.0f} chars/token; cache-write/read USD per MTok — "
             f"Sonnet {CACHE_WRITE_PER_MTOK}/{CACHE_READ_PER_MTOK}, Haiku "
             f"{HAIKU_CACHE_WRITE_PER_MTOK}/{HAIKU_CACHE_READ_PER_MTOK}, Opus "
             f"{OPUS_CACHE_WRITE_PER_MTOK}/{OPUS_CACHE_READ_PER_MTOK}; the Opus "
             "constants are new this analysis — base $5/MTok input for "
             "`claude-opus-4-8` at the house 1.25×-write / 0.1×-read basis — and "
             "are labeled estimates, used only in this descriptive section):\n")
    o.append("| cell | mean cost/run (decomposition) | completed runs | "
             "cost per completed task |")
    o.append("|---|---|---|---|")
    o.extend(econ_rows)
    o.append("\nThis table is run-weighted (all done Stage-2 runs of the "
             "cell); the cell table above is card-weighted (mean of per-card "
             "means), so the two mean-cost columns can differ in the third "
             "decimal.")
    o.append("\n### Cross-tier spend (the tier-crossing economics; SPEND, not tokens)\n")
    o.append(f"- **haiku+export − sonnet+vanilla**: Δ = {d1:+.4f} USD/run over "
             f"{n1} §7-paired cards (export-block injection mass at Haiku "
             f"pricing {inj1:+.4f}; behavioral residual {d1 - inj1:+.4f}). "
             "Cross-tier cost compares spend, not tokens — different per-token "
             "pricing; that asymmetry is the commercial point.")
    o.append(f"- **sonnet+export − opus+vanilla**: Δ = {d2:+.4f} USD/run over "
             f"{n2} §7-paired cards (export-block injection mass at Sonnet "
             f"pricing {inj2:+.4f}; behavioral residual {d2 - inj2:+.4f}). "
             "Same spend-not-tokens caveat.")
    o.append("\n### Within-tier packet effect on opus (cells 4 vs 5; descriptive)\n")
    o.append(f"- Drift: vanilla-vague@opus {dcount(('vanilla-vague', 'opus'))}/"
             f"{len(ow)} (bound ≤{cp_upper(dcount(('vanilla-vague', 'opus')), len(ow))*100:.1f}%) "
             f"vs export-vague@opus {dcount(('export-vague', 'opus'))}/{len(ox)} "
             f"(bound ≤{cp_upper(dcount(('export-vague', 'opus')), len(ox))*100:.1f}%); "
             f"discordance {ob} export-only vs {oc} vanilla-only "
             f"(n={len(opus_pairs)}). No test registered; none run.")
    vv_o_fail = len(ow) - m5count(("vanilla-vague", "opus"))
    xv_o_fail = len(ox) - m5count(("export-vague", "opus"))
    o.append(f"- M5: vanilla-vague@opus {m5count(('vanilla-vague', 'opus'))}/{len(ow)} "
             f"(fail {vv_o_fail}/{len(ow)}, bound ≤{cp_upper(vv_o_fail, len(ow))*100:.1f}%) "
             f"vs export-vague@opus {m5count(('export-vague', 'opus'))}/{len(ox)} "
             f"(fail {xv_o_fail}/{len(ox)}, bound ≤{cp_upper(xv_o_fail, len(ox))*100:.1f}%); "
             f"discordance {ob5} export-only-pass vs {oc5} vanilla-only-pass.")
    o.append("\n### Capability-gap reference (packet held fixed; descriptive)\n")
    o.append(f"- export-vague@haiku vs export-vague@sonnet: drift "
             f"{dcount(('export-vague', 'haiku'))}/{len(cells[('export-vague', 'haiku')])} vs "
             f"{dcount(('export-vague', 'sonnet'))}/{len(cells[('export-vague', 'sonnet')])}; "
             f"M5 {m5count(('export-vague', 'haiku'))}/{len(cells[('export-vague', 'haiku')])} vs "
             f"{m5count(('export-vague', 'sonnet'))}/{len(cells[('export-vague', 'sonnet')])} "
             f"(discordance {cap_b5} haiku-only-pass vs {cap_c5} sonnet-only-pass, "
             f"n={len(cap_pairs)}); mean cost/run "
             f"${econ_cells[('export-vague', 'haiku')]['mean_cost']:.3f} vs "
             f"${econ_cells[('export-vague', 'sonnet')]['mean_cost']:.3f} "
             "(spend, not tokens).")
    o.append("\n### agent_committed runs per cell (E10 convention)\n")
    o.append("- " + "; ".join(f"{arm}@{model}: {committed[(arm, model)]}"
                              for arm, model in CELLS) + ".")

    o.append("\n## Judged metric (secondary; κ = 0.626)\n")
    for arm, model in CELLS:
        met, nm, cj, j_done, j_total, j_err, _ = judged[(arm, model)]
        tot = met + nm + cj
        share = f"{met/tot*100:.1f}%" if tot else "-"
        o.append(f"- {arm}@{model}: {share} met ({met}/{tot} verdicts; "
                 f"{j_done}/{j_total} runs judged"
                 + (f"; {j_err} run(s) excluded — judge reply unparseable after "
                    "one retry, the recorded exclusion class" if j_err else "")
                 + ")")
    o.append("\nκ = 0.626 carries from the Wave-1 calibration. The same Sonnet "
             "judge scores haiku, sonnet AND opus agents — the same-judge-"
             "different-agent asymmetry now spans three tiers and applies to "
             "every judged number above (disclosed per prereg).\n")

    o.append("## Missing data (the 17 affected rows)\n")
    o.append("Missing-data handling: the prereg carries addendum §7 verbatim — "
             "each comparison uses per-card common Stage-2 reps across its two "
             "cells (complete-case at the rep level; a card drops from a "
             "comparison only when NO common rep exists). No imputation. "
             "Judged secondary is complete-case over judged runs (errored judge "
             "rows are the recorded exclusion class, per the E8/E9/E10 "
             "precedent).\n")
    o.append("### 9 coding-run errors (permanent after the retry sweep)\n")
    o.append("| run | class | error |")
    o.append("|---|---|---|")
    for run_id_, status_, attempt_, err_ in run_errors:
        if "timed out" in err_:
            cls = "double timeout (attempt 2, 1800s)"
        elif run_id_ in OPS_KILL_RUNS:
            cls = "ops-caused kill (NOT a model failure)"
        else:
            cls = "crash (claude exited abnormally)"
        o.append(f"| `{run_id_}` | {cls} | {err_[:70]} |")
    o.append("\n### 8 judge-run errors (recorded exclusion class)\n")
    for run_id_, err_ in judge_errors:
        o.append(f"- `{run_id_}`: {err_}")
    o.append("\n### §7 truncation consequences\n")
    o.append(f"- Endpoints 1-2 (haiku→sonnet): n = {s1['n']} cards with ≥1 "
             "common Stage-2 rep"
             + (" — `hugo-t05` drops entirely (all three vanilla-vague@sonnet "
                "Stage-2 reps are permanent timeouts)." if s1["n"] < 48 else "."))
    o.append(f"- Endpoints 3-4 (sonnet→opus): n = {s3['n']} cards with ≥1 "
             "common Stage-2 rep.")
    for arm, model in CELLS:
        if trunc[(arm, model)]:
            o.append(f"- {arm}@{model} cards below 3 Stage-2 reps: "
                     + "; ".join(trunc[(arm, model)]) + ".")

    o.append("\n## Deviations from the prereg\n")
    o.append("- **None in the analysis plan**: endpoints, margins, pairing, "
             "binarization, Holm family, degenerate rule, and shared R-rules are "
             "executed exactly as frozen.")
    o.append("- **Coverage shortfall, disclosed**: 711/720 scheduled runs "
             "completed; 9 permanent run errors and 8 judge errors are itemized "
             "above and handled by the frozen §7 rule (complete-case), not "
             "imputed. 2 of the 9 run errors "
             "(`zod-t05--vanilla-vague--opus--r6`, "
             "`click-t05--vanilla-vague--opus--r6`, both `git rev-parse HEAD "
             "failed`) were caused by an operational kill of the worker "
             "process, NOT by model behavior — they are excluded as "
             "environment losses, and their cards pair on the surviving common "
             "reps.")
    o.append("- **Opus injection-pricing constants** (cache-write $"
             f"{OPUS_CACHE_WRITE_PER_MTOK}/MTok, cache-read $"
             f"{OPUS_CACHE_READ_PER_MTOK}/MTok) were not in the prereg (which "
             "froze no pricing table); they are labeled estimates on the house "
             "basis, used only in the descriptive economy section — never in "
             "the confirmatory family.")
    o.append("- **Tango implementation**: the prereg names the test; the "
             "constrained-MLE score statistic (Tango 1998) is implemented "
             "pure-python in `analysis/e13_confirmatory.py` (quadratic "
             "constrained MLE; verified to reduce to McNemar's z at Δ = 0).\n")

    o.append("## Honest-outcome statement\n")
    sig = [k for k in family if adj.get(k, 1.0) < 0.05]
    nsig = [k for k in family if adj.get(k, 1.0) >= 0.05]
    o.append(f"Of the four registered endpoints, {len(sig)} survive(s) Holm at "
             "0.05" + (f" ({'; '.join(sorted(sig))})" if sig else "")
             + (f"; not confirmed: {'; '.join(sorted(nsig))}" if nsig else "")
             + (f"; degenerate: {'; '.join(degenerate)}" if degenerate else "")
             + ". H-E13 (packet-equipped lower tier non-inferior on task "
             "success AND superior on drift at both boundaries): "
             + ("**the haiku→sonnet boundary lands in full**"
                if rung1_ok else "**the haiku→sonnet boundary does NOT land in full**")
             + "; "
             + ("**the sonnet→opus boundary lands in full**"
                if rung2_ok else "**the sonnet→opus boundary does NOT land in full**")
             + ". Where a boundary fails, the tier-crossing marketing claim "
             "dies at that boundary, published with the same prominence as a "
             "success (frozen language). Stage 3 (external benchmark flank) is "
             "gated on this family per docs/10 §9.\n")

    o.append("## Claim scoping (binding)\n")
    o.append("These are statements about ONE exported context packet (vendored "
             "exporter pylgrim-repo 00ff5a1) on ONE corpus (48 short T-real "
             "cards, vague-prompt row) at one moment, across three specific "
             "model snapshots. Non-inferiority is claimed only where the Holm-"
             "level bound clears the −5pp margin; any improvement beyond "
             "non-inferiority is exploratory. Nothing here measures real "
             "enforcement, multi-turn accumulation, or external benchmarks "
             "(Stage 3). Cross-tier economy figures compare spend, not tokens.\n")

    OUT.write_text("\n".join(o) + "\n", encoding="utf-8")
    print(f"\nwritten: {OUT}")
    print("\ncells:")
    for arm, model in CELLS:
        print(table_row(arm, model))
    print("\nfamily:")
    for ln in lines_fam:
        print(ln)
    for k in sorted(family, key=lambda k: family[k]):
        print(f"holm {k}: p={family[k]:.4f} adj={adj[k]:.4f}")
    for k, v in degenerate.items():
        print(f"degenerate {k}: {v}")
    print(f"\nrung1 (haiku→sonnet) lands in full: {rung1_ok}")
    print(f"rung2 (sonnet→opus) lands in full: {rung2_ok}")
    print("\neconomy (descriptive):")
    print(f"  haiku+export - sonnet+vanilla: {d1:+.4f} (inj {inj1:+.4f}) n={n1}")
    print(f"  sonnet+export - opus+vanilla: {d2:+.4f} (inj {inj2:+.4f}) n={n2}")
    print("coverage: " + ", ".join(
        f"{a}@{m} {coverage[(a, m)][1]}/{coverage[(a, m)][0]}" for a, m in CELLS))
    if preliminary:
        print("STATUS: PRELIMINARY (pending rows in the live sweep)")


if __name__ == "__main__":
    main()
