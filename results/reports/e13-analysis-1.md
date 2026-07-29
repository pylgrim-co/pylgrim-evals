# E13 Stage-2 tier-crossing confirmatory analysis · report 1

Executed per `preregistration/prereg-v5-tiercross.md` (frozen, tag `prereg-v5-tiercross`, commit 2a9db33, committed/tagged/pushed before any Stage-2 row was appended). Five fresh cells, 48 short T-real cards, vague-prompt row, Stage-2 reps r4-r6 ONLY (the prereg's mechanical fresh-data rule; no Wave-1.5/E10/Stage-1 run enters the family): `export-vague`@haiku, `vanilla-vague`@sonnet, `export-vague`@sonnet, `vanilla-vague`@opus, `export-vague`@opus. Model snapshots as recorded per-run by provenance (E10 convention; the union per tier — the CLI also invokes an auxiliary Haiku model inside sonnet/opus runs, so that snapshot appears in their unions too): haiku: claude-haiku-4-5-20251001; sonnet: claude-haiku-4-5-20251001, claude-sonnet-4-6; opus: claude-haiku-4-5-20251001, claude-opus-4-8. The opus alias resolved to `claude-opus-4-8`, matching the prereg's smoke disclosure. Card = unit; pairing per-comparison per-card common Stage-2 reps (addendum §7 carried verbatim, the (arm, model) cell in the role §7 gives an arm). M5 binarization is the pre-pinned majority-of-reps rule (prereg-v2-ext endpoint 4). R1-ext scrub on hugo/nushell/zod context arms, R2 junk filter, R4 CLI-modelUsage economy basis, degenerate-case rule: carried verbatim from prereg-v2-ext. Vague artifact unchanged (`tasks/vague/vague-prompts-v1.yaml`, sha 2e41d3aa…); vendored exporter pylgrim-repo 00ff5a1. Judged metric secondary (κ = 0.626 from the Wave-1 calibration; the same Sonnet judge scores haiku, sonnet AND opus agents — the same-judge-different-agent asymmetry now spans three tiers, disclosed wherever judged numbers appear). Database read-only (`mode=ro`, busy timeout); nothing re-run or mutated.

**Hypothesis source (disclosed):** the Stage-1 exploratory peek in `e9-e10-analysis-1.md` (haiku→sonnet direction only; sonnet→opus was unpeeked). Stage 2 confirms or kills on this fresh data alone; either outcome publishes with the same prominence.

## Regression check (gate, computed before any Stage-2 number)

Published Wave-1.5 and E10 cells (and the published E10 endpoint-3 discordance) re-derived from the same database at reps 1-3 and asserted against `wave15-analysis-1.md` / `e9-e10-analysis-1.md`: **PASSED**.

- vanilla-vague @ sonnet (W1.5, reps 1-3): M1 7, M3 9, any-drift 9/48, M5 39/48, mean cost/run $0.854 (published: M1 7, M3 9, any-drift 9/48, M5 39/48, $0.854) — REPRODUCES
- export-vague @ sonnet (W1.5, reps 1-3): M1 1, M3 1, any-drift 1/48, M5 45/48, mean cost/run $0.754 (published: M1 1, M3 1, any-drift 1/48, M5 45/48, $0.754) — REPRODUCES
- vanilla-vague @ haiku (E10, reps 1-3): M1 13, M3 14, any-drift 14/48, M5 38/48, mean cost/run $0.458 (published: M1 13, M3 14, any-drift 14/48, M5 38/48, $0.458) — REPRODUCES
- export-vague @ haiku (E10, reps 1-3): M1 0, M3 1, any-drift 1/48, M5 42/48, mean cost/run $0.382 (published: M1 0, M3 1, any-drift 1/48, M5 42/48, $0.382) — REPRODUCES
- E10 endpoint 3 (drift, vanilla-vague vs export-vague @ haiku, reps 1-3): b=13, c=0, n=48, p=0.0002 (published: b=13, c=0, n=48, p=0.0002) — REPRODUCES

## Coverage (scheduled / done / judged per cell)

| cell | scheduled | done | runs judged | judge errors |
|---|---|---|---|---|
| export-vague @ haiku | 144 | 143 | 143/143 | 0 |
| vanilla-vague @ sonnet | 144 | 140 | 137/140 | 3 |
| export-vague @ sonnet | 144 | 143 | 142/143 | 1 |
| vanilla-vague @ opus | 144 | 141 | 138/141 | 3 |
| export-vague @ opus | 144 | 144 | 143/144 | 1 |
| **total** | 720 | 711 | 703 | 8 |

## The cells (48 short T-real cards, vague prompts, Stage-2 reps r4-r6)

| cell | model | n cards | M1 touched (bound) | M3 violated (bound) | any-drift | mean cost/run | churn share | mean turns | M5 majority-pass | agent_committed runs | judged met |
|---|---|---|---|---|---|---|---|---|---|---|---|
| export-vague | haiku | 48 | 0 (≤6.1%) | 1 (≤9.5%) | 1 | $0.375 | 0.041 | 34.4 | 46/48 | 16 | 77.0% (143/143 judged) |
| vanilla-vague | sonnet | 47 | 8 (≤28.6%) | 10 (≤33.4%) | 10 | $0.907 | 0.246 | 24.2 | 38/47 | 0 | 56.0% (137/140 judged) |
| export-vague | sonnet | 48 | 0 (≤6.1%) | 0 (≤6.1%) | 0 | $0.707 | 0.000 | 18.0 | 46/48 | 0 | 83.8% (142/143 judged) |
| vanilla-vague | opus | 48 | 9 (≤30.4%) | 11 (≤35.1%) | 11 | $1.735 | 0.125 | 28.5 | 45/48 | 0 | 65.7% (138/141 judged) |
| export-vague | opus | 48 | 0 (≤6.1%) | 0 (≤6.1%) | 0 | $1.330 | 0.000 | 20.2 | 47/48 | 0 | 84.7% (143/144 judged) |

Bounds are one-sided exact Clopper-Pearson 95%. Cost is NOT comparable across tiers on a per-token basis — the cross-tier economy comparison below compares SPEND, not tokens (different per-token pricing); that asymmetry is the commercial point and is stated wherever the number appears.

## Confirmatory family (prereg-v5-tiercross; Holm as ONE family of four)

| endpoint | result | test | p |
|---|---|---|---|
| 1 · M5 non-inferiority (−5pp), export-vague@haiku vs vanilla-vague@sonnet | Δ̂ = +14.9pp (b=7 export-vague@haiku-only-pass, c=0 vanilla-vague@sonnet-only-pass, n=47); 95% Tango CI [+6.2, +27.7]pp; one-sided 95% LB +8.3pp | one-sided Tango score, H0: Δ ≤ −5pp | p = 0.0009 |
| 2 · drift M1∪M3, export-vague@haiku vs vanilla-vague@sonnet | b=1 (export-vague@haiku-only-drift), c=10 (vanilla-vague@sonnet-only-drift), n=47 | exact McNemar, two-sided | p = 0.0117 |
| 3 · M5 non-inferiority (−5pp), export-vague@sonnet vs vanilla-vague@opus | Δ̂ = +2.1pp (b=2 export-vague@sonnet-only-pass, c=1 vanilla-vague@opus-only-pass, n=48); 95% Tango CI [-7.4, +12.3]pp; one-sided 95% LB -5.3pp | one-sided Tango score, H0: Δ ≤ −5pp | p = 0.0548 |
| 4 · drift M1∪M3, export-vague@sonnet vs vanilla-vague@opus | b=0 (export-vague@sonnet-only-drift), c=11 (vanilla-vague@opus-only-drift), n=48 | exact McNemar, two-sided | p = 0.0010 |

Holm-adjusted: 1 · M5 NI haiku→sonnet: p_adj = 0.0034; 4 · drift sonnet→opus: p_adj = 0.0034; 2 · drift haiku→sonnet: p_adj = 0.0234; 3 · M5 NI sonnet→opus: p_adj = 0.0548.

Non-inferiority decision rule as frozen: the claim holds iff the Holm-adjusted one-sided Tango score p < .05 — equivalently the one-sided Holm-level lower confidence bound for Δ lies above −0.05. The two-sided 95% Tango score CIs above are reported regardless. Any improvement beyond non-inferiority is exploratory, not claimed as confirmed (prereg-v1 H3 language carried over).

### Plain-English readings

- **Endpoint 1 (M5 non-inferiority, haiku→sonnet):** M5 46/48 for export-vague@haiku vs 38/47 for vanilla-vague@sonnet; paired Δ̂ = +14.9pp (95% Tango CI +6.2 to +27.7pp). The Holm-adjusted one-sided p (0.0034) is below .05, so the one-sided Holm-level lower bound for Δ lies above −5pp: **non-inferiority HOLDS** at this rung.
- **Endpoint 2 (drift, haiku→sonnet):** Drift 1/48 for export-vague@haiku vs 10/47 for vanilla-vague@sonnet; discordance b=1 (export-vague@haiku-only) vs c=10 (vanilla-vague@sonnet-only). Survives Holm (p_adj = 0.0234): the packet-equipped lower tier drifts LESS than the raw next tier up — **drift superiority CONFIRMED**.
- **Endpoint 3 (M5 non-inferiority, sonnet→opus):** M5 46/48 for export-vague@sonnet vs 45/48 for vanilla-vague@opus; paired Δ̂ = +2.1pp (95% Tango CI -7.4 to +12.3pp). The Holm-adjusted one-sided p (0.0548) is not below .05 — the CI does not exclude the −5pp margin: **non-inferiority is NOT established** at this rung, and the tier-crossing claim dies at this boundary (published as-is, per the prereg).
- **Endpoint 4 (drift, sonnet→opus):** Drift 0/48 for export-vague@sonnet vs 11/48 for vanilla-vague@opus; discordance b=0 (export-vague@sonnet-only) vs c=11 (vanilla-vague@opus-only). Survives Holm (p_adj = 0.0034): the packet-equipped lower tier drifts LESS than the raw next tier up — **drift superiority CONFIRMED**.

## Descriptives (registered as such; no tests run)

### Cost-per-completed-task (R4 CLI-modelUsage basis; completed = M5-passing run)

Injection-mass decomposition per addendum §3 (labeled estimates at 4 chars/token; cache-write/read USD per MTok — Sonnet 3.75/0.3, Haiku 1.25/0.1, Opus 6.25/0.5; the Opus constants are new this analysis — base $5/MTok input for `claude-opus-4-8` at the house 1.25×-write / 0.1×-read basis — and are labeled estimates, used only in this descriptive section):

| cell | mean cost/run (decomposition) | completed runs | cost per completed task |
|---|---|---|---|
| export-vague @ haiku | $0.374 (inj $0.0018, behavioral $0.372) | 133/143 | $0.402 |
| vanilla-vague @ sonnet | $0.882 (inj $0.0000, behavioral $0.882) | 111/140 | $1.113 |
| export-vague @ sonnet | $0.697 (inj $0.0035, behavioral $0.694) | 137/143 | $0.728 |
| vanilla-vague @ opus | $1.717 (inj $0.0000, behavioral $1.717) | 129/141 | $1.876 |
| export-vague @ opus | $1.330 (inj $0.0063, behavioral $1.323) | 141/144 | $1.358 |

This table is run-weighted (all done Stage-2 runs of the cell); the cell table above is card-weighted (mean of per-card means), so the two mean-cost columns can differ in the third decimal.

### Cross-tier spend (the tier-crossing economics; SPEND, not tokens)

- **haiku+export − sonnet+vanilla**: Δ = -0.5319 USD/run over 47 §7-paired cards (export-block injection mass at Haiku pricing +0.0018; behavioral residual -0.5338). Cross-tier cost compares spend, not tokens — different per-token pricing; that asymmetry is the commercial point.
- **sonnet+export − opus+vanilla**: Δ = -1.0183 USD/run over 48 §7-paired cards (export-block injection mass at Sonnet pricing +0.0036; behavioral residual -1.0219). Same spend-not-tokens caveat.

### Within-tier packet effect on opus (cells 4 vs 5; descriptive)

- Drift: vanilla-vague@opus 11/48 (bound ≤35.1%) vs export-vague@opus 0/48 (bound ≤6.1%); discordance 0 export-only vs 11 vanilla-only (n=48). No test registered; none run.
- M5: vanilla-vague@opus 45/48 (fail 3/48, bound ≤15.4%) vs export-vague@opus 47/48 (fail 1/48, bound ≤9.5%); discordance 2 export-only-pass vs 0 vanilla-only-pass.

### Capability-gap reference (packet held fixed; descriptive)

- export-vague@haiku vs export-vague@sonnet: drift 1/48 vs 0/48; M5 46/48 vs 46/48 (discordance 1 haiku-only-pass vs 1 sonnet-only-pass, n=48); mean cost/run $0.374 vs $0.697 (spend, not tokens).

### agent_committed runs per cell (E10 convention)

- export-vague@haiku: 16; vanilla-vague@sonnet: 0; export-vague@sonnet: 0; vanilla-vague@opus: 0; export-vague@opus: 0.

## Judged metric (secondary; κ = 0.626)

- export-vague@haiku: 77.0% met (473/614 verdicts; 143/143 runs judged)
- vanilla-vague@sonnet: 56.0% met (330/589 verdicts; 137/140 runs judged; 3 run(s) excluded — judge reply unparseable after one retry, the recorded exclusion class)
- export-vague@sonnet: 83.8% met (511/610 verdicts; 142/143 runs judged; 1 run(s) excluded — judge reply unparseable after one retry, the recorded exclusion class)
- vanilla-vague@opus: 65.7% met (387/589 verdicts; 138/141 runs judged; 3 run(s) excluded — judge reply unparseable after one retry, the recorded exclusion class)
- export-vague@opus: 84.7% met (520/614 verdicts; 143/144 runs judged; 1 run(s) excluded — judge reply unparseable after one retry, the recorded exclusion class)

κ = 0.626 carries from the Wave-1 calibration. The same Sonnet judge scores haiku, sonnet AND opus agents — the same-judge-different-agent asymmetry now spans three tiers and applies to every judged number above (disclosed per prereg).

## Missing data (the 17 affected rows)

Missing-data handling: the prereg carries addendum §7 verbatim — each comparison uses per-card common Stage-2 reps across its two cells (complete-case at the rep level; a card drops from a comparison only when NO common rep exists). No imputation. Judged secondary is complete-case over judged runs (errored judge rows are the recorded exclusion class, per the E8/E9/E10 precedent).

### 9 coding-run errors (permanent after the retry sweep)

| run | class | error |
|---|---|---|
| `click-t05--vanilla-vague--opus--r6` | ops-caused kill (NOT a model failure) | git rev-parse HEAD failed (exit 3221225794): |
| `hono-t01--export-vague--sonnet--r4` | double timeout (attempt 2, 1800s) | claude run timed out after 1800s |
| `hugo-t04--vanilla-vague--sonnet--r5` | crash (claude exited abnormally) | claude exited 3221226505: |
| `hugo-t05--vanilla-vague--sonnet--r4` | double timeout (attempt 2, 1800s) | claude run timed out after 1800s |
| `hugo-t05--vanilla-vague--sonnet--r5` | double timeout (attempt 2, 1800s) | claude run timed out after 1800s |
| `hugo-t05--vanilla-vague--sonnet--r6` | double timeout (attempt 2, 1800s) | claude run timed out after 1800s |
| `nushell-t04--vanilla-vague--opus--r4` | double timeout (attempt 2, 1800s) | claude run timed out after 1800s |
| `prettier-t04--export-vague--haiku--r6` | crash (claude exited abnormally) | claude exited 3221226505: |
| `zod-t05--vanilla-vague--opus--r6` | ops-caused kill (NOT a model failure) | git rev-parse HEAD failed (exit 3221225794): |

### 8 judge-run errors (recorded exclusion class)

- `hono-t01--vanilla-vague--sonnet--r4`: judge reply unparseable after one retry
- `hono-t01--vanilla-vague--sonnet--r5`: judge reply unparseable after one retry
- `nushell-t02--vanilla-vague--opus--r5`: judge reply unparseable after one retry
- `nushell-t03--export-vague--opus--r6`: judge reply unparseable after one retry
- `prettier-t03--export-vague--sonnet--r6`: judge reply unparseable after one retry
- `rich-t01--vanilla-vague--opus--r4`: judge reply unparseable after one retry
- `rich-t01--vanilla-vague--opus--r6`: judge reply unparseable after one retry
- `rich-t01--vanilla-vague--sonnet--r5`: judge reply unparseable after one retry

### §7 truncation consequences

- Endpoints 1-2 (haiku→sonnet): n = 47 cards with ≥1 common Stage-2 rep — `hugo-t05` drops entirely (all three vanilla-vague@sonnet Stage-2 reps are permanent timeouts).
- Endpoints 3-4 (sonnet→opus): n = 48 cards with ≥1 common Stage-2 rep.
- export-vague@haiku cards below 3 Stage-2 reps: prettier-t04 (reps [4, 5]).
- vanilla-vague@sonnet cards below 3 Stage-2 reps: hugo-t04 (reps [4, 6]); hugo-t05 (reps []).
- export-vague@sonnet cards below 3 Stage-2 reps: hono-t01 (reps [5, 6]).
- vanilla-vague@opus cards below 3 Stage-2 reps: click-t05 (reps [4, 5]); nushell-t04 (reps [5, 6]); zod-t05 (reps [4, 5]).

## Deviations from the prereg

- **None in the analysis plan**: endpoints, margins, pairing, binarization, Holm family, degenerate rule, and shared R-rules are executed exactly as frozen.
- **Coverage shortfall, disclosed**: 711/720 scheduled runs completed; 9 permanent run errors and 8 judge errors are itemized above and handled by the frozen §7 rule (complete-case), not imputed. 2 of the 9 run errors (`zod-t05--vanilla-vague--opus--r6`, `click-t05--vanilla-vague--opus--r6`, both `git rev-parse HEAD failed`) were caused by an operational kill of the worker process, NOT by model behavior — they are excluded as environment losses, and their cards pair on the surviving common reps.
- **Opus injection-pricing constants** (cache-write $6.25/MTok, cache-read $0.5/MTok) were not in the prereg (which froze no pricing table); they are labeled estimates on the house basis, used only in the descriptive economy section — never in the confirmatory family.
- **Tango implementation**: the prereg names the test; the constrained-MLE score statistic (Tango 1998) is implemented pure-python in `analysis/e13_confirmatory.py` (quadratic constrained MLE; verified to reduce to McNemar's z at Δ = 0).

## Honest-outcome statement

Of the four registered endpoints, 3 survive(s) Holm at 0.05 (1 · M5 NI haiku→sonnet; 2 · drift haiku→sonnet; 4 · drift sonnet→opus); not confirmed: 3 · M5 NI sonnet→opus. H-E13 (packet-equipped lower tier non-inferior on task success AND superior on drift at both boundaries): **the haiku→sonnet boundary lands in full**; **the sonnet→opus boundary does NOT land in full**. Where a boundary fails, the tier-crossing marketing claim dies at that boundary, published with the same prominence as a success (frozen language). Stage 3 (external benchmark flank) is gated on this family per docs/10 §9.

## Claim scoping (binding)

These are statements about ONE exported context packet (vendored exporter pylgrim-repo 00ff5a1) on ONE corpus (48 short T-real cards, vague-prompt row) at one moment, across three specific model snapshots. Non-inferiority is claimed only where the Holm-level bound clears the −5pp margin; any improvement beyond non-inferiority is exploratory. Nothing here measures real enforcement, multi-turn accumulation, or external benchmarks (Stage 3). Cross-tier economy figures compare spend, not tokens.

