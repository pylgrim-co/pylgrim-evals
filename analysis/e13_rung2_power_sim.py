"""E13 rung-2 (sonnet+export vs opus+vanilla) POWER SIMULATION — design memo
support only. NOT a confirmatory analysis; no claim about the observed data is
made beyond what results/reports/e13-analysis-1.md already published.

Question: can the rung-2 non-inferiority miss (one-sided 95% LB -5.3pp vs the
-5pp margin, Tango, n=48 paired cards, M5 majority-of-reps over r4-r6) be
resolved by adding reps (r7-r9), or is it card-bound at n=48?

Method:
  1. Extract per-card rep-level M5 pass flags for the two rung-2 cells
     (export-vague@sonnet, vanilla-vague@opus) at Stage-2 reps 4-6, read-only,
     and GATE on reproducing the published endpoint-3 numbers (M5 46/48 vs
     45/48; b=2, c=1, n=48; Tango 95% CI [-7.4, +12.3]pp; one-sided 95% LB
     -5.3pp; p=0.0548) before simulating anything.
  2. Fit per-card true pass probabilities: empirical-Bayes beta-binomial per
     cell (beta prior fitted by marginal ML over the 48 cards, per-card
     posterior mean). Raw per-card MLE (k/m) kept as a plug-in sensitivity.
  3. Sensitivity-sweep the assumed TRUE card-level M5 (majority-of-3) delta
     from 0 to +3pp by uniformly shifting the opus-cell rep-level probs
     (bisected so the implied majority-of-3 delta hits the target exactly).
  4. Simulate, per assumed delta:
     (a) fresh 3-rep replication at n=48 (reps 7-9 only, majority-of-3):
         P(one-sided 95% Tango LB > -5pp);
     (b) pooled 6-rep analysis conditional on the OBSERVED r4-r6 reps
         (majority-of-6, strict majority, tie=fail): P(LB > -5pp) at the
         nominal one-sided 95% level AND at a corrected one-sided 97.5%
         level (Bonferroni-style alpha-split across the two looks, since
         r4-r6 were already observed and tested);
     (c) the LB distribution (mean, p10/p50/p90) under both designs.
  5. Ceiling: resample n_cards with replacement from the fitted card pairs at
     true delta = 0 (and +2pp), 3 reps, majority-of-3: smallest n_cards with
     >=80% power for the -5pp margin at one-sided alpha=.05.

Usage (from harness/):  uv run python ../analysis/e13_rung2_power_sim.py
Prints a JSON summary; writes nothing to results/.
"""

from __future__ import annotations

import json
import math
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness" / "src"))
sys.path.insert(0, str(ROOT / "analysis"))

from e13_confirmatory import (  # noqa: E402  (reuses the frozen Tango impl)
    tango_ci, tango_lower_bound, tango_one_sided_p,
)

RUNS_DIR = ROOT / "results" / "runs"
DB = ROOT / "results" / "runs.db"

LOW = ("export-vague", "sonnet")   # packet-equipped lower tier
HIGH = ("vanilla-vague", "opus")   # raw higher tier
STAGE2_REPS = (4, 5, 6)
NI_MARGIN = -0.05
N_SIMS = 20_000
N_SIMS_GRID = 4_000
SEED = 42  # house constant

# Published rung-2 endpoint-3 numbers (results/reports/e13-analysis-1.md),
# asserted as a gate before any simulation.
PUBLISHED = {"m5_low": 46, "m5_high": 45, "b": 2, "c": 1, "n": 48,
             "ci": "[-7.4, +12.3]", "lb": "-5.3", "p": "0.0548"}


# --- extraction --------------------------------------------------------------

def load_pass_flags() -> dict[str, dict[str, dict[int, bool]]]:
    """{card: {"low": {rep: passed}, "high": {rep: passed}}} for done runs."""
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    out: dict[str, dict[str, dict[int, bool]]] = {}
    for label, (arm, model) in (("low", LOW), ("high", HIGH)):
        rows = conn.execute(
            "SELECT run_id, rep FROM runs WHERE arm=? AND model=? AND rep>=4 "
            "AND status='done'", (arm, model))
        for r in rows:
            rid = r["run_id"]
            card = rid.split("--")[0]
            p = RUNS_DIR / rid / "result.json"
            if not p.exists():
                continue
            rec = json.loads(p.read_text(encoding="utf-8"))
            passed = bool((rec["metrics"].get("outcome") or {}).get("passed"))
            out.setdefault(card, {"low": {}, "high": {}})[label][int(r["rep"])] = passed
    conn.close()
    return out


