#!/usr/bin/env python3
"""E-coord wall-clock computations (design memo backing, NOT confirmatory).

Backs results/reports/ecoord-wallclock-memo.md — the SS7 O3 binding memo for
preregistration/design-e-coord-draft-3.md (as amended: 432 confirmatory
episodes at concurrency 2 on the Hetzner VM).

Reads results-vm/*.db (episodes + episode_turns) and
results-vm/episodes/*/episode.json. Where turns carry instrumented wall_s
(all haiku phases), that is the per-turn measure; the sonnet pilot predates
the wall_s instrumentation, so its turn walls are recovered from
episode_turns completion-timestamp differences (turn stamps are written at
turn completion: stamp_k - stamp_{k-1} = wall of turn k, validated against
wall_s in the haiku DBs).

Projection: per-stratum episode-wall pools (high from the certified
confirmatory subset, very-high/extreme from the gate-calibration episodes),
composed per the SS3 amendment (12/18/18 scenarios x 3 arms x 3 reps),
double bootstrap (resample pool, then draw 432 episodes) for a p10/p90
band, serial seconds / 2 for concurrency 2. Seed 42.
"""

from __future__ import annotations

import json
import sqlite3
import statistics as st
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

SEED = 42
ROOT = Path(__file__).resolve().parents[1]
RVM = ROOT / "results-vm"
NBOOT = 4000
JUDGE_VERDICTS = 2 * 432
JUDGE_RATE_PER_MIN = 3.5  # observed judge throughput from prior drains


def ts(x):
    return datetime.fromisoformat(x)


def q(vals, p):
    return float(np.quantile(np.asarray(vals, dtype=float), p))


def load_json_episodes():
    eps = {}
    for p in sorted((RVM / "episodes").glob("*/episode.json")):
        with open(p, encoding="utf-8") as f:
            eps[p.parent.name] = json.load(f)
    return eps


def describe(name, vals, unit="s"):
    v = sorted(vals)
    print(
        f"  {name}: n={len(v)} mean {st.mean(v):.1f}{unit} median {st.median(v):.1f}{unit} "
        f"p10 {q(v,0.10):.1f}{unit} p90 {q(v,0.90):.1f}{unit} max {max(v):.1f}{unit}"
    )


