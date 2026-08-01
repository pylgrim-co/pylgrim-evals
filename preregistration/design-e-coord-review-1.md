# E-coord draft-2 adversarial review packet · round 1

Review of `design-e-coord-draft-2.md` (commit e752180) by two delegated
adversarial reviewers (methods lens, ops lens) plus the orchestrator's
positions on OQ-4-9. Assembled 2026-08-01. Input to draft 3; nothing
here is frozen. Severities as assigned by the reviewers: fatal /
must-fix-before-freeze / note.

## A. Methods findings (inferential validity)

| # | finding | severity | minimal fix |
|---|---|---|---|
| M1 | Family claim logic unpinned: C1-pass/C5-miss (plausibly the modal outcome) licenses the exact artifact-vulnerable claim C5 exists to block | fatal | Frozen conjunction rule: the marketing sentence is funded only if BOTH endpoints land; C1-pass/C5-not-established publishes as claim-not-funded |
| M2 | C5's −10pp Tango NI guard is geometry-forced (only reachable margin at n=30) and fails closed under trivial noise (b=c=1 → −10.91pp); 6-scenario pilot cannot estimate discordance rates usefully | fatal | Replace the NI test with a pre-registered deterministic tripwire: C1 claim dies if C5 net harm c−b ≥ 2; treatment-arm C5 point estimate + CP bound published beside every C1 quote |
| M3 | First mover derived from run_id (contains arm) → first-mover assignment confounded with arm across pairs | must-fix | Derive first mover from sha256(scenario, rep) only — identical across arms |
| M4 | Exclusion escape hatches: unbounded "harness defect" class on a brand-new orchestrator; drop-the-pair exclusion is differentially likely in the heavier treatment arm | must-fix | Closed defect taxonomy with mechanical detectors, adjudicated before metrics; rerun excluded reps with fresh seeds instead of dropping; exclusion-impact sensitivity; "substantive edit" defined mechanically |
| M5 | Anti-rigging reference pair leaks: authoring order lets scope_paths encode the known-disjoint split; existence-proof filter selects treatment-favorable geometry; reference-pair location unspecified | must-fix | Cards authored and logged BEFORE reference solutions attempted (auditable order); reference pairs live outside all agent-reachable roots, asserted by worktree audit; claim scoped to "scenarios with a verified disjoint solution" |
| M6 | Single-scenario leverage (3-13% of evidence), majority-of-3 amplifies mid-range noise, flaky outcome commands manufacture the killing b=c=1 pattern, 5-per-repo clustering violates pair independence | must-fix | Pre-freeze determinism check (k≥3 reruns on reference merged tree, any flake disqualifies); pre-registered leave-one-scenario-out and leave-one-repo-out sensitivities; per-repo discordance reporting |
| M7 | C1 artifact channels invisible to C5: narrower defer-the-shared-file diffs, early stopping, untracked-path filename trivia | must-fix | Pre-registered per-arm exposure descriptives (turns, churn, files touched, churn ratio vs reference); mandatory audit of every C1-discordant scenario with churn ratio; untracked-path subcomponent reported separately |
| M8 | Attribution readouts carry CP bounds (inferential dress) and no fresh-data rule bars a future registration from testing this wave's ledger-arm data | must-fix | Prereg sentence: no test will ever be computed on this wave's coord-ledger cells; future attribution claims use fresh data only; ledger-arm bounds labeled "descriptive, no error control" at point of publication |
| M9 | Injection-mass confound: arms differ in per-turn context growth/compaction, collinear with arm, pairing cannot remove | note | Log per-turn context tokens + compaction events per arm; publish beside cap-hit rates; filler-control bound added to §8 as interpretive limitation |
| M10 | Concordant failure makes the guard vacuous: NI can clear with 30% absolute success in both arms | note | Framing floor: marketing sentence only quotable with treatment-arm absolute C5 rate attached; below a pre-committed threshold (e.g. 50%) the claim publishes as "collision reduction in a regime where combined success is not attained" |

## B. Ops findings (runnability)

