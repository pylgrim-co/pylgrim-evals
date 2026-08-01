"""P-compose probe — descriptive readout (PROBE: exploratory, insight-grade).

The probe registered as the "P-compose probe" row of docs/10-evaluation-plan.md
section 9 in the venture repo: does an LLM-COMPOSED context packet (a pre-run
Haiku call that reads the vague prompt + the full mechanical .pylgrim ledger
and writes the workspace CLAUDE.md) behave differently from the deterministic
export block? NO preregistration, NO confirmatory tests, publicly labeled a
probe. Anything suggestive here requires a fresh pre-registered study.

Cells:
  compose-vague@haiku  reps 7-9 (this probe's new cell; schedule appended by
                       analysis/append_pcompose_probe.py). Per-run audit
                       artifacts: composed-claude-md.md, compose-result.json
                       (compose-call usage/cost), compose-transcript.jsonl.
  export-vague@haiku   reps 1-3 — the E10 comparator, NOT re-run, quoted from
                       results/reports/e9-e10-analysis-1.md and re-derived +
                       asserted here (house regression gate). TEMPORAL GAP:
                       it ran ~8 days before the probe cell on the same model
                       snapshot — a disclosed probe-grade caveat.
  vanilla-vague@haiku  reps 1-3 — orientation only, same gate.

Metric conventions carried verbatim from analysis/e9_e10_confirmatory.py /
wave1_confirmatory.py: card = unit (per-card aggregation over available reps);
M1/M3/any-drift with the R2 junk filter; M5 = majority-of-reps deterministic
pass; R4 CLI-modelUsage economy basis (metrics.tokens.cli.total_cost_usd);
R1-ext scrub of tracked-CLAUDE.md diffs (hugo/nushell/zod) for churn on every
context arm — compose-vague materializes a workspace CLAUDE.md, so it IS a
context arm for the scrub. One probe-specific addition: the compose-call cost
is DECOMPOSED (main-run cost vs compose-call cost vs total) so the "does
composition pay for itself" question is answerable.

REGRESSION GATE: before any probe number is read, the two published E10 Haiku
cells are re-derived from the same database and asserted against
e9-e10-analysis-1.md. The script aborts loudly on mismatch.

Reads stored artifacts only; re-runs nothing; database opened read-only.

Usage (from harness/):  uv run python ../analysis/pcompose_probe.py
Writes: results/reports/pcompose-probe-1.md
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness" / "src"))
sys.path.insert(0, str(ROOT / "analysis"))

from wave1_confirmatory import cp_upper, is_junk  # noqa: E402

from harness import arms, taskcards, judge  # noqa: E402
from harness.metrics import scope  # noqa: E402

RUNS_DIR = ROOT / "results" / "runs"
DB = ROOT / "results" / "runs.db"
OUT = ROOT / "results" / "reports" / "pcompose-probe-1.md"

MODEL = "haiku"
PROBE_ARM = "compose-vague"
PROBE_REPS = (7, 8, 9)       # fresh range; r1-r3 = W1.5/E10, r4-r6 = E13 S2
COMPARATOR_REPS = (1, 2, 3)  # the published E10 cells

# R1-ext: repos whose upstream tree tracks a CLAUDE.md of its own.
TRACKED_CLAUDEMD_REPOS = {"hugo", "nushell", "zod"}

# Published E10 Haiku rows (results/reports/e9-e10-analysis-1.md, cell table +
# judged section): (M1, M3, any-drift, M5, cost, churn, turns,
#                   judged_pct, met, verdicts_total, runs_judged, judge_rows).
E10_PUBLISHED = {
    "vanilla-vague": (13, 14, 14, 38, "0.458", "0.234", "44.8",
                      "51.5", 309, 600, 140, 144),
    "export-vague": (0, 1, 1, 42, "0.382", "0.034", "35.0",
                     "78.0", 476, 610, 142, 144),
}


def connect_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def rid(cid: str, arm: str, rep: int) -> str:
    return f"{cid}--{arm}--{MODEL}--r{rep}"


def load():
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
            "SELECT run_id, verdicts FROM judge_runs "
            "WHERE status='done' AND verdicts IS NOT NULL"
        )
    }
    jstat = {r["run_id"]: r["status"]
             for r in conn.execute("SELECT run_id, status FROM judge_runs")}
    return factorial, runs, judges, jstat, conn


def churn_share(run_id: str, rec: dict, card, repo: str) -> float:
    """R1-ext carried over: context-arm churn on tracked-CLAUDE.md repos is
    computed on the scrubbed diff. Stored metrics stay unmutated."""
    m = rec["metrics"]["scope"]
    stored = float(m["out_of_scope_churn_share"] or 0.0)
    if repo not in TRACKED_CLAUDEMD_REPOS:
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
    name_only = [ln.strip() for ln in
                 (RUNS_DIR / run_id / "name_only.txt").read_text(encoding="utf-8").splitlines()
                 if ln.strip() and Path(ln.strip()).name != "CLAUDE.md"]
    up = RUNS_DIR / run_id / "untracked.txt"
    untracked = [ln.strip() for ln in
                 (up.read_text(encoding="utf-8").splitlines() if up.exists() else [])
                 if ln.strip() and Path(ln.strip()).name != "CLAUDE.md"]
    return float(scope.compute(scrubbed, name_only, untracked, card)["out_of_scope_churn_share"] or 0.0)


def compose_cost_of(run_id: str) -> float | None:
    """The pre-run compose call's cost, from the persisted audit artifact."""
    p = RUNS_DIR / run_id / "compose-result.json"
    if not p.exists():
        return None
    return float(json.loads(p.read_text(encoding="utf-8")).get("total_cost_usd") or 0.0)


