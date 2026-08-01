# E13 rung-2 power memo: reps or cards?

**DESIGN MEMO. Not a confirmatory analysis.** Nothing here is a claim about the observed Stage-2 data beyond what `e13-analysis-1.md` published, and nothing here enters any confirmatory family. This memo exists to answer one planning question with simulation. Simulation code: `analysis/e13_rung2_power_sim.py` (seed 42, the house constant; reuses the frozen Tango implementation in `analysis/e13_confirmatory.py`). Written 2026-07-29.

## Question

E13 Stage-2 endpoint 3 (M5 non-inferiority at margin −5pp, `export-vague`@sonnet vs `vanilla-vague`@opus) did not land: M5 46/48 vs 45/48 over the same 48 cards, paired; b=2, c=1; two-sided 95% Tango CI [−7.4, +12.3]pp; one-sided 95% LB −5.3pp against a −5pp margin; Holm-adjusted p = 0.0548. The card corpus is fixed at 48 short T-real cards until Wave-2 corpus expansion; reps are the only near-term dial (a top-up would be r7-r9 in the same two cells). **Can adding reps plausibly resolve the miss, or is it card-bound at n=48?**

## Answer in one line

It is card-bound. At n=48 the −5pp margin sits below the resolution floor of the paired design: even a *perfect* outcome (zero discordant cards, b=c=0) gives a one-sided 95% Tango LB of −5.34pp, which still misses the margin. Reps cannot fix that; only cards can.

## Method

1. **Extraction and gate.** Per-card rep-level M5 pass flags for the two rung-2 cells at Stage-2 reps 4-6 were read from `results/runs.db` (read-only) and `results/runs/*/result.json`. Before any simulation, the script re-derives the published endpoint-3 numbers with §7 common-rep pairing and aborts on mismatch. Gate result: M5 46/48 vs 45/48, b=2, c=1, n=48, CI [−7.4, +12.3]pp, LB −5.3pp, p=0.0548. **REPRODUCED.**
2. **Fit.** Per-card true pass probabilities per cell by empirical-Bayes beta-binomial: a beta prior fitted by marginal ML across the 48 cards of each cell (fitted priors: sonnet+export Beta(0.51, 0.02), opus+vanilla Beta(0.36, 0.04); both cells are near-ceiling with a few near-zero cards), then per-card posterior means. Fitted rep-level means 0.958 vs 0.916; implied card-level majority-of-3 means 0.963 vs 0.925. A raw plug-in fit (k/m per card, no shrinkage) is carried as a sensitivity.
3. **Truth sweep.** Because the fitted point estimate should not be trusted as the truth, the assumed *true* card-level majority-of-3 Δ is swept over {0, +1, +2, +3}pp by uniformly shifting the opus-cell rep-level probabilities (shift solved by bisection so the implied majority-of-3 Δ hits the target exactly; heterogeneity structure otherwise preserved).
4. **Simulations** (20,000 sims per condition; error bars are ±2 simulation SEs):
   - (a) **fresh 3-rep replication** at n=48 (r7-r9 only, majority-of-3, one prespecified one-sided test at α=.05): P(one-sided 95% Tango LB > −5pp);
   - (b) **pooled 6-rep analysis** conditional on the observed r4-r6 reps (strict majority-of-6, tie = fail), at the nominal one-sided 95% level and at a corrected one-sided 97.5% level (see the sequential-testing note below);
   - (c) the **LB distributions** under both designs.
5. **Ceiling / Wave-2 sizing.** Cards resampled with replacement from the fitted card pairs; 3 reps, majority-of-3; power = P(one-sided 95% LB > −5pp) at α=.05, 4,000 sims per grid point.

No run-loss model is simulated (all simulated reps complete). Fitting uses all available reps per cell (2-3 per card); pairing in the pooled design uses the observed common reps plus the three simulated ones.

## The geometry that decides the question (n=48, one-sided 95% Tango LB)

| b (export-only-pass) | c (opus-only-pass) | LB | vs −5pp margin |
|---|---|---|---|
| 0 | 0 | −5.34pp | **misses** |
| 1 | 0 | −3.36pp | clears |
| 2 | 0 | −1.39pp | clears |
| 2 | 1 | −5.28pp | **misses (the observed outcome)** |
| 3 | 1 | −3.53pp | clears |
| 4 | 2 | −4.98pp | clears (barely) |

At n=48, clearing −5pp requires a *net-win* discordance pattern (roughly b−c ≥ 1 with c=0, or b−c ≥ 2). Zero discordance, the best a truly-equal pair of cells can converge to, misses. So the miss is not one unlucky card in an otherwise adequate design; the design cannot certify non-inferiority at this margin and this n unless the lower tier visibly wins. (Conversely it was knife-edge in a different sense: had the single c-card gone the other way, b=2/c=0 clears at −1.39pp.)

