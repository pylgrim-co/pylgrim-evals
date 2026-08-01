# E-coord design — DRAFT 2, NOT FROZEN, for remaining-OQ review

Dated: 2026-08-01 (UTC). Status: **design draft only**. Nothing here is
binding. No prereg exists, no schedule rows exist, no scenario has been
authored, no run of any kind has executed. This revision folds in Sam's
ratified answers (2026-08-01) to the three headline open questions of
draft 1 (OQ-1 control level, OQ-2 arm count, OQ-3 family composition);
see §9.0 for the decisions verbatim. The rigor pipeline is design doc →
adversarial review → freeze (prereg-v6-coord or later) → pilot
(permanently excluded) → confirmatory. Registered ahead as the
coordination study intent in the venture repo docs/10 §2 (2026-07-17,
WI-E09) and as proof 4 of the upside gate (docs/16 §4). Draft 1
(`design-e-coord-draft-1.md`) remains in place per the numbered-artifact
convention; this document supersedes it.

## 0. The claim under test

Team tier ($30/seat) sells coordination. The specific mechanism claims:
the shared `.pylgrim/` ledger gives every agent the same ratified picture
of who owns which work item and scope, and presence briefs put live
sibling-session scope (branch, scope paths, work-item id — paths only,
advisory, ephemeral; docs/04 §10) into each agent's per-message slice.
The marketing sentence this study either funds or kills: "presence
briefing tells two agents converging on the same file about each other
before the merge does."

Declared endpoints (docs/16 §4, verbatim): region-collision rate,
duplicated work, contradictory edits, tokens-to-combined-goal. All four
are still measured and published; which of them carry confirmatory tests
is now settled in §5 (two of five candidates; the rest are descriptive
with their operationalizations retained in full).

What this study does NOT claim to measure: the shipped daemon
implementation (the harness materializes the product's artifact formats
mechanically, the Wave-1.5 vendored-exporter move), true wall-clock
concurrency, teams larger than the tested N, or human-plus-agent
coordination.

## 1. Shape

N agents work adjacent work items on ONE repository from one pinned SHA,
each in its own isolated worktree on its own branch (the realistic team
motion: parallel branches, merge later). Same scenario set in all arms,
paired.

**N = 2 (primary).** Justification: (a) every declared metric is
pairwise-defined and N=2 is the smallest ensemble that exhibits all four
phenomena; (b) episode cost scales linearly in N on a subscription-bounded
single host, and N=2 buys the most paired scenarios per token; (c) the
scenario-authoring obligation (the disjoint-solution existence proof, §3)
grows combinatorially with N and is only demonstrably dischargeable at
N=2; (d) the product's own demo scenario is two agents converging on a
file. Claims are scoped to pairs; an exploratory N=3 extension on a small
scenario subset is listed as an open question (§9), not part of the
confirmatory design.

### Arms (three, per the ratified OQ-2 decision)

| arm | ledger | presence | what each agent sees |
|---|---|---|---|
| `coord-none` (control) | none | none | its own work item rendered as prompt constraints (Wave-1 arm-A discipline), plus a static one-line disclosure that another agent is concurrently working an adjacent task in this repo, with that task's TITLE only |
| `coord-ledger` (attribution) | shared | none | same prompt and title-only static disclosure discipline, plus the shared `.pylgrim/` ledger (BOTH work items ratified, with criteria, `scope_paths`, `out_of_scope`) rendered into each worktree and carried in each turn's slice exactly as in the bundle arm — but NO per-turn presence brief, ever |
| `coord-pylgrim` (treatment) | shared | live | same prompt, plus the shared `.pylgrim/` ledger rendered into each worktree, plus a presence brief recomposed at every resume turn: sibling branch, sibling touched-paths so far, sibling work-item id — exactly the schema constraints of docs/04 §10 (paths only, never content, advisory only) |

The control-arm information design is settled (OQ-1, ratified
2026-08-01): **title-only static disclosure**, the draft-1 position
confirmed. The control is NOT information-starved about the sibling's
existence. It knows a sibling exists and what the sibling's task is
called, because that is what a human dispatcher plausibly pastes. What a
static prompt structurally cannot hold is the sibling's ratified scope
and its LIVE touched-paths — which is precisely the product's category
claim. The measured contrast is therefore **"shared ratified scope + live
presence vs realistic current dispatch practice."** The alternative
controls draft 1 floated — full-static sibling scope at session start
(isolates the live-refresh delta alone) and existence-only disclosure
(inflates the effect) — are no longer candidate designs; they move to the
threats discussion as interpretive bounds on the measured contrast
(§8-T10).