def main():
    eps = load_json_episodes()

    # ---------------- per-turn wall_s (instrumented haiku phases)
    print("== per-turn wall_s (instrumented; haiku) ==")
    by_phase = defaultdict(list)
    all_haiku = []
    for name, j in eps.items():
        if j["episode"]["model"] != "haiku":
            continue
        kind = j["episode"]["scenario_id"].split("-")[1]
        ws = [t["wall_s"] for t in j["turns"] if t.get("wall_s") is not None]
        by_phase[kind] += ws
        all_haiku += ws
    for kind in ("pilot", "cal", "conf"):
        describe(f"haiku {kind}", by_phase[kind])
    describe("haiku ALL", all_haiku)

    # ---------------- turns per episode
    print("\n== turns per episode ==")
    for model in ("haiku", "sonnet"):
        tc = [len(j["turns"]) for j in eps.values() if j["episode"]["model"] == model]
        describe(f"{model} (json artifacts)", tc, unit=" turns")

    # ---------------- per-episode wall from DB timestamps, per phase
    print("\n== per-episode wall (DB started_at -> finished_at), per phase ==")
    db_walls = {}
    for db, label in [
        ("episodes.db", "sonnet pilot (36 eps)"),
        ("episodes-pilot-haiku.db", "haiku re-pilot (18 eps)"),
        ("episodes-cal-strata.db", "cal strata (8 eps)"),
    ]:
        con = sqlite3.connect(RVM / db)
        rows = con.execute(
            "select episode_id, started_at, finished_at, pause_count "
            "from episodes where status='done'"
        ).fetchall()
        walls = {e: (ts(f) - ts(s)).total_seconds() for e, s, f, _ in rows}
        db_walls[label] = walls
        cal_span = (
            max(ts(f) for _, _, f, _ in rows) - min(ts(s) for _, s, _, _ in rows)
        ).total_seconds()
        describe(label, list(walls.values()))
        print(
            f"    drain span {cal_span/3600:.2f} h; sum(ep walls)/span = "
            f"{sum(walls.values())/cal_span:.2f} effective concurrency; "
            f"pauses {sum(p for *_, p in rows)}"
        )
    # conf subset has no local DB; estimate below from wall_s + overhead.

    # ---------------- install/outcome overhead (episode wall - turn wall sum)
    print("\n== per-episode overhead (DB episode wall - sum of instrumented turn wall_s) ==")
    over = []
    for label, dbname in [
        ("haiku re-pilot (18 eps)", "episodes-pilot-haiku.db"),
        ("cal strata (8 eps)", "episodes-cal-strata.db"),
    ]:
        con = sqlite3.connect(RVM / dbname)
        tw = defaultdict(float)
        for e, w in con.execute(
            "select episode_id, wall_s from episode_turns where wall_s is not null"
        ):
            tw[e] += w
        ov = [db_walls[label][e] - tw[e] for e in db_walls[label]]
        over += ov
        describe(f"overhead {label}", ov)
    overhead_mean = st.mean(over)
    print(f"  pooled overhead mean: {overhead_mean:.0f}s per episode (n={len(over)})")

    # ---------------- sonnet fallback: turn walls from completion stamps
    print("\n== sonnet pilot (pre-instrumentation) turn walls from stamp diffs ==")
    con = sqlite3.connect(RVM / "episodes.db")
    stamps = defaultdict(list)
    for e, i, c in con.execute(
        "select episode_id, turn_idx, created_at from episode_turns order by episode_id, turn_idx"
    ):
        stamps[e].append((i, ts(c)))
    gaps = []
    spans = []
    for e, lst in stamps.items():
        lst.sort()
        gaps += [(t2 - t1).total_seconds() for (_, t1), (_, t2) in zip(lst, lst[1:])]
        spans.append((lst[-1][1] - lst[0][1]).total_seconds())
    describe("sonnet turn walls (stamp diffs, turn_idx>=1)", gaps)
    describe("sonnet episode active span (first->last stamp)", spans)
    print(
        "  NOTE: sonnet DB started_at/finished_at imply overlap up to 18 episodes\n"
        "  and stamp-derived turn walls (median ~11s) are inconsistent with the\n"
        "  episode walls (median ~24 min) - the sonnet timing rows look like a\n"
        "  batched import and are treated as UNRELIABLE; the projection below is\n"
        "  haiku-based (the model the calibration data and composition amendment\n"
        "  are fitted on)."
    )

    # ---------------- projection: 432 episodes at concurrency 2
    print("\n== 432-episode confirmatory projection (concurrency 2, seed 42) ==")
    # per-stratum episode-wall pools (haiku):
    #  high      <- certified confirmatory-subset high episodes (json wall_s sum + overhead)
    #  very-high <- cal DB walls, very-high scenarios
    #  extreme   <- cal DB walls, extreme scenarios
    pools = {"high": [], "very-high": [], "extreme": []}
    cal_press = {
        name: j["scenario"]["pressure"]
        for name, j in eps.items()
        if name.startswith("ecoord-cal-")
    }
    for e, w in db_walls["cal strata (8 eps)"].items():
        pools[cal_press[e]].append(w)
    for name, j in eps.items():
        if name.startswith("ecoord-conf-") and j["scenario"]["pressure"] == "high":
            pools["high"].append(sum(t["wall_s"] for t in j["turns"]) + overhead_mean)
    for s, v in pools.items():
        describe(f"pool {s}", v)

    rng = np.random.default_rng(SEED)
    comps = {
        "base (48 scen x 3 arms x 3 reps = 432 eps)": {"high": 108, "very-high": 162, "extreme": 162},
        "lever: ledger reps=2 (384 eps)": {"high": 96, "very-high": 144, "extreme": 144},
    }
    r4_frac = r4_savings_fraction(eps)
    results = {}
    for label, comp in comps.items():
        totals = []
        for _ in range(NBOOT):
            tot = 0.0
            for s, n in comp.items():
                pool = np.asarray(pools[s])
                boot = rng.choice(pool, size=len(pool), replace=True)  # pool uncertainty
                tot += rng.choice(boot, size=n, replace=True).sum()
            totals.append(tot)
        days = np.asarray(totals) / 2 / 86400  # concurrency 2
        results[label] = days
        print(
            f"  {label}: {days.mean():.2f} days "
            f"(p10 {q(days,0.10):.2f} / p90 {q(days,0.90):.2f}); "
            f"serial would be {days.mean()*2:.2f} days"
        )
        print(
            f"    with R=4 cap (measured -{r4_frac*100:.1f}% turn wall): "
            f"{days.mean()*(1-r4_frac):.2f} days"
        )
    # judge add-on
    judge_h = JUDGE_VERDICTS / JUDGE_RATE_PER_MIN / 60
    print(
        f"\n  judge drain add-on: <= {JUDGE_VERDICTS} verdicts at "
        f"~{JUDGE_RATE_PER_MIN}/min = {judge_h:.1f} h ({judge_h/24:.2f} days)"
    )
    exp_turns = st.mean(len(j["turns"]) for j in eps.values() if j["episode"]["model"] == "haiku")
    print(
        f"  expected CLI completions: 432 x {exp_turns:.1f} turns/ep ~= "
        f"{432*exp_turns:.0f}"
    )


def r4_savings_fraction(eps):
    """Measured fraction of haiku turn wall spent in turns with turn_idx>=8
    (the turns an R=4 cap would remove)."""
    tot = 0.0
    beyond = 0.0
    for j in eps.values():
        if j["episode"]["model"] != "haiku":
            continue
        for t in j["turns"]:
            if t.get("wall_s") is None:
                continue
            tot += t["wall_s"]
            if t["turn_idx"] >= 8:
                beyond += t["wall_s"]
    return beyond / tot


if __name__ == "__main__":
    main()
