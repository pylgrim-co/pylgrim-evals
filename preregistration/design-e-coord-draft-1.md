# E-coord design — DRAFT 1, NOT FROZEN, for adversarial review

Dated: 2026-07-29 (UTC). Status: **design draft only**. Nothing here is
binding. No prereg exists, no schedule rows exist, no scenario has been
authored, no run of any kind has executed. This document exists to be
attacked: the rigor pipeline is design doc → adversarial review → freeze
(prereg-v6-coord or later) → pilot (permanently excluded) → confirmatory.
Registered ahead as the coordination study intent in the venture repo
docs/10 §2 (2026-07-17, WI-E09) and as proof 4 of the upside gate
(docs/16 §4).

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
duplicated work, contradictory edits, tokens-to-combined-goal.

What this study does NOT claim to measure: the shipped daemon
implementation (the harness materializes the product's artifact formats
mechanically, the Wave-1.5 vendored-exporter move), true wall-clock
concurrency, teams larger than the tested N, or human-plus-agent
coordination.

## 1. Shape

N agents work adjacent work items on ONE repository from one pinned SHA,
each in its own isolated worktree on its own branch (the realistic team
motion: parallel branches, merge later). Same scenario set in both arms,
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

### Arms

| arm | ledger | presence | what each agent sees |
|---|---|---|---|
| `coord-none` (control) | none | none | its own work item rendered as prompt constraints (Wave-1 arm-A discipline), plus a static one-line disclosure that another agent is concurrently working an adjacent task in this repo, with that task's TITLE only |
| `coord-pylgrim` (treatment) | shared | live | same prompt, plus a shared `.pylgrim/` ledger (BOTH work items ratified, with criteria, `scope_paths`, `out_of_scope`) rendered into each worktree, plus a presence brief recomposed at every resume turn: sibling branch, sibling touched-paths so far, sibling work-item id — exactly the schema constraints of docs/04 §10 (paths only, never content, advisory only) |

The control-arm information design is this study's arm-A move, and it is
deliberate: the control is NOT information-starved about the sibling's
existence. It knows a sibling exists and what the sibling's task is
called, because that is what a human dispatcher plausibly pastes. What a
static prompt structurally cannot hold is the sibling's ratified scope
and its LIVE touched-paths — which is precisely the product's category
claim. The measured contrast is therefore "shared ratified scope + live
presence vs static awareness," not "informed vs ignorant." Whether this
control is the honest one is open question OQ-1 (§9): a maximal control
(full sibling work-item text, static, at session start) would isolate the
live-refresh delta alone; an existence-only control would inflate the
effect. Draft position: title-only static disclosure, because it mirrors
real dispatch practice; the review should attack this.

**Two arms, not three.** The declared proof-4 contrast is bundle vs none
("shared ledger + presence briefs vs none"). A `ledger-only` mechanism
arm would attribute the effect between the two components but costs +50%
of the entire budget. Draft position: two arms confirmatory; attribution
ambiguity is a named limitation (§8-T9); a ledger-only subset is a
candidate follow-up, not part of this family. OQ-2.

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
- **Injection point:** in the treatment arm, every turn's message is
  topped with the recomposed slice: the shared ledger export (both work
  items) plus the presence brief derived from the sibling's transcript so
  far (tool-call file paths = the touched set, mirroring the daemon's
  PostToolUse working-set window). Composed per turn by the harness,
  recorded per turn for audit. The control arm receives the identical
  continuation nudge with no slice.
- Each agent runs in its own worktree under a separate root directory;
  sibling paths are never disclosed in any prompt; worktree reset is
  tree-hash-verified per house rule. A transcript audit asserts no tool
  call escapes the agent's own worktree; a control-arm episode where an
  agent reads the sibling's worktree defeats the arm and is excluded and
  counted (pre-registered exclusion at freeze).

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
the house majority-of-reps binarization before pairing.

