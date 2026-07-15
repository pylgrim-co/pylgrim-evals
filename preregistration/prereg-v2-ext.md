# Pre-registration v2-ext — Wave 1.5, the extension wave

Dated: 2026-07-16 (UTC). Status at signing: NO Wave-1.5 confirmatory run
has been executed; the only new-arm executions are the disclosed smoke set
(§7). Wave-1 artifacts (prereg-v1.md, the 83-card manifest, the addendum)
are untouched and remain binding for their wave. This document freezes the
design and analysis of the extension wave pre-declared as E1/E2 in
results/reports/bias-audit-1.md.

## 1. Design

The full factorial prompt × context on the 48 short T-real cards:

| | context: none | context: oracle CLAUDE.md | context: exported CLAUDE.md |
|---|---|---|---|
| **specified prompt** | `vanilla` (Wave 1) | `claudemd` (Wave 1) | `export` (NEW) |
| **vague prompt** | `vanilla-vague` (NEW) | `claudemd-vague` (NEW) | `export-vague` (NEW) |

- 4 new cells × 48 cards × 3 reps × Sonnet = 576 new runs, appended to the
  existing queue with `order_key_start` past the Wave-1 rows; seed 42;
  rep-blocked shuffle as in Wave 1.
- Wave-1 cells serve as the shared baselines; they are not re-run.
- T-bait cards sit out (prompt-disclosed temptations; undisclosed bait is
  E3, a future wave). click-l01 (long-horizon) sits out (descriptive-only
  stratum, Wave 1). The 2 control cards are excluded from confirmatory
  analysis as always.

## 2. The arms (mechanics frozen)

- **`export` context:** the harness constructs a `.pylgrim/` ledger
  mechanically from the card's intent block (one work_item entry with
  criteria/scope_paths/out_of_scope; one constraint entry per
  `intent.constraints` item; `status: ratified`, `source: manual`;
  deterministic entry ids and stamp) and renders CLAUDE.md with the
  VENDORED real exporter, `harness/src/harness/vendor/export_claudemd.py`
  (verbatim from pylgrim-repo commit 00ff5a1). Same information as the
  oracle arm, through the product's own format. The skills' authorship of
  the ledger is NOT tested here (deferred, E1-skill).
- **vague prompt row:** the prompt is the card's source issue (or
  discussion) title + body VERBATIM from the GitHub API, truncated at
  8,000 chars on a paragraph boundary — mechanical rule, no human editing
  (real users paste issues). Frozen artifact:
  `tasks/vague/vague-prompts-v1.yaml`, sha256
  `2e41d3aaad0835df4e9046c23d81dad123142b697d81d4ab11e1a50c3dff9b3a`,
  50 entries (48 confirmatory + click-l01 + the zustand-l01 smoke card),
  0 fetch failures. Per-entry sha256 recorded in the artifact.
- Context files are written to the workspace root exactly as in Wave 1,
  including on the three repos carrying a tracked CLAUDE.md at base
  (hugo, nushell, zod) — see R1-ext below.

## 3. Confirmatory family (Holm-corrected as one family)

The card is the inferential unit; cells are per-card means over the reps
paired per the Wave-1 truncation rule (addendum §7, carried over verbatim).

| # | endpoint | comparison | test |
|---|---|---|---|
| 1 | drift: M1∪M3 any-drift (card-level) | `vanilla-vague` vs `export-vague` | exact McNemar, two-sided |
| 2 | economy: total_cost_usd | `export-vague` − `vanilla-vague` | repo-level sign-flip permutation (exact), two-sided |
| 3 | format channel: total_cost_usd | `export` − `claudemd` | repo-level sign-flip permutation, two-sided |
| 4 | outcome: M5 test-pass, majority-of-reps binarization (pre-pinned) | `vanilla-vague` vs `export-vague` | exact McNemar, two-sided |

- Degenerate-case rule carried over: zero discordant cards → the exact
  one-sided 95% bound on discordance probability is the estimand.
- **Format-channel drift** (`export` vs `claudemd`): expected all-zero on
  both sides; reported as paired card-level bounds, not a test. The
  format-channel CLAIM is equivalence-shaped: "the exporter's block
  performs indistinguishably from the oracle block on drift bounds and
  cost," supported by endpoint 3 plus the bounds.
- Card-level drift bounds (Clopper–Pearson one-sided 95%) are published
  per cell for M1 and M3, with the same stratum brackets as Wave 1 where
  applicable. Every economy delta carries the injection-mass decomposition
  (addendum §3, applied to whichever context file the cell carries).
- All other metrics and splits are descriptive. The judged
  criteria-satisfaction metric remains secondary, carrying the Wave-1
  calibration (κ = 0.626).

## 4. Analysis rules carried over and extended

- R1 (treatment, never drift) — **extended, R1-ext:** on hugo, nushell,
  and zod the workspace CLAUDE.md write appears as tracked churn in every
  context-arm diff (discovered post-hoc in Wave 1, wave1-analysis-1.md).
  For Wave 1.5 this is pre-registered: M2 and churn-derived quantities on
  ALL context-arm runs are computed on `judge.scrub_diff`-scrubbed diffs
  (CLAUDE.md sections dropped); stored metrics stay unmutated; the
  scrubbed value is what the analysis consumes, labeled.
- R2 (environment junk), R3 (M5 oracle-class split, list as published in
  wave1-analysis-1.md), R4 (CLI modelUsage economy basis), R5 (fnmatch
  case-insensitivity disclosure): carried over verbatim.
- Truncation rule: addendum §7 verbatim. Exclusions counted and listed.
- Judge order: judge runs for new cells are scored arm-blind exactly as
  Wave 1 (the scrubber also removes the exported block; verified in the
  smoke set); no new human calibration round — κ carries over and this is
  disclosed as a limitation (the judge sees the same artifact shapes).

## 5. Hypotheses (directional expectations, stated for honesty; the tests above decide)

- H-E2: under vague prompts the no-context cell shows a measurable drift
  base rate (the rate Wave 1's saturated prompts suppressed), and the
  exported-context cell shows less drift and lower cost. This is the
  value-of-delivered-intent claim.
- H-E1: the exporter's block is indistinguishable from the oracle block
  (drift bounds and cost). This is the format-channel claim: the product's
  real artifact inherits the oracle arm's behavior.
- If either fails in the awkward direction (e.g., vague-row drift is zero
  everywhere again, or the exported block underperforms the oracle), that
  publishes with the same prominence.

## 6. Claim scoping (binding on any writeup)

Vague-row results: "issue-text prompts, single-session, file-granular
instruments." Export arms: "a mechanically constructed ledger rendered by
the product's real exporter" — statements about the skills' authorship of
ledgers remain out of scope (E1-skill, future). Nothing here measures
enforcement (arm C, Wave 2) or multi-turn accumulation (E5).

## 7. Smoke disclosure (pre-freeze, no confirmatory peeking)

Pipeline validation before this freeze used only non-confirmatory targets:
dry renders of all four new arms on zustand-l01 (excluded card; verified
prompt selection and context materialization) and one live end-to-end run
of the `export` arm on click-c01 (positive-control card). No confirmatory
card's outcome under any new arm has been observed.

## 8. Provenance

- Harness at the freeze commit (this repo); vendored exporter from
  pylgrim-repo 00ff5a1; Claude Code CLI and model snapshots recorded
  per-run as in Wave 1 (provenance block).
- Wave-1 freeze: e8ae27a (tag `prereg-v1`). This freeze: the commit
  carrying this file, tagged `prereg-v2-ext`.
