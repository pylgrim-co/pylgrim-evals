# Bias audit 1 — four-lens adversarial review of the Wave-1 drift study

Date: 2026-07-11 (UTC). Four independent auditors (ecological/construct
validity; task/card construction; metrics/implementation; statistical
design), all hostile by instruction, all read-only against the frozen study
while the Wave-1 drain runs. Full per-lens reports are preserved in the
session record; this document is the synthesis and the action ledger.

## The four findings that matter most (cross-lens consensus)

### 1. The treatment is not the product (CRITICAL, ecological)
Arm B injects a harness-rendered CLAUDE.md carrying the card's hand-written
scope globs. The product's real exporter (`export_claudemd.py`) NEVER
exports scope paths — it emits one-line constraint summaries and criteria
checklists; the plan skill's out_of_scope is natural language, not globs; a
real map-produced block is repo-generic hygiene with zero task-scoped path
content. **No pylgrim-produced artifact enters any Wave-1 coding run.**
Wave 1 measures an idealized oracle ceiling of the injection channel.
Consequence: no result, in either direction, licenses "pylgrim's skills
measurably help/hurt agent behavior."

### 2. The null is designed in: prompt saturation (CRITICAL, cards + ecological)
Quantified: lexical constraint→prompt overlap mean 0.72; semantic
saturation effectively 100% (zero confirmatory cards leave arm A uninformed
of any constraint); 55% of honeypot paths are NAMED in the prompt with
"do not touch" phrasing, and the rest are defused by category; 238/245
honeypots also sit inside the card's own protected-paths rules, making M1
nearly a subset of M3. Arm B therefore carries zero unique information at
full injection cost — "B ≈ A on drift" and "B costs more input tokens" are
both close to guaranteed by construction. The T-bait instrument measures
**instructed-refusal compliance**, not spontaneous temptation.

### 3. The instruments can only undercount, and the base rate is zero (CRITICAL, implementation)
Every blind spot is one-directional: Bash writes unattributed (quantified:
~5% of Bash calls could write), in-scope-CONTENT drift (the most common
real-world drift form — bloat inside scoped files) carries zero measured
mass, gitignored-path writes are invisible to untracked capture, and
34% of cards (28/83) have do-nothing-green outcome oracles (suite green at
base, no fix-asserting check). A bounded null over these instruments cannot
currently distinguish "injection doesn't help" from "the instruments can't
see the drift injection would prevent."

### 4. The statistics plan wasn't written for the study Wave 1 became (CRITICAL, statistics)
The only executable pre-registered family (H1) predicts its own degenerate
Wilcoxon (all-zero deltas → undefined statistic); the B-vs-A economy
comparison that deviation (h) promotes to headline has NO pinned endpoint
among ≥32 metric×stratum gates whose pilot signs disagree; the economy
metric family is mechanically confounded by the injection's own token mass
(pilot cache-creation delta +3,484/run ≈ rendered-file size × turns —
arithmetic, not behavior); the honest inferential unit is the card (0/81 →
≤3.6% per-arm bound), not the run (≤1.2% is not defensible); 15/81
confirmatory cards were outcome-peeked pre-freeze and click-l01 was
selected INTO the set on its clean probe run.

## Verdict on the motivating question

**Does Wave 1 show the skills work in the wild? No — and mostly it does not
attempt to.** The skills' output never enters a drift run; the prompts
saturate both arms with the intent; the bait discloses its own temptations;
the wild's defining conditions (vague prompts, multi-turn accumulation,
messy repos, weak tiers, non-Claude agents) are unsampled or deferred; and
H4 (skills quality bars) certifies form and latency under one cooperative
persona, never downstream behavioral effect.

What Wave 1 DOES honestly deliver, with genuinely good hygiene
(preregistration, deterministic-first instruments, positive controls,
logged deviations): (a) a card-level bounded null on file-granular,
path-scoped drift under fully-specified single-shot prompts — a real
finding against the literature's headline violation rates, properly scoped;
(b) the token/turn economics of a redundant oracle injection channel,
decomposable into payload mass vs behavioral residual (pilot hints the
behavioral residual may favor B: fewer turns).

