# E9+E10 confirmatory analysis · report 1

Executed per `preregistration/prereg-v4-render.md` (frozen, tag `prereg-v4-render`, commit 6c2af0e, public before any E9/E10 confirmatory run). E9 cells: 48 short T-real cards × 3 reps × Sonnet, vague-prompt row, three constraint renderings (bare / [observe] / [enforce]) through the real vendored exporter (pylgrim-repo 00ff5a1); the bare cell's tag strip is the ONE documented synthetic edit. E10 cells: `vanilla-vague` + `export-vague` × 48 × 3 on Haiku (resolved snapshot(s): claude-haiku-4-5-20251001). Card unit; pairing per-comparison per-card common reps (addendum §7 carried over); R1-ext scrub applied to all context arms on hugo/nushell/zod; R2 junk filter, R4 CLI-modelUsage economy basis, and the degenerate-case rule carried verbatim from prereg-v2-ext. Vague artifact unchanged (`tasks/vague/vague-prompts-v1.yaml`, sha 2e41d3aa…). Judged metric secondary (κ=0.626; Sonnet-judge for all cells including Haiku's — a same-judge-different-agent asymmetry, disclosed). Database read-only (`mode=ro`, busy timeout) under the live judge drain; nothing re-run or mutated.

## Regression check (gate, computed before any E9/E10 number)

Published Wave-1.5 and E8 cells re-derived from the same database and asserted against `wave15-analysis-1.md` / `e8-analysis-1.md`: **PASSED**.

- vanilla-vague (Sonnet, W1.5): M1 7, M3 9, any-drift 9/48, M5 39/48 (published: M1 7, M3 9, any-drift 9/48, M5 39/48)
- export-vague (Sonnet, W1.5): M1 1, M3 1, any-drift 1/48, M5 45/48 (published: M1 1, M3 1, any-drift 1/48, M5 45/48)
- stale-wrong-vague (Sonnet, E8): M1 6, M3 6, any-drift 6/48, M5 30/48 (published: M1 6, M3 6, any-drift 6/48, M5 30/48)
- stale-generic-vague (Sonnet, E8, RECOMPUTED at 144/144 after retries; published at 142/144): M1 0, M3 1, any-drift 1/48, M5 44/48 (published: M1 0, M3 0, any-drift 0/48, M5 43/48) — CHANGED by the 2 retried runs (disclosed; e8-analysis-1.md was marked PRELIMINARY for exactly this cell)

## The cells (48 short T-real cards, vague prompts, 3 reps)

| cell | model | n cards | M1 touched (bound) | M3 violated (bound) | any-drift | mean cost/run | churn share | mean turns | M5 majority-pass | agent_committed runs | judged met |
|---|---|---|---|---|---|---|---|---|---|---|---|
| export-bare-vague | sonnet | 48 | 0 (≤6.1%) | 0 (≤6.1%) | 0 | $0.719 | 0.007 | 19.1 | 46/48 | 0 | - (0/142 judged) |
| export-vague | sonnet | 48 | 1 (≤9.5%) | 1 (≤9.5%) | 1 | $0.754 | 0.025 | 18.8 | 45/48 | 1 | 84.6% (141/142 judged) |
| export-enforce-vague | sonnet | 48 | 0 (≤6.1%) | 0 (≤6.1%) | 0 | $0.764 | 0.007 | 19.4 | 46/48 | 0 | - (0/143 judged) |
| vanilla-vague | sonnet | 48 | 7 (≤25.7%) | 9 (≤30.4%) | 9 | $0.854 | 0.239 | 23.3 | 39/48 | 0 | 57.2% (141/142 judged) |
| vanilla-vague | haiku | 48 | 13 (≤39.6%) | 14 (≤41.8%) | 14 | $0.458 | 0.234 | 44.8 | 38/48 | 71 | - (0/144 judged) |
| export-vague | haiku | 48 | 0 (≤6.1%) | 1 (≤9.5%) | 1 | $0.382 | 0.034 | 35.0 | 42/48 | 10 | - (0/144 judged) |