| ID | metric | operationalization | tier |
|---|---|---|---|
| C1 | Region collision | Binary per episode: `git merge-tree` (pinned git version) of the two branches from the common base reports ≥1 content conflict; OR both agents create the same untracked path with different content. Conflict detection on the three-way base is symmetric, so no merge-order dependence. Secondary count: number of conflicted files. Near-collision (same file, hunks within 10 lines, clean merge) reported descriptively | deterministic, primary |
| C2 | Duplicated work | Binary per episode: any cross-agent pair of ADDED-line hunks (≥5 added lines each) with normalized token-shingle Jaccard ≥ 0.6 (5-token shingles, whitespace/identifier-case normalized; threshold to be pinned at freeze after pilot calibration). Judged secondary: arm-blind judge sees both diffs + both cards, verdict per direction "does this diff re-implement work covered by the sibling's diff" (met / not-met / cannot-judge; κ-calibrated per house rule, demoted below 0.6) | deterministic primary + judged secondary |
| C3 | Contradictory edits | Binary per episode, hierarchical: if merge is clean, run both outcome commands on the merged tree; contradiction = any work item whose criteria PASS on its own branch but FAIL on the merged tree (agent B's work broke agent A's landed work, or vice versa). If merge conflicts, C3 is `not-evaluable` for that episode (the conflict is already counted by C1; C3's paired analysis uses episodes evaluable in both arms, with counts of not-evaluable published per arm) | deterministic, primary |
| C4 | Tokens-to-combined-goal | Primary form: unconditional total spend per episode (both sessions, all turns, R4 CLI-modelUsage basis), bounded by the turn cap, so failures cost what they cost instead of vanishing from the denominator. Combined-goal success is C5, its own endpoint — conditioning C4 on success would let the arms trade completion for cheapness invisibly. Descriptive companions: spend among jointly-successful episodes (labeled composition-biased), spend per satisfied criterion, and the injection-mass decomposition (addendum §3) so the treatment must repay its own injection tokens on the record | deterministic, primary |
| C5 | Combined-goal success | Binary per episode: clean merge AND both outcome commands pass on the merged tree AND each branch passes its own outcome command. This is the anti-timidity guard: an arm must not win C1-C3 by doing less | deterministic, primary |

The unequal-completion problem is handled structurally: C4 is
unconditional and cap-bounded; C5 carries completion as its own tested
endpoint; conditional economies are descriptive and labeled.

## 5. Analysis plan sketch (prereg-shape, to be frozen verbatim later)

- Unit: the scenario (30 paired observations). Reps aggregate to
  per-scenario values first (majority-of-reps for binaries, mean for
  spend), then arms compare within scenario.
- **Confirmatory family, Holm-corrected as ONE family of five:**

| # | endpoint | comparison | test |
|---|---|---|---|
| 1 | C1 any-collision, superiority | treatment vs control | exact McNemar, two-sided |
| 2 | C2 any-dup (deterministic detector), superiority | treatment vs control | exact McNemar, two-sided |
| 3 | C3 any-contradiction, superiority | treatment vs control | exact McNemar, two-sided |
| 4 | C4 total spend | treatment − control | repo-level sign-flip permutation (exact), two-sided (prereg-v2-ext endpoint-2 house test) |
| 5 | C5 combined-goal success, NON-INFERIORITY, draft margin −10pp | treatment vs control | one-sided Tango score test of H0: Δ ≤ −0.10 (prereg-v5 house form; CI must exclude the margin) |

- Degenerate-case rule carried verbatim: zero discordant scenarios on
  any McNemar endpoint → the exact one-sided 95% Clopper-Pearson bound
  on discordance probability is the estimand.
- Per-arm Clopper-Pearson one-sided 95% bounds published for C1-C3 and
  C5, by pressure stratum.
- Exclusions (house): infra crashes, rate-limit aborts, harness defects
  excluded and counted; an agent giving up, stalling, or looping is an
  OUTCOME, never an exclusion; control-arm sibling-worktree reads
  excluded and counted (§2); scenarios with substantive post-freeze
  edits excluded.
- Randomization: seeded schedule, rep-blocked shuffle, appended to the
  queue with order keys strictly after all existing rows; master seed 42,
  per-run seeds by the house derivation. First-mover assignment per
  episode comes from the same seed.
- Pinning per run: repo SHA, model snapshot, Claude Code version, git
  version (C1 depends on merge-tree semantics), harness commit, schedule
  seed, per-turn composed slices archived.
- Model: one mid-tier alias (sonnet), single tier. Tier interactions are
  out of scope for proof 4.

## 6. Pilot (permanently excluded from confirmatory)

6 scenarios (2 repos, all three pressure strata) × 2 arms × 2 reps = 24
episodes ≈ 48 multi-turn sessions. Jobs: debug the interleave
orchestrator, calibrate the turn cap R and the C2 shingle threshold,
κ-calibrate the dup-work judge, and measure the control-arm base rates.

**Pilot gate (binding once frozen): if the control arm's any-collision
rate across pilot scenarios is below ~20% or above ~90%, the scenario set
is re-authored before freeze** — a floor because all-zero discordance
cannot power the family at n=30, a ceiling because saturation means
collision was authored in, violating the §3 spirit. The pilot is excluded
from confirmatory analysis regardless of outcome, per house rule.

## 7. Budget (subscription-bounded, one Windows host)

- Confirmatory: 30 scenarios × 2 arms × 3 reps = 180 episodes = 360
  agent-sessions, each up to R=6 resume turns. At roughly 1.5-2x the
  token weight of a single-shot Wave-1 run per session, the envelope is
  ~600-900 run-equivalents — the same order as Wave 1.5 (576) and E13
  Stage 2 (720), i.e., weeks of subscription trickle, which the
  crash-safe queue already absorbs.
- Pilot adds ~24 episodes (~50 sessions).
- Judge drain (C2 secondary): ≤ 2 × 180 = 360 verdicts plus calibration
  sample.
- Whether n=30 scenarios powers five Holm endpoints is NOT asserted
  here: it depends on the pilot's discordance base rates and is the
  subject of a power memo due before freeze (the E13 power-memo motion).
  OQ-3.

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
- **T5 Same-family judge** on the C2 secondary; κ-calibrated, primary
  C-series never touches a judge.
- **T6 Single host, single subscription, time-spread** within the wave;
  house disclosure carries over.
- **T7 Turn-cap artifacts.** The cap may truncate arms asymmetrically
  (e.g., treatment spends turns rerouting); cap-hit rates per arm are
  published and C4 is cap-bounded by construction.
- **T8 Presence-brief fidelity.** Transcript-derived touched-paths may
  differ from the daemon's PostToolUse view; the composed slices are
  archived per turn so the discrepancy is auditable.
- **T9 Bundle attribution.** With two arms, ledger and presence effects
  are inseparable; the claim is scoped to the bundle, which is what Team
  ships and what proof 4 declared.
- **T10 Prompt-symmetry choice.** The control's title-only static
  disclosure defines the contrast; a different control changes the
  measured claim (OQ-1).

## 9. Open questions for the adversarial review

- **OQ-1 (control information level).** Existence-only vs title-only vs
  full-static sibling scope at session start. Draft picks title-only.
  Which contrast is the honest Team-tier claim, and does full-static
  deserve to be the control even though it halves the expected effect?
- **OQ-2 (arm count).** Is bundle-vs-none defensible for proof 4, or
  does the review demand the ledger-only mechanism arm at +50% budget
  (or as a reduced-rep descriptive cell)?
- **OQ-3 (power).** Five Holm endpoints on 30 paired scenarios with
  unknown discordance rates. Should C2 or C3 demote to descriptive to
  concentrate power? What does the power memo need from the pilot to
  decide this before freeze?
- **OQ-4 (C2 detector).** Is token-shingle similarity a defensible
  deterministic primary for duplicated work, or is dup-work inherently
  judge-led and therefore secondary-only under house rules?
- **OQ-5 (interleave realism).** Strict alternation with seeded first
  mover vs randomized turn order per round vs randomized turn quanta.
  Where is the determinism/realism line?
- **OQ-6 (C3 evaluability).** Conflicted episodes make C3 not-evaluable
  and C1/C3 structurally anti-correlated. Is the hierarchical definition
  sound, or should C3 fold into a single ordered composite (collide >
  contradict > clean)?
- **OQ-7 (existence-proof ceiling).** Does requiring a region-disjoint
  reference pair cap scenario difficulty at "separable by a careful
  agent," excluding exactly the entangled work real teams fight over?
- **OQ-8 (N=3 probe).** Is a 4-scenario exploratory N=3 extension worth
  ~40 extra sessions, or noise?
- **OQ-9 (turn-cap value).** R=6 is a guess; the pilot calibrates, but
  what is the principled stopping rule for an agent that declares
  completion falsely?

## 10. What happens next (rigor pipeline, restated)

1. Adversarial review of this draft (delegated reviewers + Sam), issues
   filed against each OQ.
2. Draft 2 absorbs the review; scenario authoring begins only after the
   construction rules (§3) survive.
3. Power memo from pilot base rates.
4. Freeze as a numbered prereg (design, family, margins, exclusions,
   seeds, append mechanism) — committed, tagged, pushed public BEFORE
   any confirmatory row is appended.
5. Pilot → gate check → confirmatory drain → analysis per the frozen
   plan. If coordination shows no effect, or costs more than it saves,
   that publishes with the same prominence; proof 4 dies honestly (the
   docs/10 §10 rule).
