# E8 staleness-study confirmatory analysis · report 1

Executed per `preregistration/prereg-v3-stale.md` (frozen, tag `prereg-v3-stale`, commit 5e0ff13, public before any E8 confirmatory run). Baselines are the already-run Wave-1.5 cells `vanilla-vague` and `export-vague` (same model snapshot and CLI, run 0-2 days earlier; the temporal gap is disclosed per prereg §1, not re-run). Card unit; pairing per-comparison per-card common reps (addendum §7 carried over); R1-ext scrub applied to all context arms (incl. both stale arms) on hugo/nushell/zod; R2 junk filter and R4 CLI-modelUsage economy basis carried over verbatim. Vague artifact unchanged (`tasks/vague/vague-prompts-v1.yaml`, sha 2e41d3aa…). Staleness rule frozen: cyclic-next T-real card in sorted id order (`wrong_card_for`, harness/src/harness/arms.py).

**Finalized 2026-07-22** — supersedes the PRELIMINARY issue: the retry sweep completed the `stale-generic-vague` cell (144/144; the PRELIMINARY issue analyzed it at 142/144), and the judge drain completed, so the judged secondary is now filled in. The registered endpoints used `stale-wrong-vague` only, which was already complete at the PRELIMINARY issue: their b/c/p values are unchanged (re-derived and asserted by the finalization guard in `analysis/e8_confirmatory.py`).

## Regression check (gate, computed before any E8 number)

Two published Wave-1.5 cells re-derived from the same database and asserted against `results/reports/wave15-analysis-1.md`: **PASSED**.

- vanilla-vague: M1 7, M3 9, any-drift 9/48, M5 39/48 (published: M1 7, M3 9, any-drift 9/48, M5 39/48)
- export-vague: M1 1, M3 1, any-drift 1/48, M5 45/48 (published: M1 1, M3 1, any-drift 1/48, M5 45/48)

## The vague-row cells (48 short T-real cards, Sonnet, 3 reps)

| cell | n cards | M1 touched (bound) | M3 violated (bound) | any-drift | mean cost/run | churn share | mean turns | M5 majority-pass | judged met |
|---|---|---|---|---|---|---|---|---|---|
| vanilla-vague | 48 | 7 (≤25.7%) | 9 (≤30.4%) | 9 | $0.854 | 0.239 | 23.3 | 39/48 | 57.2% (141/142 judged) |
| export-vague | 48 | 1 (≤9.5%) | 1 (≤9.5%) | 1 | $0.754 | 0.025 | 18.8 | 45/48 | 84.6% (141/142 judged) |
| stale-generic-vague | 48 | 0 (≤6.1%) | 1 (≤9.5%) | 1 | $0.732 | 0.130 | 20.2 | 44/48 | 64.3% (143/144 judged) |
| stale-wrong-vague | 48 | 6 (≤23.2%) | 6 (≤23.2%) | 6 | $0.674 | 0.185 | 17.1 | 30/48 | 38.3% (143/144 judged) |

`stale-generic-vague` is descriptive only (prereg-v3 §3): its role is the gradient picture, not a headline claim. Bounds above are one-sided exact Clopper-Pearson 95%.

## Confirmatory family (prereg-v3-stale §3; Holm as one family)

| endpoint | result | test | p |
|---|---|---|---|
| 1 · drift, stale-wrong-vague vs export-vague | b=5 (stale-wrong-vague-only), c=0 (export-vague-only), n=48 | exact McNemar | p = 0.0625 |
| 2 · drift, stale-wrong-vague vs vanilla-vague | b=1 (stale-wrong-vague-only), c=4 (vanilla-vague-only), n=48 | exact McNemar | p = 0.3750 |
| 3 · M5 test-pass, stale-wrong-vague vs vanilla-vague | b=0 (stale-wrong-vague-only), c=9 (vanilla-vague-only), n=48 | exact McNemar | p = 0.0039 |
| 4 · economy, stale-wrong-vague − vanilla-vague | Δ = -0.2017 USD/run (inj +0.0032, residual -0.2050) | repo sign-flip (2^10) | p = 0.1211 |

Holm-adjusted: 3 · M5 sw-vs-vv: p_adj = 0.0156; 1 · drift sw-vs-xv: p_adj = 0.1875; 4 · economy sw-vs-vv: p_adj = 0.2422; 2 · drift sw-vs-vv: p_adj = 0.3750.

### Plain-English readings

