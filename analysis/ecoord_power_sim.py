#!/usr/bin/env python3
"""E-coord C1 power simulation (design memo backing, NOT confirmatory).

Backs results/reports/ecoord-c1-power-memo.md — the SS5a freeze-gate memo for
preregistration/design-e-coord-draft-3.md including its SS3 composition
amendment (48 scenarios: 12 high / 18 very-high / 18 extreme; C1 exact
two-sided McNemar at alpha=.05 as the sole tested endpoint, bundle vs
control; 3 reps, majority-of-reps per scenario per arm; C5 deterministic
tripwire c-b>=2 spending no alpha).

Method
------
1. GATE: re-derive the calibration / pilot counts from the episode.json
   artifacts under results-vm/episodes/ and abort on any mismatch with the
   numbers this memo quotes.
2. FIT: per-stratum control-arm per-rep collision probabilities as Jeffreys
   Beta posteriors (k+0.5, n-k+0.5) from the 20-episode Haiku gate
   calibration (conf-subset low/medium/high + cal-strata very-high/extreme).
   Only high / very-high / extreme feed the confirmatory composition.
3. SWEEP: treatment effect is UNKNOWN at these strata (pilot treatment data
   exists only at low pressure), so relative per-rep collision reduction r is
   swept over {30%, 50%, 70%, 90%}. Posterior uncertainty is handled by
   sweeping too: the primary condition draws each scenario's propensity from
   the stratum posterior (posterior-predictive, doubling as scenario
   heterogeneity); fixed-p sensitivities run at the posterior mean and at the
   posterior 10th/90th percentiles.
4. SIMULATE: per scenario, 3 reps Bernoulli per arm (shared propensity,
   treatment prob = p*(1-r)), majority-of-3 binarization per arm, exact
   two-sided McNemar on the 48 paired scenario values at alpha=.05; success
   requires rejection in the collision-reducing direction. 20,000 sims per
   grid point; +/-2 simulation SEs reported.
5. TRIPWIRE: false-fire rate of the C5 net-harm tripwire (c-b>=2) under a
   no-harm assumption (identical per-rep success prob q in both arms,
   independent across arms — conservative, since shared scenario effects
   would correlate arms and shrink discordance), q swept over pilot-fitted
   and pessimistic values. 50,000 sims per q.
6. LEVERS: power at the base design vs +12 vh/extreme scenarios (60 total)
   vs 5 reps (majority-of-5) at 48 scenarios, with episode costs.

Seed 42 (house constant). numpy only; exact McNemar via math.comb.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

SEED = 42
ALPHA = 0.05
NSIM_MAIN = 20_000
NSIM_TRIP = 50_000
ROOT = Path(__file__).resolve().parents[1]
EPI = ROOT / "results-vm" / "episodes"

# ---------------------------------------------------------------- gate


def load_episodes():
    eps = []
    for p in sorted(EPI.glob("*/episode.json")):
        with open(p, encoding="utf-8") as f:
            j = json.load(f)
        eps.append(j)
    return eps


def gate(eps):
    """Re-derive every number the memo quotes; abort on mismatch."""

    def coll(js):
        return sum(1 for j in js if j["metrics_inputs"]["c1"]["any_collision"])

    def c5(js):
        return sum(1 for j in js if j["metrics_inputs"]["c5"]["combined_success"])

    def sel(kind, model=None, arm=None, pressure=None):
        out = []
        for j in eps:
            e = j["episode"]
            if e["scenario_id"].split("-")[1] != kind:
                continue
            if model and e["model"] != model:
                continue
            if arm and e["arm"] != arm:
                continue
            if pressure and j["scenario"]["pressure"] != pressure:
                continue
            out.append(j)
        return out

    checks = []
    # gate-calibration control-arm collision counts (haiku), the fit inputs
    for pr, k, n in [("low", 0, 4), ("medium", 1, 4), ("high", 0, 4)]:
        js = sel("conf", "haiku", "coord-none", pr)
        checks.append((f"conf {pr}", coll(js), k, len(js), n))
    for pr, k, n in [("very-high", 3, 4), ("extreme", 2, 4)]:
        js = sel("cal", "haiku", "coord-none", pr)
        checks.append((f"cal {pr}", coll(js), k, len(js), n))
    # haiku re-pilot (6/arm): control 0/6, bundle 1/6, ledger 0/6; C5 17/18
    for arm, k in [("coord-none", 0), ("coord-pylgrim", 1), ("coord-ledger", 0)]:
        js = sel("pilot", "haiku", arm)
        checks.append((f"haiku pilot {arm}", coll(js), k, len(js), 6))
    checks.append(("haiku pilot C5 all arms", c5(sel("pilot", "haiku")), 17, len(sel("pilot", "haiku")), 18))
    # sonnet pilot: only the rep-2 half survives locally (r1 dirs were
    # overwritten by the haiku re-pilot; episodes-pilot-sonnet.db is empty).
    for arm, k in [("coord-none", 2), ("coord-pylgrim", 1), ("coord-ledger", 0)]:
        js = sel("pilot", "sonnet", arm)
        checks.append((f"sonnet pilot r2 {arm}", coll(js), k, len(js), 6))

    ok = True
    for name, got_k, want_k, got_n, want_n in checks:
        status = "OK" if (got_k == want_k and got_n == want_n) else "MISMATCH"
        if status == "MISMATCH":
            ok = False
        print(f"  gate {name}: {got_k}/{got_n} (expect {want_k}/{want_n}) {status}")
    if not ok:
        sys.exit("GATE FAILED: artifact-derived counts do not match memo inputs.")
    print("  GATE PASSED\n")


# ---------------------------------------------------------------- McNemar

_PTAB: dict[int, np.ndarray] = {}


def mcnemar_ptable(n: int) -> np.ndarray:
    """p[k] = exact two-sided McNemar p for min(b,c)=k given b+c=n."""
    if n not in _PTAB:
        tot = 2.0**n
        cdf = np.cumsum([math.comb(n, i) for i in range(n + 1)]) / tot
        _PTAB[n] = np.minimum(1.0, 2.0 * cdf)
    return _PTAB[n]


def mcnemar_reject(b: np.ndarray, c: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    """Vectorized exact two-sided McNemar rejection, collision-reducing
    direction required (b = control-only collision > c = treatment-only)."""
    n = b + c
    p = np.ones(b.shape)
    for nv in np.unique(n):
        if nv == 0:
            continue
        tab = mcnemar_ptable(int(nv))
        m = n == nv
        p[m] = tab[np.minimum(b[m], c[m]).astype(int)]
    return (p < alpha) & (b > c)


# ---------------------------------------------------------------- sim


def beta_q(a: float, b: float, q: float, rng: np.random.Generator) -> float:
    # quantile via a large deterministic sample (no scipy on this host)
    s = rng.beta(a, b, size=400_000)
    return float(np.quantile(s, q))


def run_grid(rng, composition, posts, reductions, mode, reps=3, nsim=NSIM_MAIN):
    """composition: list of (stratum, n_scen). posts: stratum->(a,b) Jeffreys.
    mode: 'pp' (posterior-predictive per-scenario draw) or a fixed float
    quantile/mean key. Returns dict per reduction."""
    n_scen = sum(n for _, n in composition)
    maj = reps // 2 + 1
    out = {}
    # per-scenario stratum index
    strata = []
    for s, n in composition:
        strata += [s] * n
    for r in reductions:
        P = np.empty((nsim, n_scen))
        for i, s in enumerate(strata):
            a, b = posts[s]
            if mode == "pp":
                P[:, i] = rng.beta(a, b, size=nsim)
            elif mode == "mean":
                P[:, i] = a / (a + b)
            else:  # numeric quantile
                P[:, i] = FIXED_Q[(s, mode)]
        ctrl = rng.binomial(reps, P) >= maj
        trt = rng.binomial(reps, P * (1.0 - r)) >= maj
        b_disc = (ctrl & ~trt).sum(axis=1)  # control-only collision (good)
        c_disc = (~ctrl & trt).sum(axis=1)  # treatment-only collision (bad)
        rej = mcnemar_reject(b_disc, c_disc)
        nd = b_disc + c_disc
        power = rej.mean()
        out[r] = dict(
            power=power,
            se2=2 * math.sqrt(power * (1 - power) / nsim),
            e_nd=nd.mean(),
            e_b=b_disc.mean(),
            e_c=c_disc.mean(),
            p_zero=(nd == 0).mean(),
        )
    return out


def tripwire(rng, n_scen, q, reps=3, nsim=NSIM_TRIP):
    maj = reps // 2 + 1
    sc = rng.binomial(reps, q, size=(nsim, n_scen)) >= maj
    st = rng.binomial(reps, q, size=(nsim, n_scen)) >= maj
    c = (sc & ~st).sum(axis=1)  # control-only C5 success
    b = (~sc & st).sum(axis=1)  # treatment-only C5 success
    fire = (c - b >= 2).mean()
    return fire, 2 * math.sqrt(fire * (1 - fire) / nsim)


def main():
    print("== E-coord C1 power sim (seed 42) ==\n")
    eps = load_episodes()
    print(f"loaded {len(eps)} episode.json artifacts from {EPI}")
    gate(eps)

    rng = np.random.default_rng(SEED)

    # Jeffreys posteriors from the gate-calibration control-arm data
    posts = {
        "high": (0.5, 4.5),  # 0/4
        "very-high": (3.5, 1.5),  # 3/4
        "extreme": (2.5, 2.5),  # 2/4
    }
    global FIXED_Q
    FIXED_Q = {}
    print("fitted per-rep control collision posteriors (Jeffreys):")
    for s, (a, b) in posts.items():
        q10 = beta_q(a, b, 0.10, rng)
        q90 = beta_q(a, b, 0.90, rng)
        FIXED_Q[(s, "q10")] = q10
        FIXED_Q[(s, "q90")] = q90
        mean = a / (a + b)
        maj_mean = 3 * mean**2 - 2 * mean**3
        print(
            f"  {s:10s} Beta({a},{b}): mean {mean:.3f}, q10 {q10:.3f}, "
            f"q90 {q90:.3f}; majority-of-3 at mean {maj_mean:.3f}"
        )
    print()

    comp48 = [("high", 12), ("very-high", 18), ("extreme", 18)]
    comp60 = [("high", 12), ("very-high", 24), ("extreme", 24)]
    reductions = [0.30, 0.50, 0.70, 0.90]

    for mode, label in [
        ("pp", "PRIMARY posterior-predictive (per-scenario propensity draw)"),
        ("mean", "fixed p = posterior mean"),
        ("q10", "fixed p = posterior 10th pct (pessimistic base rates)"),
        ("q90", "fixed p = posterior 90th pct (optimistic base rates)"),
    ]:
        print(f"-- 48 scenarios, 3 reps, {label}")
        res = run_grid(rng, comp48, posts, reductions, mode)
        for r in reductions:
            d = res[r]
            print(
                f"   r={int(r*100)}%: P(C1 lands) = {d['power']*100:.1f}% "
                f"+/- {d['se2']*100:.1f}pp | E[discordant] = {d['e_nd']:.1f} "
                f"(b {d['e_b']:.1f} / c {d['e_c']:.1f}) | P(zero disc) = "
                f"{d['p_zero']*100:.2f}%"
            )
        print()

    print("-- C5 tripwire false-fire rate under NO HARM (c-b>=2), 48 scenarios, 3 reps")
    for q, note in [
        (17 / 18, "pilot-fitted per-rep C5 success (haiku pilot 17/18)"),
        (0.80, "moderate degradation at confirmatory strata"),
        (0.50, "coin-flip success"),
        (0.056, "cal-strata-like (Jeffreys mean of 0/8 at vh/extreme)"),
    ]:
        fire, se2 = tripwire(rng, 48, q)
        print(f"   q={q:.3f} ({note}): P(false fire) = {fire*100:.2f}% +/- {se2*100:.2f}pp")
    print()

    print("-- margin reachability: minimal discordance for two-sided exact p<.05")
    for c_adv in range(0, 4):
        for b_need in range(c_adv + 1, 60):
            tab = mcnemar_ptable(b_need + c_adv)
            if tab[min(b_need, c_adv)] < ALPHA:
                print(f"   c={c_adv}: minimal b = {b_need} (p = {tab[min(b_need,c_adv)]:.4f})")
                break
    print()

    print("-- levers at r=30% and r=50% (posterior-predictive)")
    base_eps = 48 * 3 * 3
    lever_defs = [
        ("base: 48 scen x 3 reps", comp48, 3, base_eps),
        ("lever A: 60 scen (12/24/24) x 3 reps", comp60, 3, 60 * 3 * 3),
        ("lever B: 48 scen x 5 reps (maj-5)", comp48, 5, 48 * 3 * 5),
    ]
    for label, comp, reps, cost in lever_defs:
        res = run_grid(rng, comp, posts, [0.30, 0.50], "pp", reps=reps)
        print(
            f"   {label} ({cost} episodes, +{cost-base_eps}): "
            f"r=30% -> {res[0.30]['power']*100:.1f}% +/- {res[0.30]['se2']*100:.1f}pp, "
            f"r=50% -> {res[0.50]['power']*100:.1f}% +/- {res[0.50]['se2']*100:.1f}pp"
        )
    print("\ndone.")


if __name__ == "__main__":
    main()