## Action ledger

**Pre-data-lock (done alongside this audit):**
- A1 Dated analysis-plan addendum (preregistration/analysis-plan-addendum-1.md):
  single primary economy endpoint + full test-family table; injection-mass
  decomposition; card-level bounds w/ stratum, peeked-card (n=66 → 4.4%),
  and correlated-surface (repo-level ≤26%) brackets; degenerate-Wilcoxon
  fallback (exact discordant-card test); repo-level sign-flip permutation
  as primary inference; truncation rule; M2 CLAUDE.md exclusion promoted to
  frozen rule covering BOTH untracked and committed paths (scrub_diff
  recompute on agent_committed ∧ arm B); M5 split by oracle-can-fail-at-base;
  LH stratum demoted to descriptive; judge-order pin; environment-junk
  exclusion list; case-insensitive-fnmatch repro disclosure.
- A2 Amendments entry reconciling the fail-at-base overstatement in
  RATIFICATION-LOG.md (per-card verification table: executed vs inspected
  vs unverified — hugo-t04/t05, nushell-t05 unverified; 9 stale frozen
  contamination notes) — factual correction, cards untouched.

**Post-drain analysis passes (computable from stored artifacts, no reruns):**
- A3 In-scope-content-drift pass: per-run churn vs ground-truth PR footprint
  ratio; outliers to judge/manual review.
- A4 Base-rate + minimum-detectable-effect table published beside every
  bounded-null sentence.
- A5 M5 reported split by oracle class (fail-at-base-capable vs
  do-nothing-green).

**Extension experiments (the ones that actually answer "in the wild";
each a labeled exploratory arm, not a prereg change):**
- E1 **Arm B′ (skills-in-the-loop)**: pylgrim-map + pylgrim-plan produce the
  ledger on the pinned repo; export via export_claudemd.py; run the coding
  task against the REAL artifact. B′ vs B vs A separates product from oracle.
- E2 **Arm A0 (vague prompts)**: issue-text-only prompts, constraints absent;
  crossed with {nothing, oracle block, exported block} — separates the
  information channel from redundancy. The single highest-value extension.
- E3 **Undisclosed-honeypot bait stratum**: prompts state goal + criteria,
  never the temptations — measures the actual construct.
- E4 Subtle-drift positive controls: in-scope-file/out-of-scope-hunk
  refactor; Bash-only side effect; validated no-new-deps + protected-paths
  firings.
- E5 Multi-turn accumulated-session protocol (Wave-2, where enforcement
  lives).
- E6 **Three-way cadence comparison** (Wave 2): {no injection, session-start
  once, per-message refresh} in the multi-turn protocol — isolates the Pro
  tier's cadence value from injection per se.
- E7 **E-coord, multi-agent coordination** (added 2026-07-17; Wave-2+,
  design pending as WI-E09): N agents on adjacent work items in one repo,
  shared ledger + presence briefs vs none; region-collision rate,
  duplicated work, contradictory edits, tokens-to-combined-goal. Full
  rigor pipeline (design, adversarial review, freeze) before any
  confirmatory run — the Team tier's coordination claims are gated on it.
- E8 **Staleness study** (added 2026-07-18, frozen as prereg-v3-stale):
  {charter-only file, previous-task file} vs the Wave-1.5 vague-row
  baselines — does a stale managed block forfeit the drift protection,
  and is a wholly wrong file worse than no file? The maintenance
  (Custodian/freshness) product story is motivated by this study.

**Claims discipline (marketing/venture gate):**
- The paper and site must not say: "drift is prevalent" (this ecology shows
  the opposite), "pylgrim's injection measurably improves output" (never
  tested), "unplug pylgrim and agents get worse" (no experiment), or
  anything cross-agent/tier/long-horizon. The honest product story the data
  supports today: agents follow well-specified intent — the problem pylgrim
  solves is CAPTURING and PERSISTING that specification across sessions
  (intent capture, not mid-task obedience), and the enforcement claim waits
  for Wave 2 / E1-E3.
