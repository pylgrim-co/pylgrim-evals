# Wave-1.5 confirmatory analysis · report 1

Executed per `preregistration/prereg-v2-ext.md` (frozen 99a4f16, tag `prereg-v2-ext`, public before any confirmatory run). Factorial card set: the 48 short T-real cards; Wave-1 cells restricted to that set. Pairing: per-comparison per-card common reps (§7 carried over). R1-ext scrub applied to context arms on hugo/nushell/zod. Wave-1 regression check PASSED (vanilla M1 1 / M3 2 cards; claudemd 0/0, reproduced from stored artifacts before any new number was read).

## The six-cell factorial

| cell | n cards | M1 touched (bound) | M3 violated (bound) | any-drift | mean cost/run | churn share | mean turns | M5 majority-pass | judged met |
|---|---|---|---|---|---|---|---|---|---|
| vanilla | 48 | 1 (≤9.5%) | 2 (≤12.5%) | 2 | $0.853 | 0.046 | 22.0 | 36/48 | 82.4% |
| claudemd | 48 | 0 (≤6.1%) | 0 (≤6.1%) | 0 | $0.790 | 0.104 | 20.4 | 38/48 | 84.4% |
| export | 48 | 1 (≤9.5%) | 3 (≤15.4%) | 3 | $0.754 | 0.035 | 19.1 | 47/48 | 84.2% |
| vanilla-vague | 48 | 7 (≤25.7%) | 9 (≤30.4%) | 9 | $0.854 | 0.239 | 23.3 | 39/48 | 57.2% |
| claudemd-vague | 48 | 0 (≤6.1%) | 1 (≤9.5%) | 1 | $0.698 | 0.013 | 18.0 | 46/48 | 82.8% |
| export-vague | 48 | 1 (≤9.5%) | 1 (≤9.5%) | 1 | $0.754 | 0.025 | 18.8 | 45/48 | 84.6% |

## Confirmatory family (Holm as one family)

| endpoint | result | test | p |
|---|---|---|---|
| 1 · drift, vanilla-vague vs export-vague | b=8 (vv-only), c=0 (xv-only), n=48 | exact McNemar | p = 0.0078 |
| 2 · economy, export-vague − vanilla-vague | Δ = -0.0913 USD/run (inj +0.0036, residual -0.0950) | repo sign-flip | p = 0.7227 |
| 3 · format, export − claudemd | Δ = -0.0419 USD/run (block-mass Δ +0.0008); drift claudemd 0/48 vs export 3/48 | repo sign-flip | p = 0.2871 |
| 4 · M5 test-pass, vanilla-vague vs export-vague | b=1 (vv-only-pass), c=7 (xv-only-pass) | exact McNemar | p = 0.0703 |

Holm-adjusted: 1 · drift vague-row: p_adj = 0.0312; 4 · M5 vague-row: p_adj = 0.2109; 3 · format channel economy: p_adj = 0.5742; 2 · economy vague-row: p_adj = 0.7227.

## Exclusions and disclosures

- Coding runs: 572/576 complete; 4 exclusions: nushell-t04--export-vague--sonnet--r1 (claude run timed out after 1800s); hono-t01--export-vague--sonnet--r1 (claude run timed out after 1800s); hugo-t05--vanilla-vague--sonnet--r2 (claude run timed out after 1800s); hugo-t05--vanilla-vague--sonnet--r3 (claude run timed out after 1800s).
- Judge runs: 9 unparseable-after-one-retry across both waves (recorded, excluded).
- Judged metric remains secondary, κ = 0.626 carried from the Wave-1 calibration.

