# E-coord design — DRAFT 3, NOT FROZEN, review round 1 folded in

Dated: 2026-08-01 (UTC). Status: **design draft only**. Nothing here is
binding. No prereg exists, no schedule rows exist, no scenario has been
authored, no run of any kind has executed. This revision folds in the
round-1 adversarial review (`design-e-coord-review-1.md`, commit
2e8fb2c): the minimal fix of every finding (M1-M10, O1-O10) is applied
in the section text itself, and Sam's ratified decisions (2026-08-01)
are absorbed — the C5 form change to the M1/M2/M7/M10 falsification
package (§5), the always-on Hetzner Linux VM as the pinned execution
environment (§7), and the §C positions on OQ-5 through OQ-9 (§9.0).
Appendix A is the findings crosswalk, the review-closure artifact for
round 1. The rigor pipeline is design doc → adversarial review → freeze
(prereg-v6-coord or later) → pilot (permanently excluded) →
confirmatory. Registered ahead as the coordination study intent in the
venture repo docs/10 §2 (2026-07-17, WI-E09) and as proof 4 of the
upside gate (docs/16 §4). Drafts 1 and 2
(`design-e-coord-draft-1.md`, `design-e-coord-draft-2.md`) remain in
place per the numbered-artifact convention; this document supersedes
both.

## 0. The claim under test

Team tier ($30/seat) sells coordination. The specific mechanism claims:
the shared `.pylgrim/` ledger gives every agent the same ratified picture
of who owns which work item and scope, and presence briefs put live
sibling-session scope (branch, scope paths, work-item id — paths only,
advisory, ephemeral; docs/04 §10) into each agent's per-message slice.
The marketing sentence this study either funds or kills: "presence
briefing tells two agents converging on the same file about each other
before the merge does." Whether it is funded is decided by the §5
conjunction rule, not by any single endpoint in isolation.

Declared endpoints (docs/16 §4, verbatim): region-collision rate,
duplicated work, contradictory edits, tokens-to-combined-goal. All four
are still measured and published; the confirmatory structure is now
settled in §5: ONE tested endpoint (C1) plus a frozen deterministic
falsification package on C5. The rest are descriptive with their
operationalizations retained in full.

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
file. Claims are scoped to pairs; the N=3 extension is resolved OUT of
this wave (ratified OQ-8 position, §9.0) — it is a natural follow-up if
the bundle lands, not part of this design.

### Arms (three, per the ratified OQ-2 decision)

| arm | ledger | presence | what each agent sees |
|---|---|---|---|
| `coord-none` (control) | none | none | its own work item rendered as prompt constraints (Wave-1 arm-A discipline), plus a static one-line disclosure that another agent is concurrently working an adjacent task in this repo, with that task's TITLE only |
| `coord-ledger` (attribution) | shared | none | same prompt and title-only static disclosure discipline, plus the shared `.pylgrim/` ledger (BOTH work items ratified, with criteria, `scope_paths`, `out_of_scope`) carried in each turn's slice exactly as in the bundle arm — rendered by the harness OUTSIDE the worktree, never materialized on disk inside it (O7/O8, §2) — but NO per-turn presence brief, ever |
| `coord-pylgrim` (treatment) | shared | live | same prompt, plus the shared `.pylgrim/` ledger in each turn's slice (same outside-the-worktree rendering), plus a presence brief recomposed at every resume turn: sibling branch, sibling touched-paths so far, sibling work-item id — exactly the schema constraints of docs/04 §10 (paths only, never content, advisory only) |

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
single-endpoint confirmatory structure.** The ratified OQ-2 decision buys
the ledger-only mechanism arm at full replication (3 reps × 30 scenarios,
+50% of the draft-1 budget, §7 — subject to the pre-committed wall-clock
fallback lever, §7, which may cut ledger-arm reps to 2) rather than as a
reduced-rep cell. The binding constraint that keeps this from taxing
proof 4's alpha: **the confirmatory comparison remains bundle-vs-none
ONLY.** Every comparison involving `coord-ledger` — ledger-only vs
control, bundle vs ledger-only — is DESCRIPTIVE, pre-labeled here as
attribution readouts; no test of any kind is registered on them, now or
ever on this wave's data (the M8 fresh-data rule, §5). The attribution
arm exists to answer "how much of the bundle effect is the ratified
ledger alone?" on the record, with confirmatory-grade data quality,
without ever entering the tested family. Draft-1's T9 (bundle
attribution as a named limitation) is accordingly softened, not deleted
(§8-T9).

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
- **First mover (M3 fix):** which agent takes the first turn is derived
  per episode from **sha256(scenario_id, rep) only** — the derivation
  deliberately excludes run_id and arm, so first-mover assignment is
  identical across the three arms of a paired scenario. (Draft 2 derived
  it from run_id, which contains the arm; that confounded first-mover
  assignment with arm across pairs.) Thereafter strict alternation
  A,B,A,B — the ratified OQ-5 position: determinism over simulated
  realism; randomized turn order or turn quanta buy realism theater at
  the cost of reproducibility, and real-timing evidence comes from
  daemon telemetry later, not from this harness.
- **Turn cap:** R rounds per agent (draft R=6; pilot calibrates; §7
  carries a pre-committed R=4 fallback lever). R is fixed and identical
  across arms. An agent that declares completion before the cap stops
  resuming; its sibling continues alone to its own completion or the
  cap. An agent that declares completion FALSELY is an outcome (a C5
  failure), never rescued and never excluded — the cap is the stopping
  rule (ratified OQ-9 position). Cap-hit rates are reported per arm
  (§8-T7).