def majority(passes: list[bool]) -> bool:
    return sum(passes) * 2 > len(passes)  # strict majority; tie = fail


def reproduce_gate(flags) -> dict:
    """Re-derive the published endpoint-3 numbers with §7 common-rep pairing."""
    b = c = n = m5_low = m5_high = 0
    for card, d in sorted(flags.items()):
        common = sorted(set(d["low"]) & set(d["high"]))
        if not common:
            continue
        n += 1
        pl = majority([d["low"][r] for r in common])
        ph = majority([d["high"][r] for r in common])
        m5_low += pl
        m5_high += ph
        b += pl and not ph
        c += ph and not pl
    lo, hi = tango_ci(b, c, n)
    lb = tango_lower_bound(b, c, n)
    p = tango_one_sided_p(b, c, n, NI_MARGIN)
    got = {"m5_low": m5_low, "m5_high": m5_high, "b": b, "c": c, "n": n,
           "ci": f"[{lo*100:+.1f}, {hi*100:+.1f}]".replace("+", "+").replace("[-", "[-"),
           "lb": f"{lb*100:.1f}", "p": f"{p:.4f}"}
    ok = (m5_low, m5_high, b, c, n) == (
        PUBLISHED["m5_low"], PUBLISHED["m5_high"], PUBLISHED["b"],
        PUBLISHED["c"], PUBLISHED["n"])
    ok &= f"{lo*100:.1f}" == "-7.4" and f"{hi*100:.1f}" == "12.3"
    ok &= f"{lb*100:.1f}" == "-5.3" and f"{p:.4f}" == PUBLISHED["p"]
    if not ok:
        print("REPRODUCTION GATE FAILED — aborting, no simulation run")
        print("got:", got, "\nwant:", PUBLISHED)
        raise SystemExit(1)
    return got


# --- fitting -----------------------------------------------------------------

def _log_betabin(k: int, m: int, a: float, b_: float) -> float:
    return (math.lgamma(m + 1) - math.lgamma(k + 1) - math.lgamma(m - k + 1)
            + math.lgamma(k + a) + math.lgamma(m - k + b_)
            - math.lgamma(m + a + b_)
            + math.lgamma(a + b_) - math.lgamma(a) - math.lgamma(b_))


def fit_beta(counts: list[tuple[int, int]]) -> tuple[float, float]:
    """Marginal-ML beta prior over per-card (k, m) counts; coarse-to-fine grid
    in log-space (pure python, no scipy)."""
    def nll(a, b_):
        return -sum(_log_betabin(k, m, a, b_) for k, m in counts)
    lo_a, hi_a, lo_b, hi_b = math.log(0.02), math.log(2000), math.log(0.02), math.log(2000)
    best = (1.0, 1.0)
    for _ in range(4):
        grid_a = [lo_a + i * (hi_a - lo_a) / 40 for i in range(41)]
        grid_b = [lo_b + i * (hi_b - lo_b) / 40 for i in range(41)]
        scored = min(((nll(math.exp(la), math.exp(lb_)), la, lb_)
                      for la in grid_a for lb_ in grid_b), key=lambda t: t[0])
        _, la, lb_ = scored
        best = (math.exp(la), math.exp(lb_))
        da = (hi_a - lo_a) / 40 * 2
        db = (hi_b - lo_b) / 40 * 2
        lo_a, hi_a = la - da, la + da
        lo_b, hi_b = lb_ - db, lb_ + db
    return best


def per_card_probs(flags, shrink: bool) -> tuple[dict[str, float], dict[str, float]]:
    """Per-card true-pass-prob estimates for each cell, fitted from ALL
    available Stage-2 reps of that cell (2-3 per card)."""
    counts = {"low": [], "high": []}
    cards = sorted(flags)
    for card in cards:
        for lab in ("low", "high"):
            reps = flags[card][lab]
            counts[lab].append((sum(reps.values()), len(reps)))
    out = {}
    priors = {}
    for lab in ("low", "high"):
        if shrink:
            a, b_ = fit_beta(counts[lab])
        else:
            a = b_ = 0.0
        priors[lab] = (a, b_)
        probs = {}
        for card, (k, m) in zip(cards, counts[lab]):
            if shrink:
                probs[card] = (k + a) / (m + a + b_)
            else:
                probs[card] = k / m
        out[lab] = probs
    return out["low"], out["high"], priors


# --- delta sweep -------------------------------------------------------------

def maj3(p: float) -> float:
    return p ** 3 + 3 * p ** 2 * (1 - p)


def clip(p: float) -> float:
    return min(max(p, 1e-4), 1 - 1e-4)


