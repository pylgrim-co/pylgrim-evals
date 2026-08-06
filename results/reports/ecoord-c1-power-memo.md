# E-coord C1 power memo: does 12/18/18 decide the endpoint?

**DESIGN MEMO. Not a confirmatory analysis.** Nothing here is a claim about observed treatment effects — no treatment-arm data exists at the confirmatory strata — and nothing here enters any confirmatory family. This is the §5a freeze gate of `preregistration/design-e-coord-draft-3.md`, answered for the design AS AMENDED by the §3 composition amendment (ratified 2026-08-05): 48 scenarios (12 high / 18 very-high / 18 extreme), C1 exact two-sided McNemar at α=.05 as the sole tested endpoint on bundle-vs-control, 3 reps with majority-of-reps aggregation per scenario per arm, the C5 deterministic tripwire c−b ≥ 2 spending no alpha. Simulation code: `analysis/ecoord_power_sim.py` (seed 42, the house constant). Written 2026-08-06.

## Question

Can 48 paired scenarios at the amended stratum mix decide C1? The original low/medium/high mix pooled to a ~8% control collision rate — below the §6 gate window, the rung-2 undecidable-endpoint failure mode ex ante — which is what forced the amendment. This memo checks that the amended composition actually buys the power the amendment was for, and puts the tripwire's noise behavior on the record before it freezes.

## Answer in one line

Yes for moderate-to-large effects: at the calibration-fitted control rates, P(C1 lands) is **95.6% ± 0.3pp at a 50% relative collision reduction** and ≥ 99.9% at 70-90%, with ~16-23 expected discordant scenarios and P(zero discordance) ≈ 0; the composition is only marginal if the true reduction is ≤ 30% (~51%), and if that risk is to be bought down, **more very-high/extreme scenarios beat more reps ~2.7:1 per episode**.

## Data and gate

All inputs re-derived from the episode artifacts under `results-vm/` before simulation; the script aborts on mismatch (gate PASSED):

- **Gate calibration, control-arm Haiku, per-stratum collisions** (the fit inputs; 20 episodes = `episodes-cal-strata.db` + the confirmatory-subset JSONs): low 0/4, medium 1/4, **high 0/4, very-high 3/4, extreme 2/4**.
- **Haiku re-pilot** (18 episodes, 6/arm, pilot corpus): control 0/6, bundle 1/6, ledger 0/6 collisions; **C5 combined success 17/18** across arms — the tripwire-noise input.
- **Sonnet pilot** (36 episodes, 12/arm): control 2/12, bundle 2/12, ledger 0/12. Verification disclosure: only the rep-2 half is locally verifiable (control 2/6, bundle 1/6, ledger 0/6 — matches); the r1 episode dirs were overwritten by the Haiku re-pilot and the local `episodes-pilot-sonnet.db` copy is empty (0 bytes), so the r1 half is quoted from the drain record, not re-derived. Nothing quantitative in this memo depends on it: it enters only as the statement that **pilot treatment data exists only at low pressure** — the treatment effect at the confirmatory strata is genuinely unknown, hence the sweep.
- File-naming note: the local `episodes.db` is the Sonnet pilot DB (meta: model=sonnet, 36 done); the confirmatory-subset episodes have JSON artifacts but no local DB.
- Model consistency caveat: the calibration rates are **Haiku**; draft-3 §5 still says "one mid-tier alias (sonnet)". This memo's fit is valid for a Haiku confirmatory drain. If the freeze pins sonnet, the fit is off-model (the sonnet pilot's low-pressure control rate, 2/12, is not obviously the same regime) and this memo must be recomputed. The freeze should resolve the model pin explicitly.

## Method

1. **Fit.** Per-stratum control per-rep collision probabilities as Jeffreys posteriors from the calibration counts — tiny n, so posteriors are swept, never point-trusted: high Beta(0.5, 4.5) (mean .100), very-high Beta(3.5, 1.5) (mean .700), extreme Beta(2.5, 2.5) (mean .500).
2. **Treatment sweep.** Relative per-rep collision reduction r ∈ {30%, 50%, 70%, 90%}, applied to the scenario's own propensity (paired).
3. **Uncertainty sweep.** Primary condition: each scenario's propensity drawn from its stratum posterior per sim (posterior-predictive; doubles as scenario heterogeneity, which the 1-rep calibration cannot separate from parameter uncertainty). Sensitivities: fixed p at the posterior mean, 10th percentile (pessimistic), and 90th percentile (optimistic).
4. **Simulate** the design exactly: 48 scenarios (12/18/18), 3 reps Bernoulli per arm, majority-of-3 per scenario per arm, exact two-sided McNemar on the 48 pairs; "lands" = p < .05 in the collision-reducing direction. 20,000 sims per grid point; ±2 simulation SEs.
5. **Tripwire noise:** P(c−b ≥ 2) under no true C5 harm (identical per-rep success q both arms, independent across arms), 50,000 sims per q.

## Results

### P(C1 lands), 48 scenarios, 3 reps

| true reduction r | primary (posterior-predictive) | fixed mean | pessimistic (q10) | optimistic (q90) |
|---|---|---|---|---|
| 30% | 51.0% ± 0.7pp | 53.3% | 16.3% | 80.2% |
| 50% | **95.6% ± 0.3pp** | 95.2% | 45.6% | 99.9% |
| 70% | 99.9% ± 0.0pp | 100.0% | 76.6% | 100.0% |
| 90% | 100.0% ± 0.0pp | 100.0% | 92.8% | 100.0% |

### Discordance (primary condition)