Bounds are one-sided exact Clopper-Pearson 95%. `vanilla-vague` and `export-vague` on Sonnet are the published Wave-1.5 cells, shown for context. `agent_committed` is reported per cell per prereg-v4 (the pilot's unprompted-commit behavior was Haiku-specific; capture-vs-base_sha already neutralizes it — and the Haiku counts below confirm the behavior is real and heavily cell-dependent). Cost is NOT comparable across tiers (different per-token pricing).

## Confirmatory family (prereg-v4-render; Holm as one family across E9+E10)

| endpoint | result | test | p |
|---|---|---|---|
| 1 · drift, export-bare-vague vs export-enforce-vague (Sonnet) | b=0, c=0 (n=48) | degenerate rule | bound ≤6.1% |
| 2 · drift, export-vague vs export-enforce-vague (Sonnet) | b=1 (export-vague@sonnet-only), c=0 (export-enforce-vague@sonnet-only), n=48 | exact McNemar | p = 1.0000 |
| 3 · drift, vanilla-vague vs export-vague (Haiku) | b=13 (vanilla-vague@haiku-only), c=0 (export-vague@haiku-only), n=48 | exact McNemar | p = 0.0002 |

Holm-adjusted: 2 · drift observe-vs-enforce: p_adj = 1.0000; 3 · drift haiku vv-vs-xv: p_adj = 0.0005.
Degenerate endpoints (pre-specified rule, no improvised statistic): 1 · drift bare-vs-enforce: 0 discordant cards of 48 → one-sided 95% bound on discordance ≤6.1%.

### Plain-English readings

- **Endpoint 1 (E9, tag presence):** the bare block (no mode tags) drifted on 0/48 cards vs the [enforce]-tagged block's 0/48. Discordance 0 bare-only vs 0 enforce-only. No discordant cards; only the pre-specified bound is reported.
- **Endpoint 2 (E9, observe vs enforce):** the [observe]-tagged block (current product default) drifted on 1/48 cards vs [enforce]'s 0/48. Discordance 1 observe-only vs 0 enforce-only. Not significant after Holm: the data do not confirm a drift difference between [observe] and [enforce] renderings.
- **Endpoint 3 (E10, Haiku replication):** on Haiku, no-context drifted on 14/48 cards vs the exported block's 1/48. Discordance 13 vanilla-only vs 0 export-only. The Wave-1.5 headline REPLICATES below Sonnet: the exported block's drift protection survives Holm on Haiku.

## Descriptives (no tests registered; none run)

- **Bare vs observe (E9's third pair):** export-bare-vague 0/48 drift cards vs export-vague 1/48; discordance 0 bare-only vs 1 observe-only (n=48). Descriptive only.
- **M5 majority-pass:** export-bare-vague 46/48 · export-vague 45/48 · export-enforce-vague 46/48 (Sonnet); vanilla-vague 38/48 · export-vague 42/48 (Haiku).
- **Economy** (mean per-run cost delta over §7-paired cards, with the mandatory injection-mass decomposition; labeled estimates at 4 chars/token — Sonnet cache-write $3.75/MTok, cache-read $0.3/MTok; Haiku cache-write $1.25/MTok, cache-read $0.1/MTok):
  - export-bare-vague − export-enforce-vague (Sonnet): Δ = -0.0216 USD/run (block-mass Δ -0.0001, behavioral residual -0.0215; n=48).
  - export-vague − export-enforce-vague (Sonnet): Δ = +0.0334 USD/run (block-mass Δ +0.0000, behavioral residual +0.0334; n=48).
  - export-vague − vanilla-vague (Haiku): Δ = -0.0761 USD/run (block-mass Δ +0.0019, behavioral residual -0.0780; n=48).
- **Judged:** deferred — see the judged-metric section.

## PATH_CAP probe (registered, descriptive, no new runs)

Registered stratifier: cards with ≤8 vs >8 `scope_paths` (the exporter caps each path list at 8 with "(+N more)").

| export cell | any-drift, ≤8 scope_paths | any-drift, >8 scope_paths |
|---|---|---|
| export-bare-vague @ sonnet | 0/48 | 0/0 |
| export-vague @ sonnet | 1/48 | 0/0 |
| export-enforce-vague @ sonnet | 0/48 | 0/0 |
| export-vague @ haiku | 1/48 | 0/0 |

**The registered >8 stratum is EMPTY**: no card in this corpus has more than 5 scope_paths, so the In-scope cap never fires and the probe as registered is uninformative here — reported as-is, not repaired. Labeled supplementary note (NOT the registered stratifier, hypothesis-grade): the cap DOES fire on the Out-of-scope list for 9/48 cards (nushell-t01, nushell-t03, prettier-t01, prettier-t02, prettier-t03, prettier-t04, prettier-t05, zustand-t03, zustand-t05), where entries beyond 8 — including possible honeypot paths — are hidden behind "(+N more)". Drift by that supplementary stratum:

| export cell | any-drift, ≤8 out_of_scope | any-drift, >8 out_of_scope |
|---|---|---|
| export-bare-vague @ sonnet | 0/39 | 0/9 |
| export-vague @ sonnet | 1/39 | 0/9 |
| export-enforce-vague @ sonnet | 0/39 | 0/9 |
| export-vague @ haiku | 1/39 | 0/9 |

Any claim about the out_of_scope cap requires its own pre-registered comparison.

## Tier interaction (descriptive)

- Sonnet effect (W1.5): vanilla-vague 9/48 → export-vague 1/48 drift cards; discordance 8 vanilla-only vs 0 export-only (n=48).
- Haiku effect (E10): vanilla-vague 14/48 → export-vague 1/48 drift cards; discordance 13 vanilla-only vs 0 export-only (n=48).
- Descriptive interaction: the export block removes 8 net drift cards on Sonnet and 13 on Haiku. No test is registered for the interaction; it is reported, not claimed.

## E13 Stage-1 — EXPLORATORY, HYPOTHESIS-GENERATING ONLY

**This section is NOT part of prereg-v4-render's confirmatory family. It is the Stage-1 exploratory readout registered as docs/10 §9 in the venture repo: descriptive deltas only, no tests, no confirmatory language. Any claim arising here requires fresh pre-registered runs (E13 Stage 2).**

Cross-tier comparison on the shared 48 cards (card-level, all available reps; cost in USD/run at each tier's own pricing — the cost column compares spend, not tokens):

| cell | drift cards | M5 majority-pass | mean cost/run |
|---|---|---|---|
| vanilla-vague @ sonnet | 9/48 | 39/48 | $0.854 |
| export-vague @ sonnet | 1/48 | 45/48 | $0.754 |
| vanilla-vague @ haiku | 14/48 | 38/48 | $0.458 |
| export-vague @ haiku | 1/48 | 42/48 | $0.382 |

The two Stage-1 contrasts:

- **Haiku+export-vague vs Sonnet+vanilla-vague** (packet on the small model vs raw big model): drift 1/48 vs 9/48 (-8 cards); M5 42/48 vs 39/48 (+3); cost $0.382 vs $0.854 per run (-0.472).
- **Haiku+export-vague vs Sonnet+export-vague** (capability-gap reference, packet held fixed): drift 1/48 vs 1/48 (+0); M5 42/48 vs 45/48 (-3); cost $0.382 vs $0.754 per run (-0.372).

Plain-English reading (descriptive): with no packet, Haiku drifts on 14/48 cards where Sonnet drifts on 9/48 — a raw tier gap of 5 cards. Handing Haiku the exported packet removes 13 of its drift cards (to 1/48), putting the packet-equipped small model at or below the raw big model's drift level. On test-pass, the raw tier gap is 1 card (38/48 vs 39/48) and the packet moves Haiku by +4 cards to 42/48, still 3 cards short of packet-equipped Sonnet. These are descriptive deltas on one corpus at one moment; they generate the E13 hypothesis ("the packet buys back a chunk of the tier gap") and prove nothing. Not registered in prereg-v4-render's family; any claim requires fresh pre-registered runs (E13 Stage 2).

## Judged metric (secondary)

Judge drain in progress (861 judge runs pending db-wide): runs judged — export-bare-vague@sonnet 0/142, export-enforce-vague@sonnet 0/143, vanilla-vague@haiku 0/144, export-vague@haiku 0/144, export-vague@sonnet 141/142, vanilla-vague@sonnet 141/142. Judged verdicts for the E9 and E10 cells are entirely absent, so the judged criteria-satisfaction shares for the new cells are not reported here (per the e8-analysis-1.md precedent); the deterministic results above stand on their own. Re-issue this report when the drain completes. κ = 0.626 carries from the Wave-1 calibration; the Sonnet-judge-for-Haiku-agents asymmetry (disclosed in prereg-v4) will apply to that re-issue.

## Coverage, exclusions and disclosures

| cell | done / expected |
|---|---|
| export-bare-vague @ sonnet | 142/144 |
| export-vague @ sonnet | 142/144 |
| export-enforce-vague @ sonnet | 143/144 |
| vanilla-vague @ sonnet | 142/144 |
| vanilla-vague @ haiku | 144/144 |
| export-vague @ haiku | 144/144 |

- `hono-t01--export-vague--sonnet--r1`: error, attempt 2 (claude run timed out after 1800s)
- `hugo-t05--vanilla-vague--sonnet--r2`: error, attempt 2 (claude run timed out after 1800s)
- `hugo-t05--vanilla-vague--sonnet--r3`: error, attempt 2 (claude run timed out after 1800s)
- `nushell-t04--export-bare-vague--sonnet--r1`: error, attempt 2 (claude run timed out after 1800s)
- `nushell-t04--export-bare-vague--sonnet--r3`: error, attempt 2 (claude run timed out after 1800s)
- `nushell-t04--export-enforce-vague--sonnet--r3`: error, attempt 2 (claude run timed out after 1800s)
- `nushell-t04--export-vague--sonnet--r1`: error, attempt 2 (claude run timed out after 1800s)
- The 3 E9 non-done runs above are attempt-2 timeouts (1800s) — permanent exclusions after the retry sweep, all on nushell-t04; §7 pairing truncates the affected cards to common reps. Both Haiku cells are complete (144/144). Baseline (Wave-1.5) exclusions are the permanent timeouts recorded in wave15-analysis-1.md.
- §7 truncation applied per comparison: endpoint 1 n=48, endpoint 2 n=48, endpoint 3 n=48 cards with ≥1 common rep.
- The database was read-only (`mode=ro`, busy timeout) under the live judge drain; nothing was re-run or mutated. No frozen file was modified.

## Honest-outcome statement

Of the three registered endpoints, 1 survive(s) Holm at 0.05 (3 · drift haiku vv-vs-xv); not confirmed: 2 · drift observe-vs-enforce; degenerate: 1 · drift bare-vs-enforce. Prereg-v4's stated hypothesis was enforce < observe on drift with bare between or equal; the registered fallback ("if tags turn out inert (all cells equal), that publishes and the W1.5 mode-tag note demotes to noise") applies exactly as frozen: the E9 cells are statistically indistinguishable on drift, i.e. the data do not show the mode tag carrying authority. E9 raw drift counts: bare 0/48, observe 1/48, enforce 0/48. E10: the Sonnet headline replicates on Haiku (vanilla 14/48 vs export 1/48, b=13, c=0). Every non-significant endpoint is reported as-is, not explained away. The E13 Stage-1 section above is exploratory and claims nothing.

## Claim scoping (binding)

E9 results are statements about the exporter's constraint-line rendering (mode-tag presence and value) under issue-text prompts, single-session, Sonnet — the [enforce] cell renders the tag through the real path but NO enforcement mechanism runs; this measures the word, not the machinery. E10 results are statements about one tier below Sonnet (Haiku, snapshot above), same corpus and instruments. Nothing here measures real enforcement (arm C), multi-turn accumulation, or cross-tier equivalence (E13 Stage 2 owns that question).

