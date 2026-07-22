# Pre-registration v5-tiercross — E13 Stage 2 (the tier-crossing confirmatory study)

Dated: 2026-07-22 (UTC). Status at signing: NO E13 Stage-2 run has been
executed. Prior freezes (prereg-v1 e8ae27a, prereg-v2-ext 99a4f16,
prereg-v3-stale 1725604, prereg-v4-render 6c2af0e) untouched and binding
for their waves. E13 was registered ahead in docs/10 §9 of the venture
repo (2026-07-22) and the Stage-2 design was approved by Sam 2026-07-22.

## Hypothesis source (disclosed): the Stage-1 exploratory peek

The motivating numbers are the E13 Stage-1 exploratory readout in
results/reports/e9-e10-analysis-1.md (labeled hypothesis-generating only,
outside prereg-v4-render's family): Haiku+export vs Sonnet+vanilla on the
shared 48 cards showed drift 1/48 vs 9/48, M5 42/48 vs 39/48, and mean
cost/run $0.382 vs $0.854 (−55%). That peek is why this study exists.
**Binding rule: Stage 2 confirms or kills on FRESH data only. No Stage-1
run (nor any Wave-1.5/E10 run) enters the confirmatory family, including
the very cells that generated the hypothesis. If non-inferiority fails,
that publishes with the same prominence.**

## Design (all cells fresh; 48 short T-real cards, vague-prompt row, 3 reps)

| # | cell (arm @ model) | why fresh |
|---|---|---|
| 1 | `export-vague` @ haiku | Stage-1's Haiku cells ARE the hypothesis source; reuse would confirm on the peeked data |
| 2 | `vanilla-vague` @ sonnet | fresh contemporaneous baseline (no temporal confound vs Wave-1.5's July-16 runs) |
| 3 | `export-vague` @ sonnet | fresh contemporaneous baseline, same reason |
| 4 | `vanilla-vague` @ opus | new tier |
| 5 | `export-vague` @ opus | new tier |

5 cells × 48 cards × 3 reps = 720 runs. No new arm mechanics: both arms
exist unchanged since Wave 1.5 (vendored exporter pylgrim-repo 00ff5a1;
vague artifact `tasks/vague/vague-prompts-v1.yaml`, sha 2e41d3aa…,
unchanged). The ONLY new thing is the model column value `opus` (claude
CLI alias, exactly as `haiku` entered in E10; the resolved snapshot is
recorded per-run by provenance, per the E10 convention).

**Rep indexing and seeds (frozen):** Stage-2 reps are numbered r4-r6.
This is forced by the queue's run_id primary key (`task--arm--model--rN`;
cells 1-3 already hold r1-r3 from Wave 1.5/E10) and it makes the
fresh-data rule mechanical: the Stage-2 family reads rows with rep ≥ 4
and nothing else. Master schedule seed stays 42 (the house constant for
every block since Wave 1); per-run seeds follow the house derivation
sha256("42:" + run_id), so every Stage-2 run carries a fresh seed no
prior run ever used, because every Stage-2 run_id is new. Randomization
is the house rep-blocked shuffle across all five cells as one block.

**Append mechanism (frozen in this commit):**
`analysis/append_e13_stage2.py`, committed with this freeze, reproduces
`schedule.generate`'s rep-blocked shuffle for the five (arm, model) cells
with reps 4-6 and `order_key_start` = (max existing order_key) + 1 —
the same order_key_start motion that appended Wave 1.5, E8, E9 and E10.
Expected order keys 1930-2649 (the queue holds 1930 rows, keys 0-1929,
at signing). The script asserts no run_id collision, no running worker,
and strictly-after order keys before inserting.

## Confirmatory family (Holm as ONE family of four; card = unit; §7 pairing)

Pairing: addendum §7 carried verbatim, with the (arm, model) cell playing
the role §7 gives an arm — each comparison uses per-card common Stage-2
reps (r4-r6) across its two cells. M5 binarization is the pre-pinned
majority-of-reps rule from prereg-v2-ext endpoint 4.

| # | endpoint | comparison | test |
|---|---|---|---|
| 1 | M5 test-pass, non-inferiority, margin −5pp | `export-vague`@haiku vs `vanilla-vague`@sonnet | one-sided Tango score test of H0: Δ ≤ −0.05 |
| 2 | drift: M1∪M3 any-drift, superiority | `export-vague`@haiku vs `vanilla-vague`@sonnet | exact McNemar, two-sided |
| 3 | M5 test-pass, non-inferiority, margin −5pp | `export-vague`@sonnet vs `vanilla-vague`@opus | one-sided Tango score test of H0: Δ ≤ −0.05 |
| 4 | drift: M1∪M3 any-drift, superiority | `export-vague`@sonnet vs `vanilla-vague`@opus | exact McNemar, two-sided |

- **Non-inferiority form (mirrors prereg-v1 H3 / docs/10 §7):** Δ =
  p(packet-equipped lower tier) − p(raw higher tier), card-level paired
  difference in M5 pass proportions over the 48 cards. The margin −5pp is
  pre-registered; **the CI must exclude the margin for the claim to
  hold**: the claim holds iff the Holm-adjusted one-sided Tango score
  p < .05, equivalently the one-sided Holm-level lower confidence bound
  for Δ lies above −0.05. The two-sided 95% Tango score CI is reported
  alongside regardless. Any improvement beyond non-inferiority is
  exploratory, not claimed as confirmed (prereg-v1 H3 language).
- Degenerate-case rule (zero discordant cards → exact one-sided 95%
  bound is the estimand) carried verbatim for the McNemar endpoints.
- All four p-values enter one Holm family. No other test is run.

## Descriptive (registered as such; no tests; none will be run)

- **Cost-per-completed-task** per cell: R4 CLI-modelUsage economy basis;
  "completed" = M5 pass; every economy figure carries the injection-mass
  decomposition (addendum §3). Cross-tier cost compares SPEND, not
  tokens (different per-token pricing); that asymmetry is the commercial
  point and is stated wherever the number appears.
- **Within-tier packet effect on opus** (cells 4 vs 5): drift and M5
  bounds, descriptive — the tier-crossing family above stays at four.
- **Capability-gap reference:** `export-vague`@haiku vs
  `export-vague`@sonnet (packet held fixed), descriptive.
- **agent_committed** counts per cell (E10 convention).
- **Judged criteria-satisfaction, secondary:** same Sonnet judge,
  κ = 0.626 carried from the Wave-1 calibration; the same-judge-
  different-agent asymmetry now spans three tiers (a Sonnet judge scores
  haiku, sonnet AND opus agents) and is disclosed wherever judged
  numbers appear.

## Hypotheses (honesty statement)

H-E13: the packet-equipped lower tier is non-inferior on task success
and superior on drift versus the raw next tier up, at both boundaries
(haiku→sonnet, sonnet→opus). The Stage-1 peek points this way for
haiku→sonnet; sonnet→opus is unpeeked. If either boundary fails —
non-inferiority CI crosses the margin, or drift superiority does not
survive Holm — that result publishes with the same prominence, and the
tier-crossing marketing claim dies at that boundary. Stage 3 (external
benchmark flank) is gated on this family landing, per docs/10 §9.

## Shared rules

Carried verbatim from prereg-v2-ext (as in prereg-v3/v4): degenerate-case
rule, R1-ext scrub (hugo/nushell/zod context arms), R2 junk patterns, R4
economy basis, truncation/pairing (§7), judged metric secondary
(κ = 0.626). Vague artifact unchanged (sha 2e41d3aa…). Injection-mass
decomposition accompanies any economy delta shown.

## Smoke disclosure

No new arm mechanics, so no new-arm smoke. The only new machinery surface
is the model alias `opus` on the CLI path E10 already proved for `haiku`.
ONE trivial alias-resolution check was run pre-freeze on a throwaway
prompt ("Reply with exactly: OK"), NOT on any corpus card: the alias
resolved (modelUsage snapshot `claude-opus-4-8`, standard result JSON
with the R4 modelUsage basis present). No outcome of any Stage-2 cell —
on any card, any arm, any model — has been observed.

## Ordering note

The judge drain for E8/E9/E10 (861 judge runs pending at signing) holds
the execution window; the Stage-2 coding drain launches only after it
completes. The 720 Stage-2 rows are appended with order keys strictly
after ALL existing rows (expected 1930-2649), and only after this
document is committed, tagged `prereg-v5-tiercross`, and pushed to the
public origin. Freeze-before-run is preserved per-study.

## Provenance

Harness at this freeze commit; vendored exporter pylgrim-repo 00ff5a1;
master seed 42 with fresh per-run seeds via new r4-r6 run ids (above);
vague artifact sha 2e41d3aa…; model snapshots recorded per-run (E10
convention); tag `prereg-v5-tiercross`.