| r | E[discordant pairs] (b good / c bad) | P(zero discordance) |
|---|---|---|
| 30% | 15.7 (12.1 / 3.6) | < 0.01% |
| 50% | 18.7 (16.7 / 2.0) | < 0.01% |
| 70% | 21.3 (20.5 / 0.8) | < 0.01% |
| 90% | 23.0 (22.9 / 0.1) | < 0.01% |

The degenerate case (§5: zero discordance → Clopper-Pearson bound as estimand) is effectively unreachable at the amended composition: even at the pessimistic q10 base rates, E[discordant] ≈ 10-11 and P(zero) ≤ 0.01%. The report will have a testable shape.

### C5 tripwire false-fire rate under no harm (c−b ≥ 2, 48 scenarios, 3 reps)

| per-rep C5 success q | P(false fire) |
|---|---|
| 0.944 (pilot-fitted: haiku pilot 17/18) | **4.7% ± 0.2pp** |
| 0.80 | 30.4% ± 0.4pp |
| 0.50 | 38.1% ± 0.4pp |
| 0.056 (cal-strata-like: 0/8 at vh/extreme) | 4.9% ± 0.2pp |

At the pilot-fitted success rate the tripwire is appropriately quiet (~5%). The honest warning is the middle of the range: if per-scenario success at the harder strata sits anywhere near 0.5-0.8, a no-harm world still fires the tripwire ~30-38% of the time under the independence assumption. Two mitigations are real but unquantifiable from this data: (a) shared scenario difficulty correlates the arms and shrinks discordance, so these are conservative upper bounds; (b) heterogeneous per-scenario q (easy scenarios near 1, hard near 0 — what the calibration data actually suggests) also shrinks discordance relative to homogeneous mid-q. Separately: the calibration episodes went **0/8 on C5 at very-high/extreme**, so the M10 50% framing floor — not the tripwire — is the guard most likely to bind; a C1 win at these strata may only be quotable as "collision reduction in a regime where combined success is not attained". That is the design working as ratified, but it should be walked in with eyes open, and it is now on the record pre-freeze.

## Margin reachability (the rung-2 lesson, discharged)

Rung 2 died by geometry: a −5pp non-inferiority margin at n=48 sits below the design's resolution floor, so even perfect data (b=c=0) misses. **Superiority McNemar has no such floor**, and the reason is structural: NI must push a confidence bound past a fixed margin, whose distance from zero is bounded below by 1/n-scale geometry regardless of the data; superiority only needs the observed discordance to be sufficiently asymmetric under a symmetric null, and the null hypothesis (no difference) is exactly reachable. The minimal significant patterns at α=.05 two-sided: b=6/c=0 (p=.031), b=8/c=1 (p=.039), b=10/c=2 (p=.039), b=12/c=3 (p=.035). Expected discordance at the fitted rates (16-23 pairs, b:c at least 3:1 for r ≥ 30%) sits comfortably above every one of these thresholds — there is no geometric floor problem. The composition amendment is what bought this: at the original ~8% pooled control rate, expected discordance would have been ~3-4 pairs, below the b=6 floor, and the endpoint undecidable — the same death by a different geometry.

## Levers, if the 30% case must be bought down

| design | episodes | Δ episodes | power at r=30% | power at r=50% |
|---|---|---|---|---|
| base: 48 scen × 3 reps | 432 | — | 52.0% ± 0.7pp | 95.2% ± 0.3pp |
| +12 vh/extreme scen (60 × 3 reps) | 540 | +108 | **66.4% ± 0.7pp** | 99.0% ± 0.1pp |
| 5 reps (48 scen, maj-of-5) | 720 | +288 | 65.5% ± 0.7pp | 99.1% ± 0.1pp |

Scenarios beat reps ~2.7:1 per added episode (+0.13pp vs +0.05pp of r=30% power per episode). The mechanism is the rung-2 mechanism again: extra reps only sharpen each scenario's majority toward its own propensity, while extra scenarios are new discordance draws — and discordance is the currency McNemar spends.

## Recommendation

**Freeze at 48 (12/18/18) × 3 reps. The composition is adequate.** It decides the endpoint (≥95% power) for any true relative collision reduction of 50% or more at the fitted rates, the degenerate zero-discordance case is effectively excluded, and the tripwire is quiet at the pilot-fitted C5 rate. The residual risks to accept, explicitly and on the record per §5a: (1) if the true effect is ≤30%, this is a coin flip — but a 30% collision reduction is also close to the smallest effect worth the Team-tier marketing sentence, so an underpowered miss there fails toward honesty, not toward a false claim; (2) if per-scenario C5 success lands mid-range at the hard strata, the tripwire can fire spuriously at a ~30% clip and the framing floor is likely to bind — both are disclosure rules, not tests, so they cost prominence, not validity. If Sam wants the 30% case covered instead of accepted, the pre-registered lever should be **+12 very-high/extreme scenarios (60 total, +108 episodes → 66%)**, not a rep top-up (+288 episodes for the same 66%); at +24 such scenarios the same trend continues and reps never catch up. Any such change is a pre-freeze amendment to the §3 composition, logged like the last one.

*Caveats: stratum fits rest on 4 control episodes each (hence Jeffreys + sweeps, never point estimates); the treatment sweep is a modeling assumption, not data — no treatment episodes exist above low pressure; the posterior-predictive condition conflates parameter uncertainty with scenario heterogeneity because 1-rep calibration cannot separate them; the tripwire model assumes cross-arm independence (conservative). All probabilities carry ±2-SE bars from 20,000 (tripwire: 50,000) sims, seed 42.*