def shift_for_delta(p_low: dict, p_high: dict, target: float) -> dict:
    """Uniform shift s on the opus-cell rep-level probs so the implied TRUE
    card-level majority-of-3 delta equals `target` exactly (bisection)."""
    cards = sorted(p_low)
    m_low = sum(maj3(p_low[c]) for c in cards) / len(cards)

    def implied(s):
        return m_low - sum(maj3(clip(p_high[c] + s)) for c in cards) / len(cards)

    lo, hi = -0.6, 0.6  # implied() increasing in s? shifting high UP lowers delta
    # implied(s) is DECREASING in s. Bisect accordingly.
    for _ in range(80):
        mid = (lo + hi) / 2
        if implied(mid) > target:
            lo = mid
        else:
            hi = mid
    s = (lo + hi) / 2
    return {c: clip(p_high[c] + s) for c in cards}, s


# --- simulation --------------------------------------------------------------

_LB_CACHE: dict[tuple[int, int, int, float], float] = {}


def cached_lb(b: int, c: int, n: int, conf: float) -> float:
    key = (b, c, n, conf)
    if key not in _LB_CACHE:
        if conf == 0.95:
            _LB_CACHE[key] = tango_lower_bound(b, c, n)
        else:  # one-sided 97.5% LB == lower end of the two-sided 95% CI
            _LB_CACHE[key] = tango_ci(b, c, n)[0]
    return _LB_CACHE[key]


def summarize(lbs: list[float]) -> dict:
    lbs = sorted(lbs)
    n = len(lbs)
    return {"mean_pp": round(sum(lbs) / n * 100, 2),
            "p10_pp": round(lbs[int(0.10 * n)] * 100, 2),
            "p50_pp": round(lbs[int(0.50 * n)] * 100, 2),
            "p90_pp": round(lbs[int(0.90 * n)] * 100, 2)}


def sim_fresh(rng, p_low, p_high, n_sims) -> tuple[float, list[float]]:
    cards = sorted(p_low)
    n = len(cards)
    wins = 0
    lbs = []
    for _ in range(n_sims):
        b = c = 0
        for card in cards:
            pl = sum(rng.random() < p_low[card] for _ in range(3)) >= 2
            ph = sum(rng.random() < p_high[card] for _ in range(3)) >= 2
            b += pl and not ph
            c += ph and not pl
        lb = cached_lb(b, c, n, 0.95)
        lbs.append(lb)
        wins += lb > NI_MARGIN
    return wins / n_sims, lbs


def sim_pooled(rng, flags, p_low, p_high, n_sims):
    """Conditional on the OBSERVED common r4-r6 reps; 3 fresh reps appended per
    cell per card; strict majority of the pooled 5-6 reps (tie = fail)."""
    cards = sorted(flags)
    obs = {}
    for card in cards:
        common = sorted(set(flags[card]["low"]) & set(flags[card]["high"]))
        obs[card] = ([flags[card]["low"][r] for r in common],
                     [flags[card]["high"][r] for r in common])
    n = len(cards)
    wins95 = wins975 = 0
    lbs = []
    for _ in range(n_sims):
        b = c = 0
        for card in cards:
            ol, oh = obs[card]
            kl = sum(ol) + sum(rng.random() < p_low[card] for _ in range(3))
            kh = sum(oh) + sum(rng.random() < p_high[card] for _ in range(3))
            ml, mh = len(ol) + 3, len(oh) + 3
            pl = kl * 2 > ml
            ph = kh * 2 > mh
            b += pl and not ph
            c += ph and not pl
        lb95 = cached_lb(b, c, n, 0.95)
        lb975 = cached_lb(b, c, n, 0.975)
        lbs.append(lb95)
        wins95 += lb95 > NI_MARGIN
        wins975 += lb975 > NI_MARGIN
    return wins95 / n_sims, wins975 / n_sims, lbs


def sim_ncards(rng, p_low, p_high, n_cards, n_sims) -> float:
    pairs = [(p_low[c], p_high[c]) for c in sorted(p_low)]
    wins = 0
    for _ in range(n_sims):
        b = c = 0
        for _ in range(n_cards):
            plo, phi = pairs[rng.randrange(len(pairs))]
            pl = sum(rng.random() < plo for _ in range(3)) >= 2
            ph = sum(rng.random() < phi for _ in range(3)) >= 2
            b += pl and not ph
            c += ph and not pl
        wins += cached_lb(b, c, n_cards, 0.95) > NI_MARGIN
    return wins / n_sims


