"""E9 (mode-tag authority) + E10 (tier replication) confirmatory analysis,
executed strictly per preregistration/prereg-v4-render.md (frozen, tag
prereg-v4-render, commit 6c2af0e, public before any E9/E10 confirmatory run).

Reads stored artifacts only; re-runs nothing; mutates nothing. Reuses the
Wave-1 statistical machinery (analysis/wave1_confirmatory.py) and follows
the E8 pattern (analysis/e8_confirmatory.py). Baselines are the already-run
Wave-1.5 Sonnet cells `vanilla-vague` and `export-vague`.

REGRESSION GATE: before any E9/E10 number is computed, the published
Wave-1.5 cells (vanilla-vague, export-vague; Sonnet) and the published E8
`stale-wrong-vague` cell are re-derived from the same database and asserted
against results/reports/wave15-analysis-1.md and e8-analysis-1.md. The
script aborts loudly on mismatch. `stale-generic-vague` was 142/144 at the
E8 report and is now complete after retries, so it is RECOMPUTED at full
coverage and compared (disclosed, not asserted).

Confirmatory family (prereg-v4-render, Holm as ONE family across E9+E10,
card = unit, addendum-§7 per-comparison per-card common-rep pairing):
  1  drift M1∪M3 any-drift  export-bare-vague vs export-enforce-vague  exact McNemar (Sonnet)
  2  drift M1∪M3 any-drift  export-vague vs export-enforce-vague       exact McNemar (Sonnet)
  3  drift M1∪M3 any-drift  vanilla-vague vs export-vague              exact McNemar (HAIKU)
Bare-vs-observe, M5, economy, judged: DESCRIPTIVE. PATH_CAP probe:
descriptive stratification of all export-cell results by <=8 vs >8
scope_paths. Tier interaction (Sonnet vs Haiku effect): descriptive.
agent_committed counts reported per Haiku cell.
Degenerate rule, R1-ext scrub (hugo/nushell/zod), R2 junk patterns, R4
economy basis, §7 truncation: carried verbatim from prereg-v2-ext.
Injection-mass decomposition accompanies every economy delta shown.

ALSO: the E13 Stage-1 exploratory readout (registered docs/10 §9 in the
venture repo) — hypothesis-generating ONLY, cross-tier descriptive deltas
on the shared 48 cards; no confirmatory statistics in that section.

Usage (from harness/):  uv run python ../analysis/e9_e10_confirmatory.py
Writes: results/reports/e9-e10-analysis-1.md
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
    cp_upper, holm, is_junk, mcnemar_exact,
    CACHE_WRITE_PER_MTOK, CACHE_READ_PER_MTOK, CHARS_PER_TOKEN,
)

from harness import arms, taskcards, judge  # noqa: E402
from harness.metrics import scope  # noqa: E402

RUNS_DIR = ROOT / "results" / "runs"
DB = ROOT / "results" / "runs.db"
OUT = ROOT / "results" / "reports" / "e9-e10-analysis-1.md"

# (arm, model) cells this analysis touches.
E9_CELLS = ("export-bare-vague", "export-vague", "export-enforce-vague")  # Sonnet
E10_CELLS = ("vanilla-vague", "export-vague")                             # Haiku
SONNET_ROW = ("vanilla-vague", "export-vague",
              "export-bare-vague", "export-enforce-vague")
# R1-ext: every arm that materializes a workspace CLAUDE.md is a context arm.
CONTEXT_ARMS = {"export-vague", "export-bare-vague", "export-enforce-vague",
                "claudemd-vague", "export", "claudemd",
                "stale-generic-vague", "stale-wrong-vague"}
TRACKED_CLAUDEMD_REPOS = {"hugo", "nushell", "zod"}

# Published Wave-1.5 values (results/reports/wave15-analysis-1.md):
# (M1 touched cards, M3 violated cards, any-drift cards, M5 majority).
W15_PUBLISHED = {
    "vanilla-vague": (7, 9, 9, 39),
    "export-vague": (1, 1, 1, 45),
}
# Published E8 values (results/reports/e8-analysis-1.md). stale-wrong-vague
# was complete (144/144) at publication and is asserted; stale-generic-vague
# was 142/144 at the PRELIMINARY issue and is recomputed at full coverage
# (disclosed). e8-analysis-1.md was finalized 2026-07-22 at 144/144 with the
# _FINAL values below, which are now asserted too.
E8_PUBLISHED_STALE_WRONG = (6, 6, 6, 30)
E8_PUBLISHED_STALE_GENERIC_AT_142 = (0, 0, 0, 43)
E8_PUBLISHED_STALE_GENERIC_FINAL = (0, 1, 1, 44)

# Haiku 4.5 cache pricing (USD per MTok; labeled estimate, same 4 chars/token
# basis as the Sonnet constants in wave1_confirmatory).
HAIKU_CACHE_WRITE_PER_MTOK = 1.25
HAIKU_CACHE_READ_PER_MTOK = 0.10

# The exporter's path-list cap (harness/src/harness/vendor/export_claudemd.py).
PATH_CAP = 8


def connect_ro() -> sqlite3.Connection:
    """Judge drain may be live: open read-only with a busy timeout; never
    write."""
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
    """R1-ext (carried over): on the tracked-CLAUDE.md repos, context-arm
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
    CLI-modelUsage economy basis (both carried over verbatim)."""
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


def common_reps(cid: str, a: tuple[str, str], b: tuple[str, str], runs: dict) -> list[int]:
    """Addendum §7 carried over: per-comparison per-card common reps.
    a and b are (arm, model) pairs."""
    return [r for r in (1, 2, 3)
            if rid(cid, *a, r) in runs and rid(cid, *b, r) in runs]


def block_usd(rendered: str, turns: float, write_rate: float, read_rate: float) -> float:
    """Injection mass of a rendered context block (labeled pricing estimate,
    same basis as Waves 1/1.5/E8)."""
    tok = len(rendered) / CHARS_PER_TOKEN
    return (tok * write_rate + tok * max(0.0, turns - 1) * read_rate) / 1e6


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    factorial, runs, judges, conn = load()
    repo_of = {cid: cid.rsplit("-", 1)[0] for cid in factorial}

    def arm_cell_table(arm: str, model: str) -> dict[str, dict]:
        out = {}
        for cid, card in factorial.items():
            reps = [r for r in (1, 2, 3) if rid(cid, arm, model, r) in runs]
            if reps:
                out[cid] = card_cell(cid, arm, model, reps, runs, card, repo_of[cid])
        return out

    # --- REGRESSION GATE (before any E9/E10 number) --------------------------
    reg_lines: list[str] = []

    def derive4(arm: str, model: str) -> tuple[tuple[int, int, int, int], int]:
        cellmap = arm_cell_table(arm, model)
        return (
            (sum(1 for d in cellmap.values() if d["touched"]),
             sum(1 for d in cellmap.values() if d["violated"]),
             sum(1 for d in cellmap.values() if d["drift"]),
             sum(1 for d in cellmap.values() if d["pass_majority"])),
            len(cellmap),
        )

    for arm, want in W15_PUBLISHED.items():
        got, n = derive4(arm, "sonnet")
        line = (f"{arm} (Sonnet, W1.5): M1 {got[0]}, M3 {got[1]}, any-drift {got[2]}/{n}, "
                f"M5 {got[3]}/{n} (published: M1 {want[0]}, M3 {want[1]}, "
                f"any-drift {want[2]}/48, M5 {want[3]}/48)")
        reg_lines.append(line)
        if got != want or n != 48:
            print("REGRESSION CHECK FAILED — ABORTING BEFORE ANY E9/E10 NUMBER")
            print("  " + line)
            raise SystemExit(1)
    got_sw, n_sw = derive4("stale-wrong-vague", "sonnet")
    want_sw = E8_PUBLISHED_STALE_WRONG
    line = (f"stale-wrong-vague (Sonnet, E8): M1 {got_sw[0]}, M3 {got_sw[1]}, "
            f"any-drift {got_sw[2]}/{n_sw}, M5 {got_sw[3]}/{n_sw} "
            f"(published: M1 {want_sw[0]}, M3 {want_sw[1]}, any-drift {want_sw[2]}/48, "
            f"M5 {want_sw[3]}/48)")
    reg_lines.append(line)
    if got_sw != want_sw or n_sw != 48:
        print("REGRESSION CHECK FAILED — ABORTING BEFORE ANY E9/E10 NUMBER")
        print("  " + line)
        raise SystemExit(1)
    # stale-generic-vague: recomputed at full post-retry coverage, compared
    # (not asserted — the published value was at 142/144).
    got_sg, n_sg = derive4("stale-generic-vague", "sonnet")
    sg_done = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE arm='stale-generic-vague' AND model='sonnet' "
        "AND status='done' AND rep<=3").fetchone()[0]
    want_sg = E8_PUBLISHED_STALE_GENERIC_AT_142
    sg_match = got_sg == want_sg
    sg_line = (f"stale-generic-vague (Sonnet, E8, RECOMPUTED at {sg_done}/144 after "
               f"retries; PRELIMINARY issue published at 142/144): M1 {got_sg[0]}, "
               f"M3 {got_sg[1]}, "
               f"any-drift {got_sg[2]}/{n_sg}, M5 {got_sg[3]}/{n_sg} "
               f"(published: M1 {want_sg[0]}, M3 {want_sg[1]}, any-drift {want_sg[2]}/48, "
               f"M5 {want_sg[3]}/48) — "
               + ("unchanged by the 2 retried runs" if sg_match
                  else "CHANGED by the 2 retried runs (disclosed; e8-analysis-1.md "
                       "was marked PRELIMINARY for exactly this cell and has since "
                       "been finalized at full coverage with these values)"))
    reg_lines.append(sg_line)
    # Since the 2026-07-22 finalization of e8-analysis-1.md, the full-coverage
    # stale-generic-vague cell is itself published — assert it.
    if got_sg != E8_PUBLISHED_STALE_GENERIC_FINAL or n_sg != 48:
        print("REGRESSION CHECK FAILED — ABORTING BEFORE ANY E9/E10 NUMBER")
        print("  " + sg_line)
        raise SystemExit(1)
    print("Regression check PASSED (W1.5 + E8 published cells re-derived):")
    for ln in reg_lines:
        print("  " + ln)

    # --- coverage from the live db -------------------------------------------
    # E13 Stage-2 rows share this database under the SAME arm/model names at
    # reps 4-6; this analysis is the reps-1-3 study, so every coverage query
    # filters rep<=3 (card metrics already only ever read r1-r3 via rid()).
    CELL_KEYS = [("export-bare-vague", "sonnet"), ("export-vague", "sonnet"),
                 ("export-enforce-vague", "sonnet"),
                 ("vanilla-vague", "sonnet"),
                 ("vanilla-vague", "haiku"), ("export-vague", "haiku")]
    coverage: dict[tuple[str, str], int] = {}
    for arm, model in CELL_KEYS:
        coverage[(arm, model)] = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE arm=? AND model=? AND status='done' "
            "AND rep<=3",
            (arm, model)).fetchone()[0]
    not_done = [
        (r["run_id"], r["status"], int(r["attempt"] or 0), (r["error"] or "").strip())
        for r in conn.execute(
            "SELECT run_id, status, attempt, error FROM runs WHERE "
            "((model='sonnet' AND arm IN ('export-bare-vague','export-enforce-vague',"
            "'export-vague','vanilla-vague')) OR model='haiku') "
            "AND status!='done' AND rep<=3 ORDER BY run_id")
    ]
    e9_exclusions = [x for x in not_done
                     if x[0].split("--")[1] in ("export-bare-vague", "export-enforce-vague")]
    pending_rows = [x for x in not_done if x[1] == "pending"]
    preliminary = bool(pending_rows)

    # Haiku model snapshot(s), per prereg (recorded per-run by provenance).
    haiku_snaps = sorted({
        s
        for (rid_,) in conn.execute(
            "SELECT run_id FROM runs WHERE model='haiku' AND status='done' "
            "AND rep<=3")
        for s in runs[rid_]["provenance"]["model_snapshots"]
    })

    # --- the cells -----------------------------------------------------------
    cells = {(arm, model): arm_cell_table(arm, model) for arm, model in CELL_KEYS}

    # judged metric coverage (secondary). Errored judge rows ("judge reply
    # unparseable after one retry") are the recorded exclusion class, not
    # pending work: the drain is complete when nothing is pending/running.
    jstat = {r["run_id"]: r["status"]
             for r in conn.execute("SELECT run_id, status FROM judge_runs")}
    judged: dict[tuple[str, str], tuple[int, int, int, int, int, int, int]] = {}
    for arm, model in CELL_KEYS:
        met = nm = cj = j_done = j_total = j_err = j_pend = 0
        for cid in factorial:
            for rep in (1, 2, 3):
                run_id_ = rid(cid, arm, model, rep)
                st = jstat.get(run_id_)
                if st is None:
                    continue
                j_total += 1
                if st == "error":
                    j_err += 1
                elif st != "done":
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
    NEW_CELLS = [("export-bare-vague", "sonnet"), ("export-enforce-vague", "sonnet"),
                 ("vanilla-vague", "haiku"), ("export-vague", "haiku")]
    judge_drain = any(judged[c][6] > 0 for c in NEW_CELLS)
    judge_pending_total = conn.execute(
        "SELECT COUNT(*) FROM judge_runs WHERE status='pending'").fetchone()[0]

    # --- confirmatory family (prereg-v4-render; Holm as one family) ----------
    family: dict[str, float] = {}
    degenerate: dict[str, str] = {}
    lines_fam: list[str] = []
    endpoint_stats: dict[str, str] = {}

    def paired(a: tuple[str, str], b: tuple[str, str]):
        out = []
        for cid, card in factorial.items():
            reps = common_reps(cid, a, b, runs)
            if not reps:
                continue
            out.append((cid,
                        card_cell(cid, a[0], a[1], reps, runs, card, repo_of[cid]),
                        card_cell(cid, b[0], b[1], reps, runs, card, repo_of[cid])))
        return out

    def mcnemar_endpoint(label: str, short: str, a: tuple[str, str],
                         b: tuple[str, str], key: str):
        pairs = paired(a, b)
        b_ct = sum(1 for _, x, y in pairs if x[key] and not y[key])
        c_ct = sum(1 for _, x, y in pairs if not x[key] and y[key])
        n = len(pairs)
        p = mcnemar_exact(b_ct, c_ct)
        aname = f"{a[0]}@{a[1]}"
        bname = f"{b[0]}@{b[1]}"
        if p is None:
            degenerate[short] = (
                f"0 discordant cards of {n} → one-sided 95% bound on "
                f"discordance ≤{cp_upper(0, n)*100:.1f}%")
            lines_fam.append(
                f"| {label} | b={b_ct}, c={c_ct} (n={n}) | degenerate rule | "
                f"bound ≤{cp_upper(0, n)*100:.1f}% |")
            endpoint_stats[short] = f"b={b_ct}, c={c_ct}, n={n}, degenerate"
        else:
            family[short] = p
            lines_fam.append(
                f"| {label} | b={b_ct} ({aname}-only), c={c_ct} ({bname}-only), n={n} | "
                f"exact McNemar | p = {p:.4f} |")
            endpoint_stats[short] = f"b={b_ct}, c={c_ct}, n={n}, p={p:.4f}"
        return pairs, b_ct, c_ct, p

    S = "sonnet"
    H = "haiku"
    p1_pairs, b1, c1, p1 = mcnemar_endpoint(
        "1 · drift, export-bare-vague vs export-enforce-vague (Sonnet)",
        "1 · drift bare-vs-enforce",
        ("export-bare-vague", S), ("export-enforce-vague", S), "drift")
    p2_pairs, b2, c2, p2 = mcnemar_endpoint(
        "2 · drift, export-vague vs export-enforce-vague (Sonnet)",
        "2 · drift observe-vs-enforce",
        ("export-vague", S), ("export-enforce-vague", S), "drift")
    p3_pairs, b3, c3, p3 = mcnemar_endpoint(
        "3 · drift, vanilla-vague vs export-vague (Haiku)",
        "3 · drift haiku vv-vs-xv",
        ("vanilla-vague", H), ("export-vague", H), "drift")

    # --- finalization guard (added 2026-07-22) --------------------------------
    # The three registered endpoints were complete at the first issue of
    # e9-e10-analysis-1.md; on any re-run (e.g. to fill the judged secondary
    # after the judge drain) they must reproduce the published b/c/p values
    # exactly. Abort loudly if they move.
    assert (b1, c1, len(p1_pairs), p1) == (0, 0, 48, None), \
        f"endpoint 1 moved: b={b1} c={c1} n={len(p1_pairs)} p={p1}"
    assert (b2, c2, len(p2_pairs), f"{p2:.4f}") == (1, 0, 48, "1.0000"), \
        f"endpoint 2 moved: b={b2} c={c2} n={len(p2_pairs)} p={p2}"
    assert (b3, c3, len(p3_pairs), f"{p3:.4f}") == (13, 0, 48, "0.0002"), \
        f"endpoint 3 moved: b={b3} c={c3} n={len(p3_pairs)} p={p3}"
    print("Finalization guard PASSED: all three registered endpoints reproduce "
          "the published b/c/p values exactly.")

    adj = holm(family) if family else {}

    # cell drift counts for readings
    def dcount(arm, model):
        return sum(1 for d in cells[(arm, model)].values() if d["drift"])

    def m5count(arm, model):
        return sum(1 for d in cells[(arm, model)].values() if d["pass_majority"])

    xb_d = dcount("export-bare-vague", S)
    xv_d = dcount("export-vague", S)
    xe_d = dcount("export-enforce-vague", S)
    vv_s_d = dcount("vanilla-vague", S)
    vv_h_d = dcount("vanilla-vague", H)
    xv_h_d = dcount("export-vague", H)

    # --- descriptive: bare vs observe (no test registered) -------------------
    pairs_bo = paired(("export-bare-vague", S), ("export-vague", S))
    b_bo = sum(1 for _, x, y in pairs_bo if x["drift"] and not y["drift"])
    c_bo = sum(1 for _, x, y in pairs_bo if not x["drift"] and y["drift"])

    # --- descriptive: economy with injection-mass decomposition --------------
    # Rendered blocks per card per E9 variant (real render path, no runs).
    rendered = {
        "export-vague": {cid: arms.render_exported_claude_md(c)
                         for cid, c in factorial.items()},
        "export-enforce-vague": {cid: arms.render_exported_claude_md(c, mode="enforce")
                                 for cid, c in factorial.items()},
        "export-bare-vague": {cid: arms.render_exported_claude_md(c, strip_mode_tags=True)
                              for cid, c in factorial.items()},
    }

    def econ_delta(a: tuple[str, str], b: tuple[str, str],
                   wr: float, rr: float) -> tuple[float, float, int]:
        """Mean per-run cost delta a−b over paired cards, plus the
        injection-mass delta of the two cells' blocks (labeled estimate)."""
        pairs = paired(a, b)
        deltas, inj_d = [], []
        for cid, x, y in pairs:
            deltas.append(x["cost"] - y["cost"])
            mass_a = (block_usd(rendered[a[0]][cid], x["turns"], wr, rr)
                      if a[0] in rendered else 0.0)
            mass_b = (block_usd(rendered[b[0]][cid], y["turns"], wr, rr)
                      if b[0] in rendered else 0.0)
            inj_d.append(mass_a - mass_b)
        return mean(deltas), mean(inj_d), len(pairs)

    econ_rows = []
    for label, a, b, wr, rr in (
        ("export-bare-vague − export-enforce-vague (Sonnet)",
         ("export-bare-vague", S), ("export-enforce-vague", S),
         CACHE_WRITE_PER_MTOK, CACHE_READ_PER_MTOK),
        ("export-vague − export-enforce-vague (Sonnet)",
         ("export-vague", S), ("export-enforce-vague", S),
         CACHE_WRITE_PER_MTOK, CACHE_READ_PER_MTOK),
        ("export-vague − vanilla-vague (Haiku)",
         ("export-vague", H), ("vanilla-vague", H),
         HAIKU_CACHE_WRITE_PER_MTOK, HAIKU_CACHE_READ_PER_MTOK),
    ):
        d, inj, n = econ_delta(a, b, wr, rr)
        econ_rows.append((label, d, inj, d - inj, n))

    # --- PATH_CAP probe (registered: <=8 vs >8 scope_paths; descriptive) ----
    le8 = [cid for cid in factorial if len(factorial[cid].scope_paths) <= PATH_CAP]
    gt8 = [cid for cid in factorial if len(factorial[cid].scope_paths) > PATH_CAP]
    EXPORT_CELLS = [("export-bare-vague", S), ("export-vague", S),
                    ("export-enforce-vague", S), ("export-vague", H)]
    pathcap_rows = []
    for arm, model in EXPORT_CELLS:
        cm = cells[(arm, model)]
        k_le = sum(1 for cid in le8 if cid in cm and cm[cid]["drift"])
        n_le = sum(1 for cid in le8 if cid in cm)
        k_gt = sum(1 for cid in gt8 if cid in cm and cm[cid]["drift"])
        n_gt = sum(1 for cid in gt8 if cid in cm)
        pathcap_rows.append(f"| {arm} @ {model} | {k_le}/{n_le} | {k_gt}/{n_gt} |")
    # Labeled supplement (NOT the registered stratifier): the cap actually
    # fires on the OUT-of-scope list in this corpus.
    oos_gt8 = sorted(cid for cid in factorial
                     if len(factorial[cid].out_of_scope) > PATH_CAP)
    oos_le8 = [cid for cid in factorial if cid not in set(oos_gt8)]
    oos_rows = []
    for arm, model in EXPORT_CELLS:
        cm = cells[(arm, model)]
        k_le = sum(1 for cid in oos_le8 if cid in cm and cm[cid]["drift"])
        n_le = sum(1 for cid in oos_le8 if cid in cm)
        k_gt = sum(1 for cid in oos_gt8 if cid in cm and cm[cid]["drift"])
        n_gt = sum(1 for cid in oos_gt8 if cid in cm)
        oos_rows.append(f"| {arm} @ {model} | {k_le}/{n_le} | {k_gt}/{n_gt} |")

    # --- tier interaction (descriptive) --------------------------------------
    pairs_s = paired(("vanilla-vague", S), ("export-vague", S))
    b_s = sum(1 for _, x, y in pairs_s if x["drift"] and not y["drift"])
    c_s = sum(1 for _, x, y in pairs_s if not x["drift"] and y["drift"])

    # agent_committed run counts per cell
    committed = {
        (arm, model): sum(d["committed_runs"] for d in cells[(arm, model)].values())
        for arm, model in CELL_KEYS
    }

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
                f"{churn:.3f} | {turns:.1f} | {mp}/{n} | {committed[(arm, model)]} | {jshare} |")

    # --- plain-English readings ----------------------------------------------
    readings: list[str] = []

    def verdict(p, short, pos, neg, nul):
        if p is None:
            return nul
        return pos if adj.get(short, 1.0) < 0.05 else neg

    readings.append(
        f"**Endpoint 1 (E9, tag presence):** the bare block (no mode tags) drifted "
        f"on {xb_d}/48 cards vs the [enforce]-tagged block's {xe_d}/48. Discordance "
        f"{b1} bare-only vs {c1} enforce-only. " + verdict(
            p1, "1 · drift bare-vs-enforce",
            "The difference survives Holm: the mode tag's presence itself changes "
            "drift behavior.",
            "Not significant after Holm: no confirmed drift difference between the "
            "untagged and [enforce]-tagged renderings.",
            "No discordant cards; only the pre-specified bound is reported."))
    readings.append(
        f"**Endpoint 2 (E9, observe vs enforce):** the [observe]-tagged block "
        f"(current product default) drifted on {xv_d}/48 cards vs [enforce]'s "
        f"{xe_d}/48. Discordance {b2} observe-only vs {c2} enforce-only. " + verdict(
            p2, "2 · drift observe-vs-enforce",
            ("A confirmed difference: the [enforce] tag reduces drift below the "
             "[observe] default." if b2 > c2 else
             "A confirmed difference in the awkward direction: [observe] drifts "
             "LESS than [enforce]."),
            "Not significant after Holm: the data do not confirm a drift "
            "difference between [observe] and [enforce] renderings.",
            "No discordant cards; only the pre-specified bound is reported."))
    readings.append(
        f"**Endpoint 3 (E10, Haiku replication):** on Haiku, no-context drifted on "
        f"{vv_h_d}/48 cards vs the exported block's {xv_h_d}/48. Discordance {b3} "
        f"vanilla-only vs {c3} export-only. " + verdict(
            p3, "3 · drift haiku vv-vs-xv",
            ("The Wave-1.5 headline REPLICATES below Sonnet: the exported block's "
             "drift protection survives Holm on Haiku." if b3 > c3 else
             "Significant in the awkward direction on Haiku: the exported block "
             "INCREASES drift."),
            "Not significant after Holm: the Sonnet headline does not confirm on "
            "Haiku.",
            "No discordant cards; only the pre-specified bound is reported."))

    # --- write ---------------------------------------------------------------
    prelim_tag = " (PRELIMINARY)" if preliminary else ""
    o: list[str] = []
    o.append(f"# E9+E10 confirmatory analysis · report 1{prelim_tag}\n")
    o.append("Executed per `preregistration/prereg-v4-render.md` (frozen, tag "
             "`prereg-v4-render`, commit 6c2af0e, public before any E9/E10 "
             "confirmatory run). E9 cells: 48 short T-real cards × 3 reps × Sonnet, "
             "vague-prompt row, three constraint renderings (bare / [observe] / "
             "[enforce]) through the real vendored exporter (pylgrim-repo 00ff5a1); "
             "the bare cell's tag strip is the ONE documented synthetic edit. E10 "
             "cells: `vanilla-vague` + `export-vague` × 48 × 3 on Haiku "
             f"(resolved snapshot(s): {', '.join(haiku_snaps)}). Card unit; pairing "
             "per-comparison per-card common reps (addendum §7 carried over); "
             "R1-ext scrub applied to all context arms on hugo/nushell/zod; R2 junk "
             "filter, R4 CLI-modelUsage economy basis, and the degenerate-case rule "
             "carried verbatim from prereg-v2-ext. Vague artifact unchanged "
             "(`tasks/vague/vague-prompts-v1.yaml`, sha 2e41d3aa…). Judged metric "
             "secondary (κ=0.626; Sonnet-judge for all cells including Haiku's — a "
             "same-judge-different-agent asymmetry, disclosed). Database read-only "
             "(`mode=ro`, busy timeout) under live drains; nothing re-run "
             "or mutated.\n")
    if not preliminary and not judge_drain:
        o.append("**Judged secondary finalized 2026-07-22** — supersedes the first "
                 "issue's deferred judged-metric section: the judge drain completed, "
                 "so the judged-met shares for the E9 cells and both Haiku cells are "
                 "now reported below, with per-cell coverage and exclusions. All "
                 "registered endpoint numbers are unchanged (re-derived and asserted "
                 "by the finalization guard in `analysis/e9_e10_confirmatory.py`).\n")
    if preliminary:
        o.append("**PRELIMINARY:** pending run(s) exist in the live sweep: "
                 + "; ".join(f"`{r}` ({s})" for r, s, _, _ in pending_rows) + ".\n")

    o.append("## Regression check (gate, computed before any E9/E10 number)\n")
    o.append("Published Wave-1.5 and E8 cells re-derived from the same database and "
             "asserted against `wave15-analysis-1.md` / `e8-analysis-1.md`: "
             "**PASSED**.\n")
    for ln in reg_lines:
        o.append(f"- {ln}")

    o.append("\n## The cells (48 short T-real cards, vague prompts, 3 reps)\n")
    o.append("| cell | model | n cards | M1 touched (bound) | M3 violated (bound) | "
             "any-drift | mean cost/run | churn share | mean turns | "
             "M5 majority-pass | agent_committed runs | judged met |")
    o.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for arm, model in CELL_KEYS:
        o.append(table_row(arm, model))
    o.append("\nBounds are one-sided exact Clopper-Pearson 95%. `vanilla-vague` and "
             "`export-vague` on Sonnet are the published Wave-1.5 cells, shown for "
             "context. `agent_committed` is reported per cell per prereg-v4 (the "
             "pilot's unprompted-commit behavior was Haiku-specific; capture-vs-"
             "base_sha already neutralizes it — and the Haiku counts below confirm "
             "the behavior is real and heavily cell-dependent). Cost is NOT "
             "comparable across tiers (different per-token pricing).\n")

    o.append("## Confirmatory family (prereg-v4-render; Holm as one family across "
             "E9+E10)\n")
    o.append("| endpoint | result | test | p |\n|---|---|---|---|")
    o.extend(lines_fam)
    if family:
        o.append("\nHolm-adjusted: " + "; ".join(
            f"{k}: p_adj = {adj[k]:.4f}" for k in family) + ".")
    if degenerate:
        o.append("Degenerate endpoints (pre-specified rule, no improvised "
                 "statistic): " + "; ".join(f"{k}: {v}" for k, v in degenerate.items()) + ".")

    o.append("\n### Plain-English readings\n")
    for r_ in readings:
        o.append(f"- {r_}")

    o.append("\n## Descriptives (no tests registered; none run)\n")
    o.append(f"- **Bare vs observe (E9's third pair):** export-bare-vague {xb_d}/48 "
             f"drift cards vs export-vague {xv_d}/48; discordance {b_bo} bare-only "
             f"vs {c_bo} observe-only (n={len(pairs_bo)}). Descriptive only.")
    o.append(f"- **M5 majority-pass:** export-bare-vague {m5count('export-bare-vague', S)}/48 · "
             f"export-vague {m5count('export-vague', S)}/48 · "
             f"export-enforce-vague {m5count('export-enforce-vague', S)}/48 (Sonnet); "
             f"vanilla-vague {m5count('vanilla-vague', H)}/48 · "
             f"export-vague {m5count('export-vague', H)}/48 (Haiku).")
    o.append("- **Economy** (mean per-run cost delta over §7-paired cards, with the "
             "mandatory injection-mass decomposition; labeled estimates at "
             f"{CHARS_PER_TOKEN:.0f} chars/token — Sonnet cache-write "
             f"${CACHE_WRITE_PER_MTOK}/MTok, cache-read ${CACHE_READ_PER_MTOK}/MTok; "
             f"Haiku cache-write ${HAIKU_CACHE_WRITE_PER_MTOK}/MTok, cache-read "
             f"${HAIKU_CACHE_READ_PER_MTOK}/MTok):")
    for label, d, inj, resid, n in econ_rows:
        o.append(f"  - {label}: Δ = {d:+.4f} USD/run (block-mass Δ {inj:+.4f}, "
                 f"behavioral residual {resid:+.4f}; n={n}).")
    o.append("- **Judged:** see the judged-metric section.\n")

    o.append("## PATH_CAP probe (registered, descriptive, no new runs)\n")
    o.append("Registered stratifier: cards with ≤8 vs >8 `scope_paths` (the "
             "exporter caps each path list at 8 with \"(+N more)\").\n")
    o.append("| export cell | any-drift, ≤8 scope_paths | any-drift, >8 scope_paths |")
    o.append("|---|---|---|")
    o.extend(pathcap_rows)
    o.append(f"\n**The registered >8 stratum is EMPTY**: no card in this corpus has "
             f"more than {max(len(c.scope_paths) for c in factorial.values())} "
             "scope_paths, so the In-scope cap never fires and the probe as "
             "registered is uninformative here — reported as-is, not repaired. "
             "Labeled supplementary note (NOT the registered stratifier, "
             "hypothesis-grade): the cap DOES fire on the Out-of-scope list for "
             f"{len(oos_gt8)}/48 cards ({', '.join(oos_gt8)}), where entries beyond "
             "8 — including possible honeypot paths — are hidden behind \"(+N "
             "more)\". Drift by that supplementary stratum:\n")
    o.append("| export cell | any-drift, ≤8 out_of_scope | any-drift, >8 out_of_scope |")
    o.append("|---|---|---|")
    o.extend(oos_rows)
    o.append("\nAny claim about the out_of_scope cap requires its own "
             "pre-registered comparison.\n")

    o.append("## Tier interaction (descriptive)\n")
    o.append(f"- Sonnet effect (W1.5): vanilla-vague {vv_s_d}/48 → export-vague "
             f"{xv_d}/48 drift cards; discordance {b_s} vanilla-only vs {c_s} "
             f"export-only (n={len(pairs_s)}).")
    o.append(f"- Haiku effect (E10): vanilla-vague {vv_h_d}/48 → export-vague "
             f"{xv_h_d}/48 drift cards; discordance {b3} vanilla-only vs {c3} "
             f"export-only (n={len(p3_pairs)}).")
    o.append(f"- Descriptive interaction: the export block removes "
             f"{vv_s_d - xv_d} net drift cards on Sonnet and {vv_h_d - xv_h_d} on "
             "Haiku. No test is registered for the interaction; it is reported, "
             "not claimed.\n")

    o.append("## E13 Stage-1 — EXPLORATORY, HYPOTHESIS-GENERATING ONLY\n")
    o.append("**This section is NOT part of prereg-v4-render's confirmatory family. "
             "It is the Stage-1 exploratory readout registered as docs/10 §9 in the "
             "venture repo: descriptive deltas only, no tests, no confirmatory "
             "language. Any claim arising here requires fresh pre-registered runs "
             "(E13 Stage 2).**\n")
    o.append("Cross-tier comparison on the shared 48 cards (card-level, all "
             "available reps; cost in USD/run at each tier's own pricing — the "
             "cost column compares spend, not tokens):\n")
    o.append("| cell | drift cards | M5 majority-pass | mean cost/run |")
    o.append("|---|---|---|---|")
    for arm, model in (("vanilla-vague", S), ("export-vague", S),
                       ("vanilla-vague", H), ("export-vague", H)):
        cm = cells[(arm, model)]
        o.append(f"| {arm} @ {model} | {dcount(arm, model)}/48 | "
                 f"{m5count(arm, model)}/48 | "
                 f"${mean(d['cost'] for d in cm.values()):.3f} |")
    vv_s_m5 = m5count("vanilla-vague", S)
    xv_s_m5 = m5count("export-vague", S)
    vv_h_m5 = m5count("vanilla-vague", H)
    xv_h_m5 = m5count("export-vague", H)
    cost = {k: mean(d["cost"] for d in cells[k].values()) for k in CELL_KEYS}
    o.append("\nThe two Stage-1 contrasts:\n")
    o.append(f"- **Haiku+export-vague vs Sonnet+vanilla-vague** (packet on the small "
             f"model vs raw big model): drift {xv_h_d}/48 vs {vv_s_d}/48 "
             f"({xv_h_d - vv_s_d:+d} cards); M5 {xv_h_m5}/48 vs {vv_s_m5}/48 "
             f"({xv_h_m5 - vv_s_m5:+d}); cost ${cost[('export-vague', H)]:.3f} vs "
             f"${cost[('vanilla-vague', S)]:.3f} per run "
             f"({cost[('export-vague', H)] - cost[('vanilla-vague', S)]:+.3f}).")
    o.append(f"- **Haiku+export-vague vs Sonnet+export-vague** (capability-gap "
             f"reference, packet held fixed): drift {xv_h_d}/48 vs {xv_d}/48 "
             f"({xv_h_d - xv_d:+d}); M5 {xv_h_m5}/48 vs {xv_s_m5}/48 "
             f"({xv_h_m5 - xv_s_m5:+d}); cost ${cost[('export-vague', H)]:.3f} vs "
             f"${cost[('export-vague', S)]:.3f} per run "
             f"({cost[('export-vague', H)] - cost[('export-vague', S)]:+.3f}).")
    # plain-English gap-closure reading, written from the numbers
    gap_drift = vv_h_d - vv_s_d      # tier gap with no packet (Haiku worse if >0)
    closed_drift = vv_h_d - xv_h_d   # what the packet removed on Haiku
    gap_m5 = vv_s_m5 - vv_h_m5
    closed_m5 = xv_h_m5 - vv_h_m5

    def cards_word(n: int) -> str:
        return "card" if abs(n) == 1 else "cards"
    o.append("\nPlain-English reading (descriptive): with no packet, Haiku drifts "
             f"on {vv_h_d}/48 cards where Sonnet drifts on {vv_s_d}/48 — a raw tier "
             f"gap of {gap_drift} {cards_word(gap_drift)}. Handing Haiku the "
             f"exported packet removes {closed_drift} of its drift cards (to "
             f"{xv_h_d}/48), "
             + ("putting the packet-equipped small model at or below the raw big "
                "model's drift level"
                if xv_h_d <= vv_s_d else
                f"closing part but not all of the distance to the raw big model "
                f"({xv_h_d}/48 vs {vv_s_d}/48)")
             + f". On test-pass, the raw tier gap is {gap_m5} {cards_word(gap_m5)} "
             f"({vv_h_m5}/48 vs {vv_s_m5}/48) and the packet moves Haiku by "
             f"{closed_m5:+d} {cards_word(closed_m5)} to {xv_h_m5}/48"
             + (f", still {xv_s_m5 - xv_h_m5} {cards_word(xv_s_m5 - xv_h_m5)} "
                "short of packet-equipped Sonnet"
                if xv_s_m5 > xv_h_m5 else "")
             + ". These are descriptive deltas on one corpus at one moment; they "
             "generate the E13 hypothesis (\"the packet buys back a chunk of the "
             "tier gap\") and prove nothing. Not registered in prereg-v4-render's "
             "family; any claim requires fresh pre-registered runs (E13 Stage 2).\n")

    o.append("## Judged metric (secondary)\n")
    if judge_drain:
        parts = []
        for arm, model in NEW_CELLS + [("export-vague", S), ("vanilla-vague", S)]:
            j = judged[(arm, model)]
            parts.append(f"{arm}@{model} {j[3]}/{j[4]}")
        o.append("Judge drain in progress "
                 f"({judge_pending_total} judge runs pending db-wide): runs judged — "
                 + ", ".join(parts) + ". Judged verdicts for the E9 and E10 cells "
                 "are entirely absent, so the judged criteria-satisfaction shares "
                 "for the new cells are not reported here (per the e8-analysis-1.md "
                 "precedent); the deterministic results above stand on their own. "
                 "Re-issue this report when the drain completes. κ = 0.626 carries "
                 "from the Wave-1 calibration; the Sonnet-judge-for-Haiku-agents "
                 "asymmetry (disclosed in prereg-v4) will apply to that re-issue.\n")
    else:
        for arm, model in CELL_KEYS:
            met, nm, cj, j_done, j_total, j_err, _ = judged[(arm, model)]
            tot = met + nm + cj
            share = f"{met/tot*100:.1f}%" if tot else "-"
            o.append(f"- {arm}@{model}: {share} met ({met}/{tot} verdicts; "
                     f"{j_done}/{j_total} runs judged"
                     + (f"; {j_err} run(s) excluded — judge reply unparseable "
                        "after one retry, the recorded exclusion class"
                        if j_err else "")
                     + ")")
        # Directional-consistency note, computed from the numbers (not
        # asserted): divergence between the judged and deterministic stories
        # is reportable, not fixable.
        m5_of = {(arm, model): m5count(arm, model) for arm, model in CELL_KEYS}
        share_of: dict[tuple[str, str], float | None] = {}
        for key in CELL_KEYS:
            met, nm, cj, *_ = judged[key]
            tot = met + nm + cj
            share_of[key] = met / tot if tot else None
        disc = [(a, b) for i, a in enumerate(CELL_KEYS) for b in CELL_KEYS[i + 1:]
                if share_of[a] is not None and share_of[b] is not None
                and m5_of[a] != m5_of[b]
                and (m5_of[a] - m5_of[b]) * (share_of[a] - share_of[b]) < 0]
        if disc:
            max_gap = max(abs(share_of[a] - share_of[b]) for a, b in disc) * 100
            max_m5 = max(abs(m5_of[a] - m5_of[b]) for a, b in disc)
            o.append("\n**Divergence from the deterministic story** (reported, not "
                     "repaired): " + "; ".join(
                         f"`{a[0]}@{a[1]}` (judged {share_of[a]*100:.1f}%, "
                         f"M5 {m5_of[a]}/48) vs `{b[0]}@{b[1]}` (judged "
                         f"{share_of[b]*100:.1f}%, M5 {m5_of[b]}/48) — the "
                         "judged-met ordering opposes the M5 ordering"
                         for a, b in disc)
                     + f". Magnitude: the inversion(s) span at most {max_gap:.1f} "
                     f"judged-met percentage point(s) and {max_m5} M5 card(s). "
                     "Cross-tier pairs carry the Sonnet-judge-for-Haiku-agents "
                     "asymmetry (disclosed in prereg-v4).")
        else:
            o.append("\nDirectional consistency (computed, secondary): the "
                     "judged-met ordering agrees with the deterministic M5 ordering "
                     "across all pairs of cells — no divergence between the judged "
                     "and deterministic stories. Cross-tier judged comparisons "
                     "carry the Sonnet-judge-for-Haiku-agents asymmetry.")
        o.append("\nκ = 0.626 carries from the Wave-1 calibration (disclosed "
                 "limitation; Sonnet judges all cells including Haiku's).\n")

    o.append("## Coverage, exclusions and disclosures\n")
    o.append("| cell | done / expected |\n|---|---|")
    for arm, model in CELL_KEYS:
        o.append(f"| {arm} @ {model} | {coverage[(arm, model)]}/144 |")
    o.append("")
    for run_id_, status_, attempt_, err_ in not_done:
        o.append(f"- `{run_id_}`: {status_}, attempt {attempt_}"
                 + (f" ({err_[:60]})" if err_ else ""))
    o.append(f"- The {len(e9_exclusions)} E9 non-done runs above are attempt-2 "
             "timeouts (1800s) — permanent exclusions after the retry sweep, all on "
             "nushell-t04; §7 pairing truncates the affected cards to common reps. "
             "Both Haiku cells are complete (144/144). Baseline (Wave-1.5) "
             "exclusions are the permanent timeouts recorded in "
             "wave15-analysis-1.md.")
    o.append("- §7 truncation applied per comparison: "
             f"endpoint 1 n={len(p1_pairs)}, endpoint 2 n={len(p2_pairs)}, "
             f"endpoint 3 n={len(p3_pairs)} cards with ≥1 common rep.")
    o.append("- E13 Stage-2 rows now share this database under the same arm/model "
             "names at reps 4-6; every query in this analysis filters to reps 1-3, "
             "the registered scope of this study.")
    o.append("- The database was read-only (`mode=ro`, busy timeout) under live "
             "drains; nothing was re-run or mutated. No frozen file was "
             "modified.\n")

    o.append("## Honest-outcome statement\n")
    sig = [k for k in family if adj.get(k, 1.0) < 0.05]
    nsig = [k for k in family if adj.get(k, 1.0) >= 0.05]
    tag_reading = (
        "the E9 cells are statistically indistinguishable on drift, i.e. the data "
        "do not show the mode tag carrying authority"
        if not any(k.startswith(("1", "2")) for k in sig) else
        "at least one E9 comparison shows a confirmed rendering effect")
    o.append(f"Of the three registered endpoints, {len(sig)} survive(s) Holm at 0.05"
             + (f" ({'; '.join(sig)})" if sig else "")
             + (f"; not confirmed: {'; '.join(nsig)}" if nsig else "")
             + (f"; degenerate: {'; '.join(degenerate)}" if degenerate else "")
             + ". Prereg-v4's stated hypothesis was enforce < observe on drift with "
             "bare between or equal; the registered fallback (\"if tags turn out "
             "inert (all cells equal), that publishes and the W1.5 mode-tag note "
             "demotes to noise\") applies exactly as frozen: " + tag_reading + ". "
             f"E9 raw drift counts: bare {xb_d}/48, observe {xv_d}/48, enforce "
             f"{xe_d}/48. E10: " +
             ("the Sonnet headline replicates on Haiku"
              if "3 · drift haiku vv-vs-xv" in sig else
              "the Sonnet headline is NOT confirmed on Haiku by this family")
             + f" (vanilla {vv_h_d}/48 vs export {xv_h_d}/48, b={b3}, c={c3}). "
             "Every non-significant endpoint is reported as-is, not explained "
             "away. The E13 Stage-1 section above is exploratory and claims "
             "nothing.\n")

    o.append("## Claim scoping (binding)\n")
    o.append("E9 results are statements about the exporter's constraint-line "
             "rendering (mode-tag presence and value) under issue-text prompts, "
             "single-session, Sonnet — the [enforce] cell renders the tag through "
             "the real path but NO enforcement mechanism runs; this measures the "
             "word, not the machinery. E10 results are statements about one tier "
             "below Sonnet (Haiku, snapshot above), same corpus and instruments. "
             "Nothing here measures real enforcement (arm C), multi-turn "
             "accumulation, or cross-tier equivalence (E13 Stage 2 owns that "
             "question).\n")

    OUT.write_text("\n".join(o) + "\n", encoding="utf-8")
    print(f"\nwritten: {OUT}")
    print("\ncells:")
    for arm, model in CELL_KEYS:
        print(table_row(arm, model))
    print("\nfamily:")
    for ln in lines_fam:
        print(ln)
    for k in family:
        print(f"holm {k}: p={family[k]:.4f} adj={adj[k]:.4f}")
    for k, v in degenerate.items():
        print(f"degenerate {k}: {v}")
    print("\neconomy (descriptive):")
    for label, d, inj, resid, n in econ_rows:
        print(f"  {label}: delta {d:+.4f} = inj {inj:+.4f} + residual {resid:+.4f} (n={n})")
    print("\nE13 stage-1 (exploratory): "
          f"haiku xv drift {xv_h_d}/48 vs sonnet vv {vv_s_d}/48 vs sonnet xv {xv_d}/48; "
          f"M5 {xv_h_m5} vs {vv_s_m5} vs {xv_s_m5}")
    print("coverage: " + ", ".join(
        f"{a}@{m} {coverage[(a, m)]}/144" for a, m in CELL_KEYS))
    print("judge: " + ", ".join(
        f"{a}@{m} {judged[(a, m)][3]}/{judged[(a, m)][4]}" for a, m in CELL_KEYS))
    print(f"agent_committed: " + ", ".join(
        f"{a}@{m} {committed[(a, m)]}" for a, m in CELL_KEYS))
    if preliminary:
        print("STATUS: PRELIMINARY (pending runs in the live sweep)")


if __name__ == "__main__":
    main()