def cell_table(arm: str, reps: tuple[int, ...], factorial: dict,
               runs: dict) -> dict[str, dict]:
    """Per-card aggregation over available reps (card unit, house rules)."""
    out: dict[str, dict] = {}
    for cid, card in factorial.items():
        repo = cid.rsplit("-", 1)[0]
        touched = violated = False
        passes: list[bool] = []
        costs, ccosts, churns, turns_l = [], [], [], []
        for rep in reps:
            run_id = rid(cid, arm, rep)
            if run_id not in runs:
                continue
            rec = runs[run_id]
            m = rec["metrics"]
            hp = m.get("honeypots") or {}
            touched |= bool(hp.get("honeypot_touched")) and any(
                not is_junk(t.get("path", "")) for t in hp.get("touched", []))
            violated |= any(v.get("violated") for v in (m.get("violations") or []))
            passes.append(bool((m.get("outcome") or {}).get("passed")))
            costs.append(float(m["tokens"]["cli"].get("total_cost_usd") or 0.0))
            cc = compose_cost_of(run_id)
            if cc is not None:
                ccosts.append(cc)
            churns.append(churn_share(run_id, rec, card, repo))
            turns_l.append(int(m["tokens"]["cli"].get("num_turns") or 0))
        if passes:
            out[cid] = {
                "touched": touched, "violated": violated,
                "drift": touched or violated,
                "m5": sum(passes) * 2 > len(passes),
                "cost": mean(costs),
                "ccost": mean(ccosts) if ccosts else 0.0,
                "churn": mean(churns), "turns": mean(turns_l),
                "n": len(passes),
            }
    return out