| # | finding | severity | minimal fix |
|---|---|---|---|
| O1 | Queue cannot represent an episode: one row/session/slot/transcript per run; mid-episode death loses the episode; "crash-safe queue absorbs this" is false at episode granularity | fatal | `episode_turns` checkpoint table (episode, agent, turn, session_id, slice_path, tree_hash, status) written atomically per turn; resume = replay from checkpoint after tree-hash verification |
| O2 | Mid-episode rate-limit gate is an abort; §5 exclusion turns gate-straddling into differential exclusion by arm (longer treatment episodes straddle more) | fatal | Gates are PAUSES, never aborts (checkpoint + resume same sessions, same turn order); "rate-limit abort" exclusion applies only to unresumable defects; pause counts published per arm |
| O3 | Budget in wrong unit: ~3,300-4,200 CLI completions (5-7× E13), turns serial within episode → ~130-200 drain-hours, realistically 6-10+ calendar weeks on this machine | must-fix | Binding wall-clock memo beside the power memo, fed by pilot per-turn latency; fallback levers (R=4, ledger-arm reps=2) pre-committed |
| O4 | C5 = 4 suite runs/episode → 1,080+ confirmatory suite runs; heavy-suite repos (nushell/hugo class) nonviable; §3 has no wall-time rule | must-fix | Fourth binding authoring rule: outcome command ≤120s per tree measured on-host at pinned SHA (scoped/targeted test commands); one timeout constant for all outcome runs; shared build caches pinned as harness config |
| O5 | Merged tree never materialized; slot pool is 2 and both slots hold live agent worktrees | must-fix | Third per-episode slot via merge-tree --write-tree + commit-tree + worktree add, same tree-hash-verified reset rule |
| O6 | Orphaned children + sleep/wake corrupt worktrees between turns; session_id lost between CLI completion and persistence makes tokens unaccountable and the episode unresumable | must-fix | Each turn's CLI in a Windows Job Object (kill-on-close); pre-turn assert no prior PID survives; session_id persisted atomically first; machine sleep disabled via powercfg and pinned |
| O7 | Judge scrub built for CLAUDE.md only; ledger rendered in-worktree appears in two of three arms' diffs; two-diff verdicts double prompt mass (truncation) and leak probability | must-fix | Render the ledger OUTSIDE the worktree (slice-only) killing the leak class; extend scrub denylist (.pylgrim/, work-item ids, presence/sibling strings) with skip-and-count; strict JSON judge output |
| O8 | In-worktree ledger contaminates C1's untracked-path clause and capture diffs: harness-manufactured collisions in treatment arms only | must-fix | Subsumed by O7's slice-only fix; else .pylgrim/** excluded from capture, C1, and pressure score, stated at freeze |
| O9 | Episode-level parallelism over shared bare clones reintroduces observed WinError-32/git-clean failures, now fail-loud | note | Pin at freeze: episodes strictly serial (accept O3 calendar cost) or per-episode --reference clones; bounded retry on lock errors; slots dir excluded from Defender |
| O10 | Spawn-chain fragility (PowerShell→bash→python) × ~12 spawns/episode loses whole episodes weekly | note | Episode runner is one long-lived Python process invoking claude via subprocess; launched by Task Scheduler on boot/wake; heartbeat file for death detection |

Coupled fixes: O1+O2 are one fix (per-turn checkpoint + pause semantics).
M1+M2+M7(+M10) are one fix (conjunction rule + deterministic tripwire +
exposure readouts + framing floor) converting the guard from a fragile
CI into a frozen falsification rule. O7 subsumes O8.

## C. Orchestrator positions on OQ-4-9 (for ratification)

- OQ-4: settled structurally — C2 descriptive; pilot detector-calibration
  readout gates any promotion. No decision needed.
- OQ-5: strict alternation, seeded first mover (per M3: seed from
  scenario×rep only). Determinism over simulated realism; realism comes
  from daemon telemetry later.
- OQ-6: report both frames — hierarchical C3 plus the ordered composite
  (collide > contradict > clean) as a second descriptive view.
- OQ-7: keep the existence proof (without it C1 is uninterpretable);
  adopt M5's authoring-order and location fixes; scope the claim to
  verified-separable scenarios; entangled work is follow-up.
- OQ-8: skip the N=3 probe this wave; natural follow-up if the bundle
  lands.
- OQ-9: the cap is the stopping rule; false completion is an outcome
  (C5 fail), never rescued; R fixed and identical across arms; pilot
  checks R=6 is non-binding in most episodes.

## D. Decision points for Sam

1. **C5 form (revises the ratified OQ-3 shape):** adopt the M1/M2/M7/M10
   package — conjunction rule, deterministic net-harm tripwire (c−b ≥ 2
   kills the claim) in place of the −10pp Tango NI test, pre-registered
   exposure/churn readouts, absolute-rate framing floor. The family
   remains C1+C5; C5's test changes from an unpassable CI to a frozen
   falsification rule.
2. **Execution environment:** O3's calendar math (6-10+ weeks local,
   sleep-death exposure throughout) makes the always-on Linux VM
   question concrete. Decide before the pilot, since the environment is
   pinned at freeze.
3. **Ratify C positions** (OQ-5/6/7/8/9 as stated) or amend.

All other findings are freeze hygiene and engineering; the orchestrator
adopts their minimal fixes into draft 3 without further ceremony.