def se2(p: float, n: int) -> float:
    """2x simulation standard error, in pp."""
    return round(2 * math.sqrt(max(p * (1 - p), 1e-12) / n) * 100, 2)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    flags = load_pass_flags()
    gate = reproduce_gate(flags)
    print("REPRODUCTION GATE PASSED:", gate)

    result = {"gate": gate, "sweep": {}, "plugin_sensitivity": {},
              "ncards": {}, "fit": {}}

    p_low, p_high_fit, priors = per_card_probs(flags, shrink=True)
    p_low_raw, p_high_raw, _ = per_card_probs(flags, shrink=False)
    cards = sorted(p_low)
    result["fit"] = {
        "beta_prior_low(a,b)": [round(x, 3) for x in priors["low"]],
        "beta_prior_high(a,b)": [round(x, 3) for x in priors["high"]],
        "mean_rep_p_low": round(sum(p_low.values()) / len(cards), 4),
        "mean_rep_p_high": round(sum(p_high_fit.values()) / len(cards), 4),
        "mean_maj3_low": round(sum(maj3(p) for p in p_low.values()) / len(cards), 4),
        "mean_maj3_high": round(sum(maj3(p) for p in p_high_fit.values()) / len(cards), 4),
        "fitted_maj3_delta_pp": round(
            (sum(maj3(p) for p in p_low.values())
             - sum(maj3(p) for p in p_high_fit.values())) / len(cards) * 100, 2),
    }
    print("FIT:", json.dumps(result["fit"]))

    for delta_pp in (0, 1, 2, 3):
        target = delta_pp / 100.0
        p_high, s = shift_for_delta(p_low, p_high_fit, target)
        rng = random.Random(SEED + delta_pp)
        pa, lbs_a = sim_fresh(rng, p_low, p_high, N_SIMS)
        pb95, pb975, lbs_b = sim_pooled(rng, flags, p_low, p_high, N_SIMS)
        result["sweep"][f"delta_{delta_pp}pp"] = {
            "opus_shift_applied": round(s, 4),
            "P_fresh_3rep_lands": round(pa, 4), "2se_fresh_pp": se2(pa, N_SIMS),
            "P_pooled6_lands_nominal95": round(pb95, 4), "2se_pooled_pp": se2(pb95, N_SIMS),
            "P_pooled6_lands_corrected975": round(pb975, 4),
            "LB_dist_fresh": summarize(lbs_a),
            "LB_dist_pooled6": summarize(lbs_b),
        }
        print(f"delta=+{delta_pp}pp:",
              json.dumps(result["sweep"][f"delta_{delta_pp}pp"]))

    # plug-in (raw MLE) sensitivity, fresh replication only
    for delta_pp in (0, 2):
        target = delta_pp / 100.0
        p_high, s = shift_for_delta(p_low_raw, p_high_raw, target)
        rng = random.Random(1000 + SEED + delta_pp)
        pa, lbs_a = sim_fresh(rng, p_low_raw, p_high, N_SIMS)
        result["plugin_sensitivity"][f"delta_{delta_pp}pp"] = {
            "P_fresh_3rep_lands": round(pa, 4), "2se_pp": se2(pa, N_SIMS),
            "LB_dist_fresh": summarize(lbs_a)}
        print(f"plugin delta=+{delta_pp}pp:",
              json.dumps(result["plugin_sensitivity"][f"delta_{delta_pp}pp"]))

    # ceiling: n_cards for 80% power at 3 reps, majority-of-3
    for delta_pp in (0, 2):
        target = delta_pp / 100.0
        p_high, _ = shift_for_delta(p_low, p_high_fit, target)
        rng = random.Random(2000 + SEED + delta_pp)
        grid = {}
        for n_cards in (48, 96, 144, 192, 240, 288):
            pw = sim_ncards(rng, p_low, p_high, n_cards, N_SIMS_GRID)
            grid[n_cards] = {"power": round(pw, 4), "2se_pp": se2(pw, N_SIMS_GRID)}
        # refine: smallest grid point crossing 0.80, step back by 24
        crossing = min((n for n, d in grid.items() if d["power"] >= 0.80),
                       default=None)
        if crossing and crossing > 48:
            for n_cards in (crossing - 24,):
                pw = sim_ncards(rng, p_low, p_high, n_cards, N_SIMS_GRID)
                grid[n_cards] = {"power": round(pw, 4), "2se_pp": se2(pw, N_SIMS_GRID)}
        result["ncards"][f"delta_{delta_pp}pp"] = dict(sorted(grid.items()))
        print(f"ncards delta=+{delta_pp}pp:",
              json.dumps(result["ncards"][f"delta_{delta_pp}pp"]))

    print("\nSUMMARY_JSON")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