- **Endpoint 1 (H-E8a):** the wholly stale file drifted on 6/48 cards against the fresh exported file's 1/48. Discordance 5 stale-only vs 0 export-only. The difference does not survive Holm at 0.05; the direction is consistent with H-E8a (more stale-side drift) but not confirmed.
- **Endpoint 2 (H-E8b, drift):** stale-wrong 6/48 drift cards vs no-file 9/48. Discordance 1 stale-only vs 4 vanilla-only. Not significant after Holm: the data do not confirm that a wholly stale file is worse than (or different from) no file on drift.
- **Endpoint 3 (H-E8b, outcome):** majority-of-reps test-pass 30/48 (stale-wrong) vs 39/48 (vanilla). Discordance 0 stale-only-pass vs 9 vanilla-only-pass. The outcome difference survives Holm: the wholly stale file REDUCES test-pass relative to no file — H-E8b's outcome half is confirmed (confident wrong scope steers the agent away from the actual task).
- **Endpoint 4 (economy):** stale-wrong costs -0.2017 USD/run vs vanilla, of which +0.0032 is the mechanical injection mass of the actual rendered stale block and -0.2050 is behavioral residual. Not significant after Holm.

## Injection-mass decomposition (endpoint 4, mandatory)

Economy delta (stale-wrong − vanilla, repo-mean of card-cell means): **$-0.2017** per run = injection overhead **$+0.0032** (the ACTUAL rendered stale block per card at 4 chars/token, cache-write $3.75/MTok once + cache-read $0.3/MTok × (turns−1); labeled estimate) + behavioral residual **$-0.2050**. The stale block still carries mass; it buys nothing by construction.

## Descriptives: the staleness gradient

Any-drift cards per cell, no file → stale-generic → stale-wrong → fresh export:

- vanilla-vague 9/48 · stale-generic-vague 1/48 · stale-wrong-vague 6/48 · export-vague 1/48.
- H-E8c (descriptive only): the generic cell sits between the no-file and fresh-file cells on any-drift; no test is registered for this cell.

## Judged metric (secondary)

- vanilla-vague: 57.2% met (346/605 verdicts; 141/142 runs judged; 1 run(s) excluded — judge reply unparseable after one retry, the recorded exclusion class)
- export-vague: 84.6% met (512/605 verdicts; 141/142 runs judged; 1 run(s) excluded — judge reply unparseable after one retry, the recorded exclusion class)
- stale-generic-vague: 64.3% met (395/614 verdicts; 143/144 runs judged; 1 run(s) excluded — judge reply unparseable after one retry, the recorded exclusion class)
- stale-wrong-vague: 38.3% met (235/614 verdicts; 143/144 runs judged; 1 run(s) excluded — judge reply unparseable after one retry, the recorded exclusion class)

Directional consistency (computed, secondary): the judged-met ordering agrees with the deterministic M5 ordering across all pairs of cells — vanilla-vague 57.2% (M5 39/48) · export-vague 84.6% (M5 45/48) · stale-generic-vague 64.3% (M5 44/48) · stale-wrong-vague 38.3% (M5 30/48). In particular stale-wrong-vague's judged-met share sits well below vanilla-vague's, matching endpoint 3's deterministic finding. No divergence between the judged and deterministic stories.

κ = 0.626 carries from the Wave-1 calibration (disclosed limitation).

## Coverage, exclusions and disclosures

| cell | done / expected |
|---|---|
| vanilla-vague | 142/144 |
| export-vague | 142/144 |
| stale-generic-vague | 144/144 |
| stale-wrong-vague | 144/144 |

- `hono-t01--export-vague--sonnet--r1`: error (claude run timed out after 1800s)
- `hugo-t05--vanilla-vague--sonnet--r2`: error (claude run timed out after 1800s)
- `hugo-t05--vanilla-vague--sonnet--r3`: error (claude run timed out after 1800s)
- `nushell-t04--export-vague--sonnet--r1`: error (claude run timed out after 1800s)
- Baseline (Wave-1.5) exclusions are permanent timeouts recorded in wave15-analysis-1.md.
- §7 truncation applied per comparison: endpoint 1 n=48, endpoints 2-4 n=48 cards with ≥1 common rep.
- E13 Stage-2 rows now share this database under the same arm/model names at reps 4-6; every query in this analysis filters to reps 1-3, the registered scope of this study.
- The database was read-only (`mode=ro`, busy timeout) under live drains; nothing was re-run or mutated.

## Honest-outcome statement

Of the four registered endpoints, 1 survive(s) Holm at 0.05 (3 · M5 sw-vs-vv); not confirmed: 1 · drift sw-vs-xv; 2 · drift sw-vs-vv; 4 · economy sw-vs-vv. Awkward-direction results publish with the same prominence (prereg §2): endpoint 2's drift direction is NOT stale-worse-than-nothing (b=1 vs c=4, the opposite of H-E8b's drift half); H-E8b's outcome half IS confirmed by endpoint 3 (the stale file reduces test-pass vs no file). H-E8b was registered as drift AND/OR outcomes, so the hypothesis stands or falls per channel, as stated above. Every non-significant endpoint is reported as-is, not explained away.

## Claim scoping (binding, prereg-v3-stale §4)

These results are statements about "a wholly out-of-date managed block under issue-text prompts, single-session" — the staleness MODEL is one specific frozen rule (previous-task file, cyclic-next), not a measurement of real-world aging distributions. The Custodian/freshness product mechanism is motivated by, not tested by, this study.