**Three arms at full power, all confirmatory-grade execution, but a
one-pair confirmatory family.** The ratified OQ-2 decision buys the
ledger-only mechanism arm at full replication (3 reps × 30 scenarios,
+50% of the draft-1 budget, §7) rather than as a reduced-rep cell. The
binding constraint that keeps this from taxing proof 4's alpha: **the
confirmatory family remains bundle-vs-none ONLY.** Every comparison
involving `coord-ledger` — ledger-only vs control, bundle vs ledger-only
— is DESCRIPTIVE, pre-labeled here as attribution readouts; no test of
any kind is registered on them. The attribution arm exists to answer
"how much of the bundle effect is the ratified ledger alone?" on the
record, with confirmatory-grade data quality, without ever entering the
tested family. Draft-1's T9 (bundle attribution as a named limitation)
is accordingly softened, not deleted (§8-T9).

## 2. Execution protocol: deterministic interleave

True concurrency (two `claude -p` processes racing) is nondeterministic,
unschedulable under rate limits, and unreproducible. Draft protocol
instead: **seeded round-based interleaving via multi-turn headless
resume** (the mechanism WI-E06a already proved for scripted personas).

- An episode = one (scenario × arm × rep): two sessions advanced in
  alternating turns. Turn = one `claude -p` invocation (first turn: the
  task prompt; subsequent turns: `--resume <session_id>` with a fixed
  continuation nudge, verbatim across arms: "Continue working on your
  task. Stop when your acceptance criteria are met.").
- Which agent takes the first turn is drawn from the seeded schedule per
  episode (house derivation, sha256 over run_id); thereafter strict
  alternation A,B,A,B.
- **Turn cap:** R rounds per agent (draft R=6; pilot calibrates). An
  agent that declares completion before the cap stops resuming; its
  sibling continues alone to its own completion or the cap. Cap-hit
  rates are reported per arm (§8-T7).
- **Injection point:** in the bundle arm, every turn's message is
  topped with the recomposed slice: the shared ledger export (both work
  items) plus the presence brief derived from the sibling's transcript so
  far (tool-call file paths = the touched set, mirroring the daemon's
  PostToolUse working-set window). In the ledger-only arm, the slice is
  the shared ledger export alone — identical rendering, no presence
  brief. Composed per turn by the harness, recorded per turn for audit.
  The control arm receives the identical continuation nudge with no
  slice.
- Each agent runs in its own worktree under a separate root directory;
  sibling paths are never disclosed in any prompt; worktree reset is
  tree-hash-verified per house rule. A transcript audit asserts no tool
  call escapes the agent's own worktree; a control-arm episode where an
  agent reads the sibling's worktree defeats the arm and is excluded and
  counted (pre-registered exclusion at freeze). The same audit applies
  to the ledger-only arm (its arm definition is defeated by a sibling-
  worktree read just as the control's is).

This is simulated concurrency and the writeup will say so (§8-T1): it
tests the presence CHANNEL (does live sibling scope in the slice change
behavior?), not the daemon's wall-clock delivery.

## 3. Scenario construction (the hard part, stated plainly)

A scenario is the inferential unit (the role the card plays in every
prior wave): one repo at one pinned SHA plus TWO authored work items,
each a full task card (criteria, `scope_paths`, `out_of_scope`, outcome
command), drawn from the existing ratified corpus repos.

Adjacency must create genuine collision PRESSURE without making
collision a construction artifact in either direction. Three binding
authoring rules, all checkable pre-freeze:

1. **Existence proof (anti-rigging floor):** every scenario ships with a
   committed reference solution pair whose two diffs (a) produce a clean
   `git merge-tree` from the common base and (b) pass BOTH work items'
   outcome commands on the merged tree. Collision is therefore always
   evitable; a control-arm collision is a behavioral outcome, never
   forced by construction. The reference pair also validates the outcome
   commands, exactly as merged PRs ground T-real.
2. **Pressure floor (anti-triviality):** the two work items' plausible
   implementation surfaces must intersect — shared registry/config/index
   files, shared test fixtures, shared helper modules on the import path
   of both scopes. Overlap pressure is measured, not vibed: the
   pre-freeze pressure score = files in the intersection of the two
   reference solutions' read-plus-write neighborhoods (touched files plus
   their direct importers/importees at the pinned SHA). Scenarios
   stratify low/medium/high pressure and results report by stratum
   (never silently pooled — the T-real/T-bait discipline).
3. **Symmetry:** the two work items are comparable in size (reference
   diff churn within 3x of each other) so neither agent is a bystander.

Draft sourcing: ~6 corpus repos × 5 scenarios = **30 scenarios**,
authored against already-pinned SHAs, frozen as cards before the pilot
completes; post-freeze edits follow the house amendment log and
confirmatory exclusion rule.

## 4. Metrics (C-series; deterministic first, house discipline)

All computed from the two final branch diffs, the merged tree, and the
per-session transcripts. Episode-level; reps aggregate per scenario by
the house majority-of-reps binarization before pairing. Every metric is
computed in all three arms. **Tier assignments reflect the ratified
OQ-3 decision:** C1 and C5 are the confirmatory endpoints (bundle vs
control only); C2, C3, C4 are descriptive, with their full
operationalizations retained below so a future promotion (or a Wave-2
re-registration) inherits pinned definitions rather than inventing them
post hoc.

| ID | metric | operationalization | tier |
|---|---|---|---|
| C1 | Region collision | Binary per episode: `git merge-tree` (pinned git version) of the two branches from the common base reports ≥1 content conflict; OR both agents create the same untracked path with different content. Conflict detection on the three-way base is symmetric, so no merge-order dependence. Secondary count: number of conflicted files. Near-collision (same file, hunks within 10 lines, clean merge) reported descriptively | deterministic, **confirmatory** |
| C2 | Duplicated work | Binary per episode: any cross-agent pair of ADDED-line hunks (≥5 added lines each) with normalized token-shingle Jaccard ≥ 0.6 (5-token shingles, whitespace/identifier-case normalized; threshold to be pinned at freeze after pilot calibration). Judged companion: arm-blind judge sees both diffs + both cards, verdict per direction "does this diff re-implement work covered by the sibling's diff" (met / not-met / cannot-judge; κ-calibrated per house rule, demoted below 0.6) | deterministic + judged, **descriptive** (detector unvalidated; pilot calibration readout gates any future promotion, §9-OQ-4) |
| C3 | Contradictory edits | Binary per episode, hierarchical: if merge is clean, run both outcome commands on the merged tree; contradiction = any work item whose criteria PASS on its own branch but FAIL on the merged tree (agent B's work broke agent A's landed work, or vice versa). If merge conflicts, C3 is `not-evaluable` for that episode (the conflict is already counted by C1; C3's paired analysis uses episodes evaluable in both arms, with counts of not-evaluable published per arm) | deterministic, **descriptive** (structurally anti-correlated with C1 via conflict non-evaluability) |
| C4 | Tokens-to-combined-goal | Primary form: unconditional total spend per episode (both sessions, all turns, R4 CLI-modelUsage basis), bounded by the turn cap, so failures cost what they cost instead of vanishing from the denominator. Combined-goal success is C5, its own endpoint — conditioning C4 on success would let the arms trade completion for cheapness invisibly. Descriptive companions: spend among jointly-successful episodes (labeled composition-biased), spend per satisfied criterion, and the injection-mass decomposition (addendum §3) so the treatment must repay its own injection tokens on the record | deterministic, **descriptive** (its test class is 0-for-4 across published studies) |
| C5 | Combined-goal success | Binary per episode: clean merge AND both outcome commands pass on the merged tree AND each branch passes its own outcome command. This is the anti-timidity guard: an arm must not win C1 by doing less | deterministic, **confirmatory (non-inferiority guard)** |

The unequal-completion problem is handled structurally: C4 is
unconditional and cap-bounded; C5 carries completion as its own tested
endpoint; conditional economies are descriptive and labeled.

## 5. Analysis plan sketch (prereg-shape, to be frozen verbatim later)

- Unit: the scenario (30 paired observations). Reps aggregate to
  per-scenario values first (majority-of-reps for binaries, mean for
  spend), then arms compare within scenario.
- **Confirmatory family, Holm-corrected as ONE family of TWO, on the
  bundle-vs-control pair only** (ratified OQ-3 decision, 2026-08-01):

| # | endpoint | comparison | test |
|---|---|---|---|
| 1 | C1 any-collision, superiority | `coord-pylgrim` vs `coord-none` | exact McNemar, two-sided |
| 2 | C5 combined-goal success, NON-INFERIORITY, margin −10pp | `coord-pylgrim` vs `coord-none` | one-sided Tango score test of H0: Δ ≤ −0.10 (prereg-v5 house form; CI must exclude the margin) |

  Rationale for the two-endpoint family, stated for the record: (a)
  alpha concentration — n=30 scenarios is the corpus ceiling for this
  wave, and the rung-2 lesson (§5a) is that thin paired designs die by
  margin geometry, not by effect absence; a five-way Holm split at n=30
  invites exactly that death. (b) C2's deterministic detector is
  unvalidated — no shingle threshold has ever been calibrated against a
  judged ground truth in this harness; it cannot carry confirmatory
  weight before a pilot calibration readout exists. (c) C3 is
  structurally anti-correlated with C1 via conflict non-evaluability
  (every C1 collision removes an episode from C3's evaluable set), so
  testing both double-counts one causal surface. (d) C4's test class
  (paired spend comparisons) is 0-for-4 across the published studies to
  date; registering a fifth attempt at n=30 spends alpha on the family's
  weakest prior.
- **Descriptive readouts, pre-labeled, no tests registered:**
  - C2, C3, C4 on the bundle-vs-control pair (full operationalizations
    per §4; effect sizes with per-arm Clopper-Pearson bounds, no p).
  - ALL comparisons involving `coord-ledger`: ledger-only vs control and
    bundle vs ledger-only, on every C-series metric. These are the
    attribution readouts (§1); they characterize how the bundle effect
    splits between ratified-scope sharing and live presence, and they
    are barred from the confirmatory family by construction.
- Degenerate-case rule carried verbatim: zero discordant scenarios on
  the C1 McNemar endpoint → the exact one-sided 95% Clopper-Pearson
  bound on discordance probability is the estimand.
- Per-arm Clopper-Pearson one-sided 95% bounds published for C1-C3 and
  C5, by pressure stratum, for all three arms.
- Exclusions (house): infra crashes, rate-limit aborts, harness defects
  excluded and counted; an agent giving up, stalling, or looping is an
  OUTCOME, never an exclusion; sibling-worktree reads in the control and
  ledger-only arms excluded and counted (§2); scenarios with substantive
  post-freeze edits excluded.
- Randomization: seeded schedule, rep-blocked shuffle, appended to the
  queue with order keys strictly after all existing rows; master seed 42,
  per-run seeds by the house derivation. First-mover assignment per
  episode comes from the same seed.
- Pinning per run: repo SHA, model snapshot, Claude Code version, git
  version (C1 depends on merge-tree semantics), harness commit, schedule
  seed, per-turn composed slices archived.
- Model: one mid-tier alias (sonnet), single tier. Tier interactions are
  out of scope for proof 4.

### 5a. Margin-reachability check (binding requirement on the power memo)

The pre-freeze power memo MUST verify that the C5 −10pp non-inferiority
margin is **geometrically reachable at n=30** before the family freezes
— the rung-2 card-bound lesson (`results/reports/e13-rung2-power-memo.md`):
at n=48 the −5pp margin sat below the design's resolution floor, so even
a perfect zero-discordance outcome (b=c=0) gave a one-sided 95% Tango LB
of −5.34pp and missed, and no number of reps could fix it.

Computed with the frozen Tango implementation in
`analysis/e13_confirmatory.py` (not asserted): at **n=30, b=c=0, the
one-sided 95% Tango LB is −8.27pp**, which clears the −10pp margin. The
floor therefore does not exclude the margin a priori — this design does
not repeat the rung-2 geometry error. But reachability is necessary, not
sufficient: symmetric discordance of even one scenario each way (b=1,
c=1) gives LB −10.91pp and misses, and b=c=2 gives −13.02pp. The power
memo must therefore also estimate, from pilot C5 base rates, the
probability mass on discordance patterns that clear the margin, and the
freeze is gated on that memo showing acceptable power, or on an
explicit, logged decision to accept the risk.

## 6. Pilot (permanently excluded from confirmatory)

6 scenarios (2 repos, all three pressure strata) × 3 arms × 2 reps = 36
episodes ≈ 72 multi-turn sessions. Jobs: debug the interleave
orchestrator (including the ledger-only slice composition), calibrate
the turn cap R and the C2 shingle threshold, κ-calibrate the dup-work
judge and produce the C2 detector-calibration readout (§9-OQ-4), and
measure the control-arm base rates that feed the power memo (§5a).

**Pilot gate (binding once frozen): if the control arm's any-collision
rate across pilot scenarios is below ~20% or above ~90%, the scenario set
is re-authored before freeze** — a floor because all-zero discordance
cannot power the family at n=30, a ceiling because saturation means
collision was authored in, violating the §3 spirit. The pilot is excluded
from confirmatory analysis regardless of outcome, per house rule.

## 7. Budget (subscription-bounded, one Windows host)

- Confirmatory: 30 scenarios × 3 arms × 3 reps = **270 episodes = 540
  agent-sessions**, each up to R=6 resume turns. At roughly 1.5-2x the
  token weight of a single-shot Wave-1 run per session, the envelope is
  ~900-1350 run-equivalents — a ~50% increase over draft 1's two-arm
  180-episode plan, accepted with the ratified OQ-2 decision. This is
  larger than Wave 1.5 (576) and E13 Stage 2 (720) but the same order:
  weeks of subscription trickle, which the crash-safe queue already
  absorbs.
- Pilot adds ~36 episodes (~72 sessions).
- Judge drain (C2 companion, descriptive): ≤ 2 × 270 = 540 verdicts plus
  calibration sample.
- Whether n=30 scenarios powers the two-endpoint Holm family is NOT
  asserted here: the C5 margin is geometrically reachable (§5a), but
  power depends on the pilot's discordance base rates and is the subject
  of a power memo due before freeze (the E13 power-memo motion).

## 8. Threats to validity (named, not buried)

- **T1 Simulated concurrency.** Deterministic interleave + harness-
  composed presence briefs test the information channel, not the shipped
  daemon or wall-clock racing. Sub-turn races (both agents editing the
  same file inside one turn quantum) are structurally invisible. Claims
  will be scoped to the channel.
- **T2 Author-constructed scenarios.** The founder authors the pressure.
  Counterweights: the existence proof (collision always evitable), the
  measured pressure score, published scenario cards, public harness.
- **T3 N=2 generality.** Nothing here evidences 5-agent swarms; Team
  marketing must quote the pair-wise result as pair-wise.
- **T4 Base-rate fragility.** If vanilla agents given explicit scopes
  rarely collide, the study is underpowered by reality; the pilot gate
  and the degenerate-case rule keep the report honest either way, and a
  low control base rate is itself a publishable finding about when
  coordination tooling matters.
- **T5 Same-family judge** on the C2 companion; κ-calibrated,
  confirmatory C-series never touches a judge.
- **T6 Single host, single subscription, time-spread** within the wave;
  house disclosure carries over.
- **T7 Turn-cap artifacts.** The cap may truncate arms asymmetrically
  (e.g., treatment spends turns rerouting); cap-hit rates per arm are
  published and C4 is cap-bounded by construction.
- **T8 Presence-brief fidelity.** Transcript-derived touched-paths may
  differ from the daemon's PostToolUse view; the composed slices are
  archived per turn so the discrepancy is auditable.
- **T9 Bundle attribution (softened by the three-arm design).** The
  confirmatory claim is still scoped to the bundle — that is what Team
  ships and what proof 4 declared — but the full-power ledger-only arm
  now puts the ledger/presence split on the record descriptively. The
  residual limitation: the attribution readouts carry no error control
  and must never be quoted as tested findings.
- **T10 Control-level choice (was OQ-1; resolved, limitation retained).**
  The title-only static disclosure defines the measured contrast as
  "shared ratified scope + live presence vs realistic current dispatch
  practice." Two rejected alternatives bound the interpretation: a
  full-static control (entire sibling work-item text at session start)
  would have isolated the live-refresh delta alone, so any observed
  bundle effect here confounds ratified-scope sharing with liveness —
  which is partly what the ledger-only arm's descriptive readouts
  disentangle; an existence-only control would have inflated the effect
  and was rejected as a strawman. Effects measured against title-only
  must not be quoted as pure liveness effects.

## 9. Open questions

### 9.0 Resolved (Sam, ratified 2026-08-01)

- **OQ-1 (control information level) — RESOLVED: title-only static
  disclosure**, the draft-1 position confirmed. The measured claim is
  "shared ratified scope + live presence vs realistic current dispatch
  practice." The full-static and existence-only alternatives move to the
  limitations discussion (§8-T10) as interpretive bounds, not candidate
  designs.
- **OQ-2 (arm count) — RESOLVED: three arms at full power** (control,
  ledger-only, full bundle; 3 reps × 30 scenarios each; 270 episodes,
  ~50% budget increase over draft 1). The ledger-only arm gets the
  shared ratified ledger rendered per worktree but no per-turn presence
  brief. Constraint: the confirmatory family remains bundle-vs-none
  ONLY; every ledger-only comparison is descriptive, pre-labeled as an
  attribution readout, no tests registered — the attribution arm does
  not tax proof 4's alpha.
- **OQ-3 (family composition) — RESOLVED: confirmatory Holm family = C1
  + C5 only**, on the bundle-vs-control pair. C2, C3, C4 demote to
  descriptive with full operationalizations retained (§4). Rationale:
  alpha concentration at n=30; C2's detector is unvalidated; C3 is
  structurally anti-correlated with C1 via conflict non-evaluability;
  C4's test class is 0-for-4 across published studies. See §5.

### 9.1 Remaining, for the continued review

- **OQ-4 (C2 detector).** Is token-shingle similarity a defensible
  deterministic measure for duplicated work, or is dup-work inherently
  judge-led? Urgency downgraded by the OQ-3 resolution: C2 is now
  descriptive, so nothing confirmatory rides on the answer this wave.
  What remains live: the pilot's detector-calibration readout (shingle
  verdicts vs κ-calibrated judge verdicts on pilot episodes) now GATES
  any future promotion of C2 to a tested endpoint — no calibration
  evidence, no promotion, in this wave or Wave-2.
- **OQ-5 (interleave realism).** Strict alternation with seeded first
  mover vs randomized turn order per round vs randomized turn quanta.
  Where is the determinism/realism line?
- **OQ-6 (C3 evaluability).** Conflicted episodes make C3 not-evaluable
  and C1/C3 structurally anti-correlated. Softened by the OQ-3
  resolution — with C3 descriptive, the anti-correlation no longer
  double-counts inside a tested family. Still open for the descriptive
  readout's sake: is the hierarchical definition the right descriptive
  frame, or should C3 fold into a single ordered composite (collide >
  contradict > clean)?
- **OQ-7 (existence-proof ceiling).** Does requiring a region-disjoint
  reference pair cap scenario difficulty at "separable by a careful
  agent," excluding exactly the entangled work real teams fight over?
- **OQ-8 (N=3 probe).** Is a small exploratory N=3 extension worth the
  extra sessions (now costed against a three-arm design — a 4-scenario
  probe in the control and bundle arms only would be ~48 sessions), or
  noise?
- **OQ-9 (turn-cap value).** R=6 is a guess; the pilot calibrates, but
  what is the principled stopping rule for an agent that declares
  completion falsely?

## 10. What happens next (rigor pipeline, restated)

1. Remaining-OQ review of this draft (OQ-4 through OQ-9; delegated
   reviewers + Sam). Scenario authoring begins only after the
   construction rules (§3) survive.
2. Power memo from pilot base rates, including the binding §5a
   margin-reachability and discordance-pattern analysis for C5.
3. Freeze as a numbered prereg (design, family, margins, exclusions,
   seeds, append mechanism) — committed, tagged, pushed public BEFORE
   any confirmatory row is appended.
4. Pilot → gate check → confirmatory drain → analysis per the frozen
   plan. If coordination shows no effect, or costs more than it saves,
   that publishes with the same prominence; proof 4 dies honestly (the
   docs/10 §10 rule).