## Results

### (a) P(fresh 3-rep replication at n=48 lands)

| assumed true Δ (maj-3, card level) | P(LB > −5pp) | LB dist (p10 / median / p90) |
|---|---|---|
| 0pp | 16.7% ± 0.5pp | −10.1 / −7.0 / −3.4pp |
| +1pp | 24.1% ± 0.6pp | −10.1 / −5.3 / −1.4pp |
| +2pp | 34.8% ± 0.7pp | −8.4 / −5.3 / −1.4pp |
| +3pp | 48.6% ± 0.7pp | −8.4 / −5.3 / −0.1pp |

Plug-in sensitivity (no shrinkage): 11.6% ± 0.5pp at Δ=0, 27.3% ± 0.6pp at Δ=+2pp. Even under a generously favorable truth (+3pp, larger than the observed Δ̂ of +2.1pp), a fresh replication is a coin flip at best; under truths near zero it fails five times in six.

### (b) P(pooled 6-rep analysis, reps 4-9, lands) — conditional on the observed r4-r6

| assumed true Δ | nominal one-sided 95% | corrected one-sided 97.5% |
|---|---|---|
| 0pp | 6.3% ± 0.3pp | 5.8% |
| +1pp | 9.9% ± 0.4pp | 6.2% |
| +2pp | 20.4% ± 0.6pp | 6.8% |
| +3pp | 35.4% ± 0.7pp | 10.8% |

**Correction stated:** reps 4-6 were already observed and tested, so pooling reps 4-9 is a second look at partly-seen data. No prespecified group-sequential plan exists, and look 1 already spent the full one-sided α=.05, so a pooled test **cannot be made confirmatory ex post**; the corrected column applies a heuristic Bonferroni-style alpha split (test at one-sided α=.025, i.e. the 97.5% LB), and even that is a courtesy calculation, not a defensible confirmatory rule. A pooled majority-of-6 also changes the pre-pinned M5 binarization (majority-of-reps was pinned at 3 reps; strict majority-of-6 with tie=fail is a different estimand). Under any legitimate framing, the pooled route lands with probability ~6-11%.

### (c) LB distribution under majority-of-6 (pooled)

Median pooled LB is −5.28pp at every swept Δ (p10/p90 range −8.4 to −1.8pp at Δ=+3): the modal pooled outcome *reproduces the observed miss*. Pooling more reps sharpens each card's majority toward its true pass probability, which near ceiling drives discordance toward zero, and b=c=0 misses by construction (the geometry table). This is the card-bound mechanism made visible: more reps push the LB toward −5.34pp, not above −5pp.

## Ceiling: what Wave-2 corpus expansion needs (3 reps, majority-of-3, 80% power)

| n_cards | power at true Δ=0 | power at true Δ=+2pp |
|---|---|---|
| 48 | 25.6% ± 1.4pp | 44.5% ± 1.6pp |
| 96 | 58.8% ± 1.6pp | **83.3% ± 1.2pp** |
| 144 | 76.3% ± 1.4pp | 93.9% ± 0.8pp |
| 168 | **84.3% ± 1.2pp** | — |
| 192 | 85.8% ± 1.1pp | 98.1% ± 0.4pp |

With true pass rates in the observed ~92-96% band, **~160-170 cards** give 80% power for the −5pp margin at 3 reps under the standard NI design assumption (true Δ=0); if the truth is as favorable as +2pp, **~96 cards** suffice. Wave-2 should therefore target roughly **3-3.5× the current corpus** (or accept a wider margin, which would be a new preregistration decision, not a patch).

## Recommendation

Fold rung 2 into Wave-2; do not buy the rep top-up. The miss is card-bound, not rep-bound: at n=48 even a zero-discordance outcome cannot clear the −5pp margin, a fresh r7-r9 replication lands with probability only ~17-49% across the full sweep of plausible truths (roughly a one-in-three chance at the fitted effect size), and every legitimate pooled framing is worse (~6-11%) while raising a sequential-testing problem the prereg discipline exists to avoid. The ~290 additional runs (~$350 at published mean costs) would most likely purchase a second published miss on the same 48 cards. The efficient spend is Wave-2 corpus expansion sized at ~96 cards if we are willing to power against the fitted +2pp truth, ~168 cards for the standard Δ=0 assumption, with rung-2 non-inferiority re-registered as a fresh confirmatory endpoint on the expanded corpus.

*Simulation caveats: per-card probabilities are estimated from at most 3 reps per cell and then shrunk; the truth sweep is the honesty device for that. The uniform-shift construction preserves card heterogeneity but is one of several defensible choices. No run-loss model. All probabilities carry ±2-SE simulation error bars from 20,000 (grid: 4,000) sims.*