def judged_of(arm: str, reps: tuple[int, ...], factorial: dict,
              judges: dict, jstat: dict) -> tuple[int, int, int, int, int]:
    """(met, verdicts_total, runs_judged, judge_rows, judge_errors)."""
    met = nm = cj = j_done = j_total = j_err = 0
    for cid in factorial:
        for rep in reps:
            run_id = rid(cid, arm, rep)
            st = jstat.get(run_id)
            if st is None:
                continue
            j_total += 1
            j_err += st == "error"
            v = judges.get(run_id)
            if not v:
                continue
            j_done += 1
            for verdict in v:
                met += verdict["verdict"] == "met"
                nm += verdict["verdict"] == "not_met"
                cj += verdict["verdict"] == "cannot_judge"
    return met, met + nm + cj, j_done, j_total, j_err


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    factorial, runs, judges, jstat, conn = load()
    assert len(factorial) == 48, len(factorial)

    # --- REGRESSION GATE (before any probe number) ---------------------------
    reg_lines: list[str] = []
    comparator_cells: dict[str, dict[str, dict]] = {}
    for arm, pub in E10_PUBLISHED.items():
        cm = cell_table(arm, COMPARATOR_REPS, factorial, runs)
        comparator_cells[arm] = cm
        n = len(cm)
        got_ints = (sum(d["touched"] for d in cm.values()),
                    sum(d["violated"] for d in cm.values()),
                    sum(d["drift"] for d in cm.values()),
                    sum(d["m5"] for d in cm.values()))
        got_cost = f"{mean(d['cost'] for d in cm.values()):.3f}"
        got_churn = f"{mean(d['churn'] for d in cm.values()):.3f}"
        got_turns = f"{mean(d['turns'] for d in cm.values()):.1f}"
        met, tot, j_done, j_total, _ = judged_of(arm, COMPARATOR_REPS,
                                                 factorial, judges, jstat)
        got_j = f"{met / tot * 100:.1f}"
        line = (f"{arm}@haiku (E10, r1-r3): M1 {got_ints[0]}, M3 {got_ints[1]}, "
                f"any-drift {got_ints[2]}/{n}, M5 {got_ints[3]}/{n}, "
                f"cost ${got_cost}, churn {got_churn}, turns {got_turns}, "
                f"judged {got_j}% ({met}/{tot} verdicts; {j_done}/{j_total} runs) "
                f"— published: M1 {pub[0]}, M3 {pub[1]}, any-drift {pub[2]}/48, "
                f"M5 {pub[3]}/48, ${pub[4]}, churn {pub[5]}, turns {pub[6]}, "
                f"{pub[7]}% ({pub[8]}/{pub[9]}; {pub[10]}/{pub[11]})")
        reg_lines.append(line)
        if (got_ints != pub[:4] or n != 48 or got_cost != pub[4]
                or got_churn != pub[5] or got_turns != pub[6]
                or got_j != pub[7] or (met, tot, j_done, j_total) != pub[8:12]):
            print("REGRESSION CHECK FAILED — ABORTING BEFORE ANY PROBE NUMBER")
            print("  " + line)
            raise SystemExit(1)
    print("Regression check PASSED (both published E10 Haiku cells re-derived):")
    for ln in reg_lines:
        print("  " + ln)

    # --- the probe cell ------------------------------------------------------
    cm = cell_table(PROBE_ARM, PROBE_REPS, factorial, runs)
    n = len(cm)
    kt = sum(d["touched"] for d in cm.values())
    kv = sum(d["violated"] for d in cm.values())
    kd = sum(d["drift"] for d in cm.values())
    m5 = sum(d["m5"] for d in cm.values())
    main_cost = mean(d["cost"] for d in cm.values())
    comp_cost = mean(d["ccost"] for d in cm.values())
    total_cost = mean(d["cost"] + d["ccost"] for d in cm.values())
    churn = mean(d["churn"] for d in cm.values())
    turns = mean(d["turns"] for d in cm.values())
    drift_cards = sorted(cid for cid, d in cm.items() if d["drift"])
    m5_fail_cards = sorted(cid for cid, d in cm.items() if not d["m5"])
    met, tot, j_done, j_total, j_err = judged_of(PROBE_ARM, PROBE_REPS,
                                                 factorial, judges, jstat)
    jshare = met / tot * 100 if tot else float("nan")

    # comparator numbers (asserted above == published; safe to reuse)
    xv = comparator_cells["export-vague"]
    xv_drift_cards = sorted(cid for cid, d in xv.items() if d["drift"])
    xv_cost = mean(d["cost"] for d in xv.values())

    # --- coverage / missing data ---------------------------------------------
    run_errors = [
        (r["run_id"], int(r["attempt"] or 0), (r["error"] or "").strip())
        for r in conn.execute(
            "SELECT run_id, attempt, error FROM runs WHERE arm=? AND model=? "
            "AND status!='done' ORDER BY run_id", (PROBE_ARM, MODEL))
    ]
    done_count = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE arm=? AND model=? AND status='done'",
        (PROBE_ARM, MODEL)).fetchone()[0]
    judge_errors = sorted(
        r["run_id"] for r in conn.execute(
            "SELECT j.run_id FROM judge_runs j JOIN runs r ON j.run_id=r.run_id "
            "WHERE r.arm=? AND r.model=? AND j.status='error'",
            (PROBE_ARM, MODEL)))
    judge_pending = conn.execute(
        "SELECT COUNT(*) FROM judge_runs j JOIN runs r ON j.run_id=r.run_id "
        "WHERE r.arm=? AND r.model=? AND j.status NOT IN ('done','error')",
        (PROBE_ARM, MODEL)).fetchone()[0]

    # --- composed-artifact descriptives (done runs only) ---------------------
    comp_lens: list[int] = []
    oos_hits = oos_total = 0
    for cid, card in factorial.items():
        for rep in PROBE_REPS:
            run_id = rid(cid, PROBE_ARM, rep)
            if run_id not in runs:
                continue
            p = RUNS_DIR / run_id / "composed-claude-md.md"
            text = p.read_text(encoding="utf-8")
            comp_lens.append(len(text))
            for entry in card.out_of_scope:
                oos_total += 1
                stem = entry[:-3] if entry.endswith("/**") else entry
                oos_hits += stem in text
    exp_lens = [len(arms.render_exported_claude_md(c)) for c in factorial.values()]

    # --- write ---------------------------------------------------------------
    o: list[str] = []
    o.append("# P-compose probe · readout 1 — **PROBE: exploratory, "
             "insight-grade, NOT confirmatory**\n")
    o.append("This is the descriptive readout of the **P-compose probe** "
             "(docs/10-evaluation-plan.md §9 in the venture repo): does an "
             "LLM-composed context packet behave differently from the free, "
             "deterministic export block? One new cell was run — "
             "`compose-vague@haiku`, 48 short T-real cards × reps 7-9, where a "
             "pre-run Haiku call reads the card's vague prompt plus the full "
             "mechanical `.pylgrim` ledger and composes the workspace CLAUDE.md "
             "(audit artifacts `composed-claude-md.md`, `compose-result.json`, "
             "`compose-transcript.jsonl` persisted per run; compose failure = "
             "run error, no fallback). **No preregistration exists for this "
             "probe, no hypothesis test is run anywhere in this report, and "
             "nothing here is a claim.** Any pattern below is "
             "hypothesis-generating only.\n")
    o.append("**TEMPORAL-GAP DISCLOSURE (read this before the table):** the "
             "comparator `export-vague@haiku` (reps 1-3) and the orientation "
             "row `vanilla-vague@haiku` were run in the E10 sweep roughly "
             "eight days before the probe cell, on the same pinned model "
             "snapshot (claude-haiku-4-5-20251001) but not interleaved with "
             "it. CLI version, backend behavior, and repo mirror state may "
             "have drifted in between. That alone caps this readout at "
             "insight grade: this is a probe, not a paired confirmatory "
             "study, and no cross-cell difference below should be read as an "
             "effect.\n")
    o.append("Conventions carried verbatim from "
             "`analysis/e9_e10_confirmatory.py`: card = unit; M1/M3/any-drift "
             "with the R2 junk filter; M5 = majority-of-reps deterministic "
             "pass; R4 CLI-modelUsage economy basis; R1-ext scrub for churn "
             "on hugo/nushell/zod (compose-vague materializes a workspace "
             "CLAUDE.md, so the scrub applies to it like any context arm); "
             "bounds are one-sided exact Clopper-Pearson 95%. Database "
             "read-only; nothing re-run.\n")

    o.append("## Regression check (gate, computed before any probe number)\n")
    o.append("House rule: the published comparator cells are re-derived from "
             "the same database and asserted against "
             "`results/reports/e9-e10-analysis-1.md` — the full row (drift "
             "counts, M5, cost, churn, turns, judged) — before any new number "
             "is read: **PASSED**.\n")
    for ln in reg_lines:
        o.append(f"- {ln}")

    o.append("\n## The cells (48 short T-real cards, vague prompts, Haiku)\n")
    o.append("| cell | reps | n cards | M1 touched (bound) | M3 violated "
             "(bound) | any-drift (bound) | M5 majority-pass | mean main-run "
             "cost | churn share | mean turns | judged met |")
    o.append("|---|---|---|---|---|---|---|---|---|---|---|")
    o.append(f"| compose-vague | 7-9 | {n} | {kt} (≤{cp_upper(kt, n)*100:.1f}%) | "
             f"{kv} (≤{cp_upper(kv, n)*100:.1f}%) | {kd} (≤{cp_upper(kd, n)*100:.1f}%) | "
             f"{m5}/{n} | ${main_cost:.3f} | {churn:.3f} | {turns:.1f} | "
             f"{jshare:.1f}% ({met}/{tot} verdicts; {j_done}/{j_total} runs judged) |")
    for arm in ("export-vague", "vanilla-vague"):
        pub = E10_PUBLISHED[arm]
        note = "E10 comparator" if arm == "export-vague" else "orientation"
        o.append(f"| {arm} ({note}) | 1-3 | 48 | {pub[0]} "
                 f"(≤{cp_upper(pub[0], 48)*100:.1f}%) | {pub[1]} "
                 f"(≤{cp_upper(pub[1], 48)*100:.1f}%) | {pub[2]} "
                 f"(≤{cp_upper(pub[2], 48)*100:.1f}%) | {pub[3]}/48 | "
                 f"${pub[4]} | {pub[5]} | {pub[6]} | {pub[7]}% "
                 f"({pub[8]}/{pub[9]} verdicts; {pub[10]}/{pub[11]} runs judged) |")
    o.append("\nComparator rows are the published E10 values (asserted above, "
             "not recomputed fresh for this table). The compose row's cost "
             "column is the MAIN RUN only — the compose call is decomposed "
             "below. Turns likewise count the main run only (the compose call "
             "is a single-turn text call).\n")
    o.append(f"- Compose drift cards: {', '.join(f'`{c}`' for c in drift_cards)} "
             f"(vs the comparator's single drift card `{xv_drift_cards[0]}`). "
             f"Compose M5 misses: {', '.join(f'`{c}`' for c in m5_fail_cards)}.")
    o.append(f"- Reading, probe-grade: drift {kd}/48 vs 1/48 and M5 {m5}/48 vs "
             f"{E10_PUBLISHED['export-vague'][3]}/48 are both within what the "
             "temporal gap plus rep-to-rep noise could produce; judged-met is "
             f"a wash ({jshare:.1f}% vs {E10_PUBLISHED['export-vague'][7]}%). "
             "Nothing here suggests composition helps or hurts agent behavior "
             "by more than noise on this corpus.\n")

    o.append("## Compose-cost decomposition (does composition pay for itself?)\n")
    o.append("Economy basis: R4 CLI-reported `total_cost_usd` for the main "
             "run; the compose call's own `total_cost_usd` from its persisted "
             "`compose-result.json`. Card-unit means (mean over cards of the "
             "per-card rep mean).\n")
    o.append("| component | mean USD/run |\n|---|---|")
    o.append(f"| compose-vague main run | ${main_cost:.4f} |")
    o.append(f"| compose call (pre-run) | ${comp_cost:.4f} |")
    o.append(f"| **compose-vague total** | **${total_cost:.4f}** |")
    o.append(f"| export-vague comparator (block is free) | ${xv_cost:.4f} |")
    o.append(f"\n- The compose call adds ${comp_cost:.4f}/run "
             f"({comp_cost / main_cost * 100:.1f}% of the main-run cost). "
             f"Total, composition costs ${total_cost - xv_cost:+.4f}/run vs "
             "the deterministic block — i.e. the composed packet is "
             f"~{(total_cost - xv_cost) / xv_cost * 100:+.1f}% on total spend, "
             "while the export block costs $0 to produce (a deterministic "
             "render of the ledger).")
    o.append("- For composition to \"pay for itself\" it would have to buy "
             "back its own mass in behavior (drift, M5, or judged-met). On "
             "this corpus it does not: drift is nominally worse, M5 nominally "
             "better, judged-met flat — all within probe noise — and the "
             "main-run cost saving vs the comparator "
             f"(${main_cost - xv_cost:+.4f}) is smaller than the compose "
             "call itself.\n")

    o.append("## Coverage and missing data\n")
    o.append(f"- Runs: {done_count}/144 done. {len(run_errors)} permanent "
             "run errors (post-retry):")
    for run_id, attempt, err in run_errors:
        o.append(f"  - `{run_id}`: attempt {attempt} — {err[:90]}")
    o.append(f"- Judge: {j_done}/{j_total} done runs judged; {len(judge_errors)} "
             "excluded as judge errors (judge reply unparseable after one "
             "retry, the recorded exclusion class):")
    for run_id in judge_errors:
        o.append(f"  - `{run_id}`")
    o.append(f"- Judge rows pending: {judge_pending} (drain complete for this "
             "cell)." if judge_pending == 0 else
             f"- Judge rows pending: {judge_pending} — PRELIMINARY for the "
             "judged column.")
    o.append("- Card-unit aggregation absorbs the run errors (affected cards "
             "aggregate over their remaining reps): `nushell-t04` counts from "
             "1 rep, `eslint-t02` and `click-t02` from 2. Comparator "
             "exclusions are as published in e9-e10-analysis-1.md (none; "
             "144/144).\n")

    o.append("## What the composer actually writes (qualitative pass)\n")
    o.append("Eleven composed artifacts read across 8 repos — `click-t01 r7`, "
             "`hugo-t02 r7`, `nushell-t01 r7/r9`, `zod-t04 r7`, "
             "`prettier-t03 r7`, `eslint-t04 r7`, `hono-t02 r7/r8/r9`, "
             "`rich-t01 r7` — each against the card's deterministic export "
             "block, its raw ledger, and its vague prompt.\n")
    o.append(f"- **Shape and length.** Composed blocks average "
             f"{mean(comp_lens):.0f} chars (median {median(comp_lens):.0f}, "
             f"range {min(comp_lens)}-{max(comp_lens)}, n={len(comp_lens)} "
             f"done runs) vs the export block's {mean(exp_lens):.0f} "
             f"(median {median(exp_lens):.0f}) — composition does not "
             "compress; it re-narrates. The composer reliably restructures "
             "the ledger into a task-shaped document: a problem statement "
             "lifted from the vague prompt (which the deterministic block "
             "never contains), then scope/constraints/acceptance criteria "
             "that map 1:1 onto ledger entries, usually with imperative "
             "phrasing (\"Do not touch\", \"Work in these files\").")
    o.append("- **What it keeps.** Scope boundaries and acceptance criteria "
             "survive essentially intact in all eleven reads; a crude "
             "literal-string scan over all done runs finds the card's "
             f"out-of-scope path literals verbatim in the composed text for "
             f"{oos_hits}/{oos_total} (card, path) occurrences "
             f"({oos_hits / oos_total * 100:.1f}%; heuristic — paraphrases "
             "like \"docs, CI, examples\" count as misses). Notably the "
             "composer reads the RAW ledger, not the exported rendering, so "
             "it is not subject to the exporter's 8-path cap: `nushell-t01 "
             "r7` lists `crates/nu-protocol/**` explicitly — an entry the "
             "export block hides behind \"(+3 more)\".")
    o.append("- **What it drops.** Uniformly: the `pylgrim:begin/end` "
             "markers, the managed-block notice, the `[observe]` mode tags, "
             "the Skills footer, and the full-ledger pointer. The E9 result "
             "(mode tags inert on drift) suggests the tag loss is behaviorally "
             "neutral, but the dropped markers mean a repo-hygiene layer "
             "(managed-block detection, staleness tooling) would not "
             "recognize a composed block.")
    o.append("- **Key risk finding — content not traceable to the ledger.** "
             "Three of the eleven artifacts contain material traceable to "
             "NEITHER the ledger NOR the prompt: (1) `click-t01 r7` invents "
             "the technical detail \"when `echo_via_pager=False` and "
             "`color=False`\" — `echo_via_pager` appears nowhere in the "
             "ledger, prompt, or repo instructions; (2) `nushell-t01 r7` and "
             "`r9` invent a test command (`cargo test -p nu-command --lib "
             "http`) never stated anywhere; (3) worst, `hono-t02 r7` "
             "CORRUPTS an exact oracle literal: the acceptance criterion's "
             "expected Location header `%E3%81%93%E3%82%93%E3%81%AB%E3%81%A1"
             "%E3%81%AF` (こんにちは) is reproduced with a duplicated "
             "`%E3%81%AB` (こんににちは) — a wrong expected value handed to "
             "the agent as ground truth. The same card's r7/r8 also append "
             "\"Implementation Guidance\" pseudo-logic (\"if url contains "
             "non-ASCII characters, encode\") that contradicts its own "
             "invalid-percent criterion (`%hello` is pure ASCII yet must "
             "become `%25hello`). All three hono-t02 reps still passed the "
             "deterministic oracle — the agent implemented correct encoding "
             "despite the corrupted literal — so the fidelity failures did "
             "not convert to outcome failures HERE, but a composed packet "
             "that silently mutates ratified acceptance criteria is exactly "
             "the failure mode the ledger exists to prevent, and nothing in "
             "the compose path would catch it.\n")

    o.append("## Is the smart-compose dial worth a registered study?\n")
    o.append(f"On this evidence, no — not as a replacement for the "
             "deterministic export block. Behaviorally the two packets are "
             f"indistinguishable at probe grade (drift {kd}/48 vs 1/48, M5 "
             f"{m5}/48 vs {E10_PUBLISHED['export-vague'][3]}/48, judged-met "
             f"{jshare:.1f}% vs {E10_PUBLISHED['export-vague'][7]}% — every "
             "delta within temporal-gap-plus-noise range), so there is no "
             "effect worth the cost of confirming. Economically composition "
             f"is strictly worse: +${total_cost - xv_cost:.4f}/run "
             f"(~{(total_cost - xv_cost) / xv_cost * 100:.0f}%) against a "
             "free deterministic render, plus a per-run LLM dependency in "
             "the context path. And on fidelity — the one axis where "
             "composition could not merely match but corrupt — it is not "
             "clean: a corrupted oracle literal and two invented technical "
             "details in eleven audited artifacts is a real, recurring "
             "hallucination rate in the exact artifact whose job is to carry "
             "ratified intent verbatim. If composition is ever revisited, "
             "the registered question should not be \"composed vs export on "
             "a clean ledger\" (this probe suggests that answer is \"no "
             "difference, at a cost\") but whether composition earns its keep "
             "where the deterministic exporter cannot go — messy, "
             "unratified, or oversized ledgers — and any such study needs a "
             "fidelity gate (composed content mechanically checked against "
             "ledger literals) as a primary endpoint, because the failure "
             "mode observed here is silent. Until then, the free block wins "
             "by default.\n")

    OUT.write_text("\n".join(o) + "\n", encoding="utf-8")
    print(f"\nwritten: {OUT}")
    print(f"\ncompose-vague@haiku (r7-9): n={n} M1={kt} M3={kv} drift={kd} "
          f"M5={m5}/{n} main=${main_cost:.4f} compose=${comp_cost:.4f} "
          f"total=${total_cost:.4f} churn={churn:.3f} turns={turns:.1f} "
          f"judged={jshare:.1f}% ({j_done}/{j_total})")
    print(f"drift cards: {drift_cards}")
    print(f"coverage: {done_count}/144 done; run errors {len(run_errors)}; "
          f"judge errors {len(judge_errors)}; judge pending {judge_pending}")


if __name__ == "__main__":
    main()