- **Injection point:** in the bundle arm, every turn's message is
  topped with the recomposed slice: the shared ledger export (both work
  items) plus the presence brief derived from the sibling's transcript so
  far (tool-call file paths = the touched set, mirroring the daemon's
  PostToolUse working-set window). In the ledger-only arm, the slice is
  the shared ledger export alone — identical rendering, no presence
  brief. **The slice is the ledger's ONLY channel: the harness renders
  the ledger outside every worktree and never materializes it on disk
  inside one (O7/O8).** An in-worktree render would have put `.pylgrim/`
  files in two of three arms' diffs — contaminating C1's untracked-path
  clause with harness-manufactured collisions and leaking arm identity
  to the C2 judge; slice-only delivery kills that leak class by
  construction. Composed per turn by the harness, recorded per turn for
  audit. The control arm receives the identical continuation nudge with
  no slice. **Per-turn context tokens and compaction events are logged
  per session (M9)** and published per arm beside cap-hit rates (§5,
  §8-T11).
- Each agent runs in its own worktree under a separate root directory;
  sibling paths are never disclosed in any prompt; worktree reset is
  tree-hash-verified per house rule. A transcript audit asserts no tool
  call escapes the agent's own worktree; a control-arm episode where an
  agent reads the sibling's worktree defeats the arm and is excluded and
  counted (pre-registered exclusion at freeze). The same audit applies
  to the ledger-only arm (its arm definition is defeated by a sibling-
  worktree read just as the control's is), and it additionally asserts
  no tool call reaches the reference-solution store (§3, M5).
- **Episode checkpointing (O1 fix):** the existing queue's rows are
  run-granular (one row, one session, one transcript) and cannot
  represent a multi-turn two-session episode; "the crash-safe queue
  absorbs this" was false at episode granularity. The harness therefore
  adds an **`episode_turns` checkpoint table — (episode_id, agent, turn,
  session_id, slice_path, tree_hash, status) — written atomically at
  every turn boundary.** Resume after any interruption = replay from the
  last checkpoint after tree-hash verification of both worktrees; a
  mid-episode death loses at most one turn, never the episode.
- **Gate semantics (O2 fix):** rate-limit gates are PAUSES, never
  aborts. On gate, the runner checkpoints, waits out `resume_after`, and
  resumes the SAME sessions in the SAME turn order from the checkpoint.
  The "rate-limit abort" exclusion class (§5) is narrowed to unresumable
  defects only; gate-straddling is normal operation, not an exclusion —
  otherwise longer treatment episodes would straddle more gates and be
  differentially excluded by arm. Pause counts are published per arm.
- **Merged-tree slot (O5 fix):** C1, C3, and C5 evaluate a merged tree
  that must actually be materialized, and the two agent slots are both
  live worktrees. Each episode gets a THIRD slot: `git merge-tree
  --write-tree` + `commit-tree` + `worktree add`, subject to the same
  tree-hash-verified reset rule as the agent slots.
- **Process hygiene (O6 fix, stated in Linux form per the ratified VM
  decision, §7):** each turn's `claude` CLI runs in its own process
  group (`start_new_session`); on turn completion or timeout the entire
  group is killed (`killpg`), and a pre-turn assertion verifies no PID
  from any prior turn survives. The returned `session_id` is persisted
  atomically (temp-file write + rename into the `episode_turns` row)
  BEFORE any subsequent step, so a crash between CLI completion and
  persistence can no longer orphan an unaccountable, unresumable
  session. The reviewed Windows forms of this fix (Job Objects,
  `powercfg` sleep-disable) are superseded by the environment decision:
  the VM is always-on, which removes the sleep/wake worktree-corruption
  class outright, and the runner's systemd unit uses control-group kill
  semantics.
- **Runner topology (O10 fix):** the episode runner is ONE long-lived
  Python process on the drain2 pattern (commit 779d687): claim episode,
  execute turns via direct `subprocess` invocations of `claude`,
  heartbeat per claim, mark, claim next. No PowerShell→bash→python spawn
  chain, no per-turn interpreter spawns (~12 per episode under the old
  shape), no backgrounded trees to orphan. It runs as a systemd unit
  (start on boot, restart on failure); a stale heartbeat is the death
  detector, and startup reclaims only heartbeat-stale claims.

This is simulated concurrency and the writeup will say so (§8-T1): it
tests the presence CHANNEL (does live sibling scope in the slice change
behavior?), not the daemon's wall-clock delivery.

## 3. Scenario construction (the hard part, stated plainly)

A scenario is the inferential unit (the role the card plays in every
prior wave): one repo at one pinned SHA plus TWO authored work items,
each a full task card (criteria, `scope_paths`, `out_of_scope`, outcome
command), drawn from the existing ratified corpus repos.

Adjacency must create genuine collision PRESSURE without making
collision a construction artifact in either direction. Four binding
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
4. **Wall-time floor (O4 fix):** each work item's outcome command
   completes in **≤120 seconds per tree, measured on the pinned
   execution host (the §7 VM) at the pinned SHA** — scoped/targeted test
   invocations, not whole-suite runs. One timeout constant governs every
   outcome-command execution in the study; shared build caches are
   pinned as harness config. Rationale: C5 alone implies four outcome
   runs per episode (~1,080+ across the confirmatory drain); without
   this rule, heavy-suite repos of the nushell/hugo class are nonviable
   and the calendar math of §7 collapses.

Two anti-leak process rules attach to the existence proof (M5 fix):

- **Authoring order:** both task cards are authored, committed, and
  logged BEFORE any reference solution is attempted; the commit sequence
  is the audit trail. This blocks the leak where knowledge of the
  reference pair's known-disjoint split flows backward into
  `scope_paths`, pre-partitioning the repo for the agents.
- **Reference-pair location:** reference solutions live OUTSIDE every
  agent-reachable root — never inside any worktree or slot — and the §2
  transcript/worktree audit asserts no tool call reaches them.

And one honesty rule on scope: the existence-proof filter necessarily
selects scenarios where a disjoint solution demonstrably exists, so all
claims are scoped to **"scenarios with a verified disjoint solution"**
(ratified OQ-7 position: keep the existence proof — without it C1 is
uninterpretable — and name the selection; genuinely entangled work is a
follow-up study, not a silent generalization).

**Determinism check (M6 fix):** pre-freeze, each scenario's two outcome
commands are run **k≥3 times on the reference merged tree; any flake
(non-identical pass/fail across the k runs) disqualifies the scenario**
until the command is fixed and re-verified. A flaky outcome command is
exactly the machine that manufactures spurious C5 discordance — the
b=1/c=1-class noise the §5 tripwire must not be fed.

Draft sourcing: ~6 corpus repos × 5 scenarios = **30 scenarios**,
authored against already-pinned SHAs, frozen as cards before the pilot
completes; post-freeze edits follow the house amendment log and the
mechanically-defined substantive-edit exclusion rule (§5, M4). The
5-per-repo clustering is a known independence violation carried to the
analysis plan as pre-registered leave-one-repo-out sensitivity (§5, M6).

## 4. Metrics (C-series; deterministic first, house discipline)

All computed from the two final branch diffs, the merged tree (§2, O5
slot), and the per-session transcripts. Episode-level; reps aggregate
per scenario by the house majority-of-reps binarization before pairing.
Every metric is computed in all three arms. **Tier assignments reflect
the ratified OQ-3 decision as revised by the ratified C5-form decision
(2026-08-01):** C1 is the sole TESTED endpoint (bundle vs control only);
C5 is the deterministic falsification guard — no statistical test, §5;
C2, C3, C4 are descriptive, with their full operationalizations retained
below so a future promotion (or a Wave-2 re-registration) inherits
pinned definitions rather than inventing them post hoc.

| ID | metric | operationalization | tier |
|---|---|---|---|
| C1 | Region collision | Binary per episode: `git merge-tree` (pinned git version) of the two branches from the common base reports ≥1 content conflict; OR both agents create the same untracked path with different content. Conflict detection on the three-way base is symmetric, so no merge-order dependence. Secondary count: number of conflicted files. Near-collision (same file, hunks within 10 lines, clean merge) reported descriptively. The untracked-path clause is reported as a SEPARATE subcomponent (M7) so filename trivia cannot silently carry the endpoint; the `.pylgrim/` ledger is never materialized in any worktree (slice-only, §2), so harness artifacts cannot satisfy this clause — belt-and-braces, `.pylgrim/**` is excluded from capture, C1, and the pressure score, stated at freeze (O8) | deterministic, **confirmatory (sole tested endpoint)** |
| C2 | Duplicated work | Binary per episode: any cross-agent pair of ADDED-line hunks (≥5 added lines each) with normalized token-shingle Jaccard ≥ 0.6 (5-token shingles, whitespace/identifier-case normalized; threshold to be pinned at freeze after pilot calibration). Judged companion: arm-blind judge sees both diffs + both cards, verdict per direction "does this diff re-implement work covered by the sibling's diff" (met / not-met / cannot-judge; κ-calibrated per house rule, demoted below 0.6) | deterministic + judged, **descriptive** (detector unvalidated; pilot calibration readout gates any future promotion, §9.0-OQ-4) |
| C3 | Contradictory edits | Binary per episode, hierarchical: if merge is clean, run both outcome commands on the merged tree; contradiction = any work item whose criteria PASS on its own branch but FAIL on the merged tree (agent B's work broke agent A's landed work, or vice versa). If merge conflicts, C3 is `not-evaluable` for that episode (the conflict is already counted by C1; C3's paired analysis uses episodes evaluable in both arms, with counts of not-evaluable published per arm). Per the ratified OQ-6 position, a SECOND descriptive frame is reported alongside: the ordered composite collide > contradict > clean, which has no evaluability hole | deterministic, **descriptive** (structurally anti-correlated with C1 via conflict non-evaluability) |
| C4 | Tokens-to-combined-goal | Primary form: unconditional total spend per episode (both sessions, all turns, R4 CLI-modelUsage basis), bounded by the turn cap, so failures cost what they cost instead of vanishing from the denominator. Combined-goal success is C5, its own endpoint — conditioning C4 on success would let the arms trade completion for cheapness invisibly. Descriptive companions: spend among jointly-successful episodes (labeled composition-biased), spend per satisfied criterion, and the injection-mass decomposition (addendum §3) so the treatment must repay its own injection tokens on the record | deterministic, **descriptive** (its test class is 0-for-4 across published studies) |
| C5 | Combined-goal success | Binary per episode: clean merge AND both outcome commands pass on the merged tree AND each branch passes its own outcome command. This is the anti-timidity guard: an arm must not win C1 by doing less | deterministic, **confirmatory guard (falsification tripwire + disclosure rules, no statistical test — §5)** |

The unequal-completion problem is handled structurally: C4 is
unconditional and cap-bounded; C5 carries completion as the frozen
falsification guard on the C1 claim; conditional economies are
descriptive and labeled.

**Judge protocol (O7 fix; applies to the C2 companion and any future
judged readout):** the pre-judge scrub extends its denylist beyond
CLAUDE.md to `.pylgrim/` path strings, work-item ids, and
presence/sibling phrasing, with skip-and-count on any diff the scrub
cannot clean. Verdicts use the strict-JSON structured-output path
(verdicts JSON Schema via `--json-schema`, one re-ask on residual
failure; commit 779d687). With the ledger slice-only (§2), ledger
content cannot appear in any diff by construction — the extended scrub
is defense in depth, not the primary barrier. Two-diff verdicts carry
roughly double the prompt mass of single-diff ones; truncation events
are counted and published.

## 5. Analysis plan sketch (prereg-shape, to be frozen verbatim later)

- Unit: the scenario (30 paired observations). Reps aggregate to
  per-scenario values first (majority-of-reps for binaries, mean for
  spend), then arms compare within scenario.
- **Confirmatory structure (ratified C5-form decision, 2026-08-01;
  replaces draft 2's two-endpoint Holm family): ONE tested endpoint plus
  a frozen deterministic falsification package, on the bundle-vs-control
  pair only.**

| # | element | comparison | form |
|---|---|---|---|
| 1 | C1 any-collision, superiority | `coord-pylgrim` vs `coord-none` | exact McNemar, two-sided, α=0.05 |
| 2 | C5 falsification package | `coord-pylgrim` vs `coord-none` | frozen deterministic publication rules — NOT a statistical test (verbatim below) |

  Stated precisely: **the Holm family reduces to C1 alone as the tested
  endpoint.** With a singleton family, Holm correction is vacuous and no
  multiplicity adjustment applies. **No alpha is spent on the C5
  package, because none is needed: a deterministic decision rule on
  observed counts makes no probabilistic claim and carries no error
  rate to control.** It is a pre-committed publication rule, frozen
  verbatim at prereg time. Draft 2's rationale for excluding C2/C3/C4
  from testing (detector unvalidated; structural anti-correlation with
  C1; 0-for-4 test class) stands unchanged and now also explains why
  the family is this small.

  **The C5 falsification package, verbatim (M1/M2/M7/M10):**

  1. **Conjunction rule (M1).** The coordination claim — the §0
     marketing sentence — is funded only if C1 lands (McNemar
     significant, collision-reducing direction) AND the C5 tripwire
     (rule 2) does not fire. **A C1 pass with the tripwire fired
     publishes as claim-not-funded**, with the same prominence as a
     funded claim. This closes the fail-open hole draft 2 left: under
     the old family logic, C1-pass/C5-miss — plausibly the modal
     outcome — licensed exactly the artifact-vulnerable claim C5 exists
     to block.
  2. **Tripwire (M2).** On the majority-of-reps scenario-level C5
     values, let **c = the number of scenarios where ONLY the control
     arm reaches combined-goal success** and **b = the number where ONLY
     the treatment arm does**. **The C1 claim dies if net harm
     c − b ≥ 2.** This replaces draft 2's −10pp Tango non-inferiority
     test, which was geometry-forced (the only reachable margin at
     n=30) and failed closed under trivial noise (b=c=1 → LB −10.91pp,
     an automatic miss), while the 6-scenario pilot could never estimate
     discordance rates well enough to power it.
  3. **Absolute-rate disclosure (M7/M10).** The treatment arm's absolute
     C5 success rate, with its one-sided 95% Clopper-Pearson bound, is
     published beside EVERY quotation of the C1 result, in any venue.
  4. **Framing floor (M10).** If the treatment-arm absolute C5 rate is
     below **50%** (pre-committed threshold), the claim publishes only
     as "collision reduction in a regime where combined success is not
     attained"; the C1 sentence may not be quoted without that frame.
     This closes the concordant-failure hole: a guard that compares arms
     is vacuous when both arms fail together.

- **Exposure descriptives (M7, pre-registered):** per arm: turns used,
  diff churn (added+deleted lines), files touched, and churn ratio vs
  the reference solution. **Every C1-discordant scenario receives a
  mandatory audit note including its churn ratio** — did the treatment
  "win" C1 by doing less (narrower defer-the-shared-file diffs, early
  stopping)? The untracked-path subcomponent of C1 is reported
  separately (§4). These make the C1 artifact channels visible that C5
  alone cannot see.
- **Descriptive readouts, pre-labeled, no tests registered:**
  - C2, C3, C4 on the bundle-vs-control pair (full operationalizations
    per §4, including C3's two frames per the ratified OQ-6 position;
    effect sizes with per-arm Clopper-Pearson bounds, no p).
  - ALL comparisons involving `coord-ledger`: ledger-only vs control and
    bundle vs ledger-only, on every C-series metric. These are the
    attribution readouts (§1); they characterize how the bundle effect
    splits between ratified-scope sharing and live presence, and they
    are barred from the confirmatory family by construction.
  - **Fresh-data rule (M8), prereg sentence verbatim:** *no test of any
    kind will ever be computed on this wave's `coord-ledger` cells; any
    future attribution claim must be registered on fresh data.* Every
    ledger-arm interval is labeled **"descriptive, no error control"**
    at its point of publication, so the Clopper-Pearson dressing cannot
    be quoted as inference.
- **Injection-mass logging (M9):** per-turn context tokens and
  compaction events, logged per session (§2), published per arm beside
  cap-hit rates. The confound — per-turn context growth and compaction
  behavior are collinear with arm, and pairing cannot remove them — is
  carried as an interpretive limitation (§8-T11); no filler-control arm
  exists this wave.
- **Leverage and clustering sensitivities (M6, pre-registered):**
  leave-one-scenario-out and leave-one-repo-out recomputation of the C1
  test AND the tripwire counts (a single scenario is 3-13% of the
  evidence; 5-per-repo sourcing violates strict pair independence), plus
  per-repo discordance reporting. Published with the primary result.
- Degenerate-case rule carried verbatim: zero discordant scenarios on
  the C1 McNemar endpoint → the exact one-sided 95% Clopper-Pearson
  bound on discordance probability is the estimand.
- Per-arm Clopper-Pearson one-sided 95% bounds published for C1-C3 and
  C5, by pressure stratum, for all three arms (ledger-arm bounds carry
  the M8 label above).
- **Exclusions (house rule, hardened per M4):**
  - **Closed defect taxonomy.** The only excludable classes, each with a
    mechanical detector, frozen at prereg: (i) runner/harness crash the
    §2 checkpoint replay cannot resume; (ii) CLI invocation failure
    (nonzero exit or no session_id) after bounded retry; (iii) worktree
    tree-hash mismatch at a turn boundary; (iv) unresumable session
    (resume rejected). Adjudication runs on detector output BEFORE any
    metric is computed, blind to outcomes. There is no open-ended
    "harness defect" class on a brand-new orchestrator.
  - **Rerun, not drop.** An excluded rep is RERUN with a fresh seed
    rather than dropped, so the heavier treatment arm (more turns, more
    gate-straddling) cannot differentially lose observations; the
    excluded rep itself is retained and counted.
  - **Exclusion-impact sensitivity.** The C1 result and tripwire counts
    are recomputed under worst-case assignment of all excluded-then-
    rerun episodes; published beside the primary.
  - Rate-limit pauses are NOT exclusions (§2, O2); only unresumable
    defects qualify. Pause counts published per arm.
  - An agent giving up, stalling, looping, or falsely declaring
    completion is an OUTCOME, never an exclusion (ratified OQ-9).
  - Sibling-worktree reads in the control and ledger-only arms defeat
    the arm: excluded and counted (§2); the detector is the mechanical
    transcript path audit.
  - **Substantive post-freeze edit, defined mechanically:** any change
    to a card's criteria, `scope_paths`, `out_of_scope`, outcome
    command, or pinned SHA — detected by normalized field hash — is
    substantive and excludes the scenario; prose-only edits are logged
    in the amendment log and are not substantive.
- Randomization: seeded schedule, rep-blocked shuffle, appended to the
  queue with order keys strictly after all existing rows; master seed 42,
  per-run seeds by the house derivation. **First-mover assignment per
  episode comes from sha256(scenario_id, rep) only — never from run_id
  or arm (M3, §2).**
- Pinning per run: repo SHA, model snapshot, Claude Code version, git
  version (C1 depends on merge-tree semantics), harness commit, schedule
  seed, per-turn composed slices archived, and the execution-environment
  pins of §7 (VM class, OS image, vm-setup.md revision).
- Model: one mid-tier alias (sonnet), single tier. Tier interactions are
  out of scope for proof 4.

### 5a. C1 discordance planning (binding requirement on the power memo)

Draft 2's §5a carried a Tango margin-reachability computation for the
C5 −10pp non-inferiority test (n=30, b=c=0 → one-sided 95% LB −8.27pp,
clearing the margin; b=c=1 → −10.91pp, missing it). **That math is
removed, not moved:** the ratified C5-form decision (§5) replaced the NI
test with a deterministic tripwire, so there is no margin whose
reachability needs proving, and retaining the computation would imply a
test that no longer exists. The lesson that motivated it — the rung-2
card-bound finding that thin paired designs die by margin geometry
(`results/reports/e13-rung2-power-memo.md`) — is precisely WHY the NI
form was abandoned, and is preserved here as that rationale.

What the pre-freeze power memo must now show, fed by the pilot:

- from pilot control-arm C1 base rates: the projected distribution of
  C1-discordant pairs at n=30 and the power of the exact two-sided
  McNemar test at α=0.05 across plausible treatment effects;
- the projected probability of the degenerate case (zero discordance →
  CP bound as estimand, §5), so the report's likely shape is known
  before freeze;
- descriptively (informative, not a gate): the probability of a spurious
  tripwire fire (c − b ≥ 2 arising under no true C5 harm) at
  pilot-estimated C5 rates and the frozen rep count, so the tripwire's
  strictness is on the record before it is frozen.

**The freeze is gated on the memo showing acceptable C1 power, or on an
explicit, logged decision to accept the risk.** The wall-clock memo (§7)
is the second, parallel gate.

## 6. Pilot (permanently excluded from confirmatory)

6 scenarios (2 repos, all three pressure strata) × 3 arms × 2 reps = 36
episodes ≈ 72 multi-turn sessions, run on the §7 VM. Jobs: debug the
interleave orchestrator end-to-end on the drain2-pattern runner
(including the ledger-only slice composition, the `episode_turns`
checkpoint/resume path, and pause-not-abort gate handling); calibrate
the turn cap R (including whether the R=4 fallback lever is viable) and
the C2 shingle threshold; κ-calibrate the dup-work judge and produce the
C2 detector-calibration readout (§9.0-OQ-4); measure the control-arm C1
base rates that feed the power memo (§5a); measure per-turn wall-clock
latency on the VM for the wall-clock memo (§7); and record pilot C5
rates for the tripwire-noise readout (§5a).

**Pilot gate (binding once frozen): if the control arm's any-collision
rate across pilot scenarios is below ~20% or above ~90%, the scenario set
is re-authored before freeze** — a floor because all-zero discordance
cannot power the C1 test at n=30, a ceiling because saturation means
collision was authored in, violating the §3 spirit. The pilot is excluded
from confirmatory analysis regardless of outcome, per house rule.

## 7. Budget and execution environment (subscription-bounded, one always-on VM)

- **Execution environment (ratified 2026-08-01):** an **always-on
  Hetzner Linux VM — CPX32 — 4 vCPU/8GB, sized for strictly-serial episodes, CPX42 rescale path for parallel drains — Ubuntu 24.04, Hillsboro; docs/ops/vm-setup.md** — replaces
  the local Windows host, and is **pinned at freeze**. Rationale: the
  honest calendar math below makes the drain a 6-10+ week affair, and a
  sleep/wake-exposed laptop-class host cannot carry a multi-week
  always-on drain (the O6 corruption class). A provisioning guide is
  being written in parallel at `docs/ops/vm-setup.md` and is the
  reference for the pinned setup. Pinning-list entries this decision
  adds: VM instance class, OS image and version, installed git and
  Claude Code CLI versions, and the `vm-setup.md` revision in force.
- **Budget in the honest unit — CLI completions (O3 fix).** Draft 2's
  "run-equivalents" understated the object actually rate-limited and
  scheduled: the individual `claude -p` completion. An episode is up to
  2 × R = 12 turn completions; 270 confirmatory episodes ≈ up to ~3,240
  completions, plus the pilot (~430) and the judge drain — **~3,300-
  4,200 CLI completions total including pilot and judging, 5-7× the
  largest drain to date (E13).** Turns within an episode are inherently
  serial (each resume depends on the prior turn), so the drain is
  wall-clock-bound, not queue-bound: ~130-200 drain-hours, realistically
  spanning weeks of subscription trickle.
- **Binding wall-clock memo (O3).** Beside the §5a power memo, before
  freeze, fed by measured pilot per-turn latency on the VM: projected
  calendar time for the full confirmatory drain. **Freeze is gated on
  both memos.**
- **Pre-committed fallback levers (O3),** applied in order if the
  wall-clock memo shows unacceptable calendar time, and only these:
  (1) **R = 4** (pilot verifies most episodes complete under it);
  (2) **ledger-arm reps = 2** (the descriptive attribution arm absorbs
  the cut; the tested bundle-vs-control cells keep 3 reps). No other
  reduction may be introduced at or after freeze.
- **Episode concurrency = 2 (O9, AMENDED, ratified 2026-08-02):** the
  draft pinned strictly-serial episodes to design out the observed
  lock-contention class. The pilot deviated (the runner claimed 2
  episodes concurrently) and produced the amendment's evidence: 36/36
  episodes, 349 turns, ZERO git-lock or workspace failures under 2-way
  concurrency on the VM, at roughly half the serial calendar (270
  confirmatory episodes ≈ 3.5 days vs ~7). Amended rule: at most TWO
  episodes in flight, each with its own three slots; bounded retry on
  transient git lock errors retained; any lock-class failure at
  confirmatory time is a §5 mechanical defect (rerun, not dropped) and
  3+ occurrences trigger a pre-committed fallback to serial. The
  original serial pin and this amendment history both freeze. (The
  reviewed Windows-specific mitigations — Defender exclusions on the
  slots dir — are moot on the VM.)
- Judge drain (C2 companion, descriptive): ≤ 2 × 270 = 540 verdicts plus
  calibration sample, strict-JSON structured output per §4.
- Whether n=30 scenarios powers the C1 test is NOT asserted here: power
  depends on the pilot's discordance base rates and is the subject of
  the §5a memo, due before freeze (the E13 power-memo motion).

## 8. Threats to validity (named, not buried)

- **T1 Simulated concurrency.** Deterministic interleave + harness-
  composed presence briefs test the information channel, not the shipped
  daemon or wall-clock racing. Sub-turn races (both agents editing the
  same file inside one turn quantum) are structurally invisible. Claims
  will be scoped to the channel.
- **T2 Author-constructed scenarios.** The founder authors the pressure.
  Counterweights: the existence proof (collision always evitable), the
  measured pressure score, published scenario cards, public harness —
  and, new in this draft, the M5 process rules: cards are committed
  before reference solutions are attempted (auditable order), reference
  pairs live outside agent-reachable roots, and every claim is scoped to
  verified-disjoint-solution scenarios.
- **T3 N=2 generality.** Nothing here evidences 5-agent swarms; Team
  marketing must quote the pair-wise result as pair-wise.
- **T4 Base-rate fragility.** If vanilla agents given explicit scopes
  rarely collide, the study is underpowered by reality; the pilot gate
  and the degenerate-case rule keep the report honest either way, and a
  low control base rate is itself a publishable finding about when
  coordination tooling matters.
- **T5 Same-family judge** on the C2 companion; κ-calibrated,
  confirmatory C-series never touches a judge.
- **T6 Single host, single subscription, time-spread** within the wave —
  now a single always-on VM (§7), whose class, image, and provisioning
  doc revision are pinned and disclosed; house disclosure carries over.
- **T7 Turn-cap artifacts.** The cap may truncate arms asymmetrically
  (e.g., treatment spends turns rerouting); cap-hit rates per arm are
  published, C4 is cap-bounded by construction, and the M7 exposure
  descriptives (§5) put per-arm turns and churn beside the cap-hit
  rates.
- **T8 Presence-brief fidelity.** Transcript-derived touched-paths may
  differ from the daemon's PostToolUse view; the composed slices are
  archived per turn so the discrepancy is auditable.
- **T9 Bundle attribution (softened by the three-arm design).** The
  confirmatory claim is still scoped to the bundle — that is what Team
  ships and what proof 4 declared — but the full-power ledger-only arm
  now puts the ledger/presence split on the record descriptively. The
  residual limitation: the attribution readouts carry no error control
  and must never be quoted as tested findings (M8 fresh-data rule and
  labeling, §5).
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
- **T11 Injection-mass confound (was M9; logged, not removable).** The
  arms differ mechanically in per-turn context growth and compaction
  behavior, and this is collinear with arm — pairing cannot remove it.
  Any bundle effect therefore includes whatever pure context-mass does
  to behavior. Per-turn token and compaction logs (§2, §5) bound the
  confound on the record; a filler-control arm (matched token mass,
  uninformative content) is the clean isolation and is explicitly NOT
  run this wave — an interpretive limitation, stated.
- **T12 Collision reduction by doing less (was M7; audited, not
  assumed away).** The treatment could "win" C1 through artifact
  channels invisible to C5's binary: narrower diffs that defer the
  shared file, early stopping, or untracked-path filename trivia. Status
  after this draft: audited rather than invisible — per-arm exposure
  descriptives with churn ratios, a mandatory audit of every
  C1-discordant scenario, the separately-reported untracked-path
  subcomponent (§5), and the §5 conjunction rule + framing floor, which
  make an artifact-carried C1 unquotable as a funded claim.

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
  shared ratified ledger rendered per worktree [delivery mechanism
  revised post-ratification by O7/O8: slice-only, never on disk in the
  worktree — §2] but no per-turn presence brief. Constraint: the
  confirmatory comparison remains bundle-vs-none ONLY; every ledger-only
  comparison is descriptive, pre-labeled as an attribution readout, no
  tests registered — the attribution arm does not tax proof 4's alpha.
- **OQ-3 (family composition) — RESOLVED: confirmatory family = C1 + C5
  on the bundle-vs-control pair**, C2/C3/C4 descriptive with full
  operationalizations retained (§4) — **as revised by the ratified
  C5-form decision (2026-08-01, review §D.1):** C5's form changes from
  the −10pp Tango non-inferiority test to the M1/M2/M7/M10 deterministic
  falsification package (conjunction rule, c−b ≥ 2 net-harm tripwire,
  absolute-rate disclosure, 50% framing floor). The tested family is
  therefore C1 alone; C5 remains confirmatory in force as a frozen
  falsification rule that spends no alpha. See §5.
- **Execution environment — RESOLVED (2026-08-01, review §D.2): an
  always-on Hetzner Linux VM (CPX32 — 4 vCPU/8GB, sized for strictly-serial episodes, CPX42 rescale path for parallel drains — Ubuntu 24.04, Hillsboro; docs/ops/vm-setup.md),
  pinned at freeze**; setup guide in parallel preparation at
  `docs/ops/vm-setup.md` (§7).
- **OQ-4 (C2 detector) — RESOLVED (2026-08-01, §C position ratified):
  settled structurally.** C2 is descriptive this wave; the pilot's
  detector-calibration readout (shingle verdicts vs κ-calibrated judge
  verdicts) GATES any future promotion of C2 to a tested endpoint — no
  calibration evidence, no promotion, in this wave or Wave-2.
- **OQ-5 (interleave realism) — RESOLVED (2026-08-01, §C position
  ratified): strict alternation with seeded first mover**, the seed
  derived from sha256(scenario_id, rep) only (M3, §2). Determinism over
  simulated realism; realism evidence comes from daemon telemetry later.
- **OQ-6 (C3 evaluability) — RESOLVED (2026-08-01, §C position
  ratified): report both frames** — the hierarchical C3 definition plus
  the ordered composite (collide > contradict > clean) as a second
  descriptive view (§4).
- **OQ-7 (existence-proof ceiling) — RESOLVED (2026-08-01, §C position
  ratified): keep the existence proof** (without it C1 is
  uninterpretable); adopt the M5 authoring-order and reference-pair-
  location rules (§3); scope every claim to "scenarios with a verified
  disjoint solution"; genuinely entangled work is a follow-up study.
- **OQ-8 (N=3 probe) — RESOLVED (2026-08-01, §C position ratified):
  skipped this wave.** A natural follow-up if the bundle lands; not
  costed, not designed here.
- **OQ-9 (turn-cap value) — RESOLVED (2026-08-01, §C position ratified):
  the cap IS the stopping rule.** False completion is an outcome (C5
  fail), never rescued; R is fixed and identical across arms; the pilot
  checks that R=6 (or the R=4 fallback lever, §7) is non-binding in most
  episodes.

### 9.1 Remaining

None. All open questions are resolved and all round-1 review findings
are folded in (Appendix A). What stands between this draft and freeze is
execution, not decisions: scenario authoring under the §3 rules, the
pilot, and the two binding memos (§5a power, §7 wall-clock). Any new
question raised between now and freeze goes through a further review
round or the amendment log, on the record.

## 10. What happens next (rigor pipeline, restated)

1. Scenario authoring under the §3 rules (cards committed before
   reference solutions, wall-time floor measured on the VM) + episode
   runner build on the drain2 pattern (§2) + pilot — all on the VM
   (provisioned per `docs/ops/vm-setup.md`).
2. C1 power memo (§5a) + wall-clock memo (§7), both binding freeze
   gates.
3. Freeze as a numbered prereg (design, tested endpoint, the C5
   falsification package verbatim, closed exclusion taxonomy, seeds,
   environment pins, append mechanism) — committed, tagged, pushed
   public BEFORE any confirmatory row is appended.
4. Pilot gate check → confirmatory drain (concurrency 2, O9 as amended) → analysis
   per the frozen plan. If coordination shows no effect, or costs more
   than it saves, that publishes with the same prominence; proof 4 dies
   honestly (the docs/10 §10 rule).

## Appendix A. Findings crosswalk (review round 1 → draft 3)

Review-closure artifact: every finding in
`design-e-coord-review-1.md` §A/§B and the draft-3 section(s) where its
minimal fix landed.

| finding | landed in |
|---|---|
| M1 (family claim logic unpinned) | §5 falsification package rule 1 (conjunction rule; C1-pass + tripwire-fired publishes as claim-not-funded); §0 pointer |
| M2 (Tango NI guard geometry-forced, fails closed) | §5 package rule 2 (deterministic c−b ≥ 2 net-harm tripwire replaces the −10pp Tango test); §4 C5 tier; §5a removal note |
| M3 (first mover confounded with arm via run_id) | §2 first-mover bullet (sha256(scenario_id, rep) only); §5 randomization bullet |
| M4 (exclusion escape hatches) | §5 exclusions: closed defect taxonomy with mechanical detectors, rerun-not-drop, exclusion-impact sensitivity, mechanical substantive-edit definition |
| M5 (reference-pair leak channels) | §3 anti-leak process rules (authoring order, reference-pair location outside agent-reachable roots), claim scoped to verified-disjoint scenarios; §2 audit extension; §8-T2 |
| M6 (leverage, majority-noise, flaky commands, repo clustering) | §3 determinism check (k≥3 reruns, flake disqualifies); §5 LOSO/LORO sensitivities + per-repo discordance reporting |
| M7 (C1 artifact channels invisible to C5) | §5 exposure descriptives + mandatory C1-discordant audit with churn ratio; §4 C1 untracked-path subcomponent; §5 package rule 3; §8-T12 |
| M8 (attribution readouts in inferential dress) | §5 fresh-data prereg sentence verbatim + "descriptive, no error control" labeling at publication; §1 |
| M9 (injection-mass confound) | §2 per-turn context-token + compaction logging; §5 injection-mass bullet; §8-T11 (filler-control bound as interpretive limitation) |
| M10 (concordant failure makes guard vacuous) | §5 package rules 3-4 (absolute-rate disclosure beside every C1 quote; 50% framing floor) |
| O1 (queue cannot represent an episode) | §2 `episode_turns` checkpoint table spec (atomic per-turn write, replay-from-checkpoint resume after tree-hash verification) |
| O2 (rate-limit gate is an abort → differential exclusion) | §2 pause-not-abort gate semantics, pause counts per arm; §5 exclusion class narrowed to unresumable defects |
| O3 (budget in wrong unit; calendar reality) | §7 restated in CLI completions (~3,300-4,200 incl. pilot + judging), binding wall-clock memo as freeze gate, pre-committed fallback levers (R=4; ledger-arm reps=2); §6 latency-measurement job |
| O4 (no wall-time rule; 1,080+ suite runs) | §3 rule 4 (outcome command ≤120s/tree on the pinned VM host; one timeout constant; pinned build caches) |
| O5 (merged tree never materialized) | §2 third per-episode slot (merge-tree --write-tree + commit-tree + worktree add, tree-hash-verified reset) |
| O6 (orphaned children, sleep/wake, session_id loss) | §2 process hygiene in Linux/systemd form (per-turn process group + killpg, pre-turn PID assertion, atomic session_id persistence); sleep class removed by the §7 always-on VM |
| O7 (judge scrub gap; in-worktree ledger leak; prompt mass) | §1 arm table + §2 injection point (ledger slice-only, never on disk in worktrees); §4 judge protocol (extended scrub denylist with skip-and-count, strict-JSON structured output per commit 779d687, truncation counting) |
| O8 (ledger contaminates C1 untracked-path clause) | Subsumed by O7's slice-only fix; §4 C1 row states the belt-and-braces `.pylgrim/**` exclusion from capture, C1, and the pressure score at freeze |
| O9 (episode parallelism reintroduces lock failures) | §7 concurrency-2 pin as amended 2026-08-02 (pilot evidence: 36/36 at 2-way, zero lock failures; serial fallback pre-committed on 3+ lock defects) |
| O10 (spawn-chain fragility) | §2 runner topology (one long-lived Python process on the drain2 pattern, commit 779d687; systemd unit; heartbeat death detection) |
