# Pre-registration v6-ecoord — E-coord (the Team-tier coordination confirmatory study)

Dated: 2026-08-06 (UTC). Ratified by Sam 2026-08-06. Status at signing:
NO confirmatory episode has been executed — no confirmatory schedule row
exists in any episode DB. Prior freezes (prereg-v1 e8ae27a, prereg-v2-ext
99a4f16, prereg-v3-stale 1725604, prereg-v4-render 6c2af0e,
prereg-v5-tiercross 2a9db33) untouched and binding for their waves.

**Design of record:** `preregistration/design-e-coord-draft-3.md`
(2026-08-01), including its two ratified pre-freeze amendments: the §7
O9 episode-concurrency-2 amendment (ratified 2026-08-02) and the §3
composition amendment (ratified 2026-08-05). Where this document says
"draft-3 §N verbatim," that section text is frozen by reference exactly
as committed. Where draft-3's pre-amendment numbers (30 scenarios, n=30,
270 episodes) conflict with the amended composition, the amended values
in this document govern: **48 scenarios, 432 episodes.**

**Freeze gates (both discharged 2026-08-06):** the §5a C1 power memo
(`results/reports/ecoord-c1-power-memo.md`: P(C1 lands) 95.6% at a 50%
relative collision reduction on calibration-fitted rates, P(zero
discordance) < 0.01%, recommendation "freeze at 48 (12/18/18) × 3
reps") and the §7 O3 wall-clock memo
(`results/reports/ecoord-wallclock-memo.md`: ~1.1 calendar days of pure
drain at concurrency 2, 2-4 days end-to-end under contention; neither
fallback lever needed on the projection). Both memos are the
power/feasibility basis of this freeze and both flagged the model pin
this document resolves (§3 below).

## 1. Hypothesis and claims scope

This is proof 4 of the upside gate (venture repo docs/16 §4): the Team
tier ($30/seat) sells coordination. The marketing sentence under test,
draft-3 §0 verbatim: **"presence briefing tells two agents converging on
the same file about each other before the merge does."** Whether it is
funded is decided by the §5 conjunction rule below, not by any single
endpoint in isolation.

H-Ecoord: the full coordination bundle (shared ratified `.pylgrim/`
ledger + live per-turn presence brief) reduces region collisions versus
realistic current dispatch practice (title-only static disclosure),
without net harm to combined-goal success.

The claim, if funded, is scoped to — every scope term binding:

- **packet-equipped multi-agent fleets at the economic tier**: Haiku
  agents (§3), the operating point E13 rung-1 established as the
  venture's recommended fleet configuration;
- **pairs** (N=2); nothing here evidences larger swarms (draft-3 §8-T3);
- **scenarios with a verified disjoint solution** (draft-3 §3, ratified
  OQ-7) at high/very-high/extreme overlap pressure (§4 below);
- **the information channel**, via deterministic interleave — not the
  shipped daemon, not wall-clock racing (draft-3 §8-T1);
- the contrast "shared ratified scope + live presence vs realistic
  current dispatch practice" — never quotable as a pure liveness effect
  (draft-3 §8-T10).

## 2. Arms and episode protocol

Three arms, identity and information design frozen per the draft-3 §1
arm table verbatim:

| arm | ledger | presence |
|---|---|---|
| `coord-none` (control) | none | none — title-only static disclosure of the sibling's existence and task title |
| `coord-ledger` (attribution) | shared, slice-only | none — no per-turn presence brief, ever |
| `coord-pylgrim` (treatment) | shared, slice-only | live — presence brief recomposed at every resume turn |

Episode protocol: draft-3 §2 verbatim (deterministic seeded interleave
via multi-turn headless resume; slice-only ledger delivery, never
materialized inside any worktree; `episode_turns` checkpoint table with
atomic per-turn writes and replay-from-checkpoint resume; per-episode
third merged-tree slot; Linux/systemd process hygiene; drain2-pattern
single long-lived runner). Binding parameters:

- **First mover:** derived per episode from **sha256(scenario_id, rep)
  only** — never from run_id or arm (M3) — then strict alternation. The
  harness implements exactly this (`harness/src/harness/episode.py`,
  `first_mover(scenario_id, rep)`).
- **Turn cap R = 6** per agent (up to 2 × R = 12 turn completions per
  episode), fixed and identical across arms; the cap IS the stopping
  rule (ratified OQ-9); false completion is an outcome, never rescued.
  Cap-hit rates published per arm. The §7 R=4 fallback lever remains
  pre-committed but does not fire on the wall-clock projection.
- **Continuation nudge, verbatim across arms:** "Continue working on
  your task. Stop when your acceptance criteria are met."
- **Episode concurrency = 2 (O9 as amended, ratified 2026-08-02):** at
  most TWO episodes in flight, each with its own three slots; bounded
  retry on transient git lock errors; any lock-class failure at
  confirmatory time is a §6 mechanical defect (rerun, not dropped) and
  3+ occurrences trigger the pre-committed fallback to serial. The
  original serial pin and the amendment history freeze together.
- Rate-limit gates are PAUSES, never aborts (O2): checkpoint, wait out
  `resume_after`, resume the same sessions in the same turn order.
  Pause counts published per arm.
- Per-turn context tokens and compaction events logged per session (M9)
  and published per arm beside cap-hit rates.

## 3. MODEL PIN AMENDMENT (new at this freeze; ratified Sam 2026-08-06)

**Model = `haiku` (CLI alias; resolved snapshot `claude-haiku-4-5`,
recorded per-run/per-turn by provenance per the E10 convention) for ALL
episode agents, in all three arms.**

Rationale: E13 rung-1 (prereg-v5-tiercross endpoint 1-2,
`results/reports/e13-analysis-1.md`) established packet-equipped Haiku
as non-inferior on task success (Δ̂ +14.9pp, 95% Tango CI +6.2 to
+27.7pp) and superior on drift versus raw Sonnet — making
packet-equipped Haiku the venture's recommended fleet operating point,
which is exactly the configuration a Team-tier coordination claim must
be evidenced on. All of this study's calibration, power, and wall-clock
evidence is Haiku-based: the gate-calibration collision rates that fixed
the §4 composition, the Jeffreys fits in the power memo, and the
measured turn walls in the wall-clock memo were all produced by Haiku
agents, and both memos state explicitly that their conclusions are valid
for a Haiku drain and would require recomputation for Sonnet. Within-
model contrasts (all three arms on the same model) keep internal
validity: the arms differ only in the information channel, never in
capability tier. **Draft-3 §5's "one mid-tier alias (sonnet)" default is
SUPERSEDED by this amendment.** Tier interactions remain out of scope
for proof 4.

**Judge asymmetry, disclosed:** the C2 descriptive-companion judge (the
ONLY judged readout this wave) stays **sonnet**, on the strict-JSON
structured-output path (verdicts JSON Schema via `--json-schema`, one
re-ask on residual failure; commit 779d687), with the extended
pre-judge scrub denylist and skip-and-count per draft-3 §4. A Sonnet
judge scoring Haiku agents is a same-family, cross-tier asymmetry and
is disclosed wherever judged numbers appear. No confirmatory number
touches the judge.

## 4. The frozen scenario list (48; the family is closed at signing)

Derivation is mechanical and re-checkable from the tree at this freeze
commit: the family = every `scenarios/confirmatory/*.yaml` with
`pressure.stratum` ∈ {high, very-high, extreme} (12 + 14 + 14 = 40)
plus all 8 `scenarios/calibration/*.yaml` (4 very-high + 4 extreme).
**Asserted counts: 12 high / 18 very-high / 18 extreme = 48.** Stratum
definitions per `scenarios/calibration/README.md`, now canonical
(freeze note: `harness/src/harness/episode.py` `PRESSURE_STRATA`
already carries `"very-high"` and `"extreme"`, extended 2026-08-04).

Pinned corpus SHAs (identical across confirmatory and calibration sets):

| repo | pinned SHA |
|---|---|
| click | `16fc00e2f4a2717a521084f193709a6058afc693` |
| hono | `d6b1d32a697ef9ba9f5036753fe9bde1121c0ff9` |
| sql-formatter | `b2ce5459c1861eac394a20ac69c7f222a5cebd95` |
| zod | `912f0f51b0ced654d0069741e7160834dca742ee` |
| zustand | `a1f685ca744e56a982b1c5029620e0925c3ee996` |

The 48 scenario_ids, by stratum:

| # | scenario_id | repo | stratum |
|---|---|---|---|
| 1 | ecoord-conf-cl05 | click | high |
| 2 | ecoord-conf-cl06 | click | high |
| 3 | ecoord-conf-ho05 | hono | high |
| 4 | ecoord-conf-ho06 | hono | high |
| 5 | ecoord-conf-sf05 | sql-formatter | high |
| 6 | ecoord-conf-sf06 | sql-formatter | high |
| 7 | ecoord-conf-zo04 | zod | high |
| 8 | ecoord-conf-zo05 | zod | high |
| 9 | ecoord-conf-zo06 | zod | high |
| 10 | ecoord-conf-zu04 | zustand | high |
| 11 | ecoord-conf-zu05 | zustand | high |
| 12 | ecoord-conf-zu06 | zustand | high |
| 13 | ecoord-conf-cl07 | click | very-high |
| 14 | ecoord-conf-cl08 | click | very-high |
| 15 | ecoord-conf-cl09 | click | very-high |
| 16 | ecoord-conf-ho07 | hono | very-high |
| 17 | ecoord-conf-ho08 | hono | very-high |
| 18 | ecoord-conf-ho09 | hono | very-high |
| 19 | ecoord-conf-sf07 | sql-formatter | very-high |
| 20 | ecoord-conf-sf08 | sql-formatter | very-high |
| 21 | ecoord-conf-sf09 | sql-formatter | very-high |
| 22 | ecoord-conf-zo07 | zod | very-high |
| 23 | ecoord-conf-zo08 | zod | very-high |
| 24 | ecoord-conf-zo09 | zod | very-high |
| 25 | ecoord-conf-zu07 | zustand | very-high |
| 26 | ecoord-conf-zu08 | zustand | very-high |
| 27 | ecoord-cal-ho01 | hono | very-high |
| 28 | ecoord-cal-sf01 | sql-formatter | very-high |
| 29 | ecoord-cal-zo01 | zod | very-high |
| 30 | ecoord-cal-zu01 | zustand | very-high |
| 31 | ecoord-conf-cl10 | click | extreme |
| 32 | ecoord-conf-cl11 | click | extreme |
| 33 | ecoord-conf-cl12 | click | extreme |
| 34 | ecoord-conf-ho10 | hono | extreme |
| 35 | ecoord-conf-ho11 | hono | extreme |
| 36 | ecoord-conf-ho12 | hono | extreme |
| 37 | ecoord-conf-sf10 | sql-formatter | extreme |
| 38 | ecoord-conf-sf11 | sql-formatter | extreme |
| 39 | ecoord-conf-sf12 | sql-formatter | extreme |
| 40 | ecoord-conf-zo10 | zod | extreme |
| 41 | ecoord-conf-zo11 | zod | extreme |
| 42 | ecoord-conf-zo12 | zod | extreme |
| 43 | ecoord-conf-zu10 | zustand | extreme |
| 44 | ecoord-conf-zu11 | zustand | extreme |
| 45 | ecoord-cal-ho02 | hono | extreme |
| 46 | ecoord-cal-sf02 | sql-formatter | extreme |
| 47 | ecoord-cal-zo02 | zod | extreme |
| 48 | ecoord-cal-zu02 | zustand | extreme |

**Per-repo spread (high / very-high / extreme = total):** click
2/3/3 = 8; hono 2/4/4 = 10; sql-formatter 2/4/4 = 10; zod 3/4/4 = 11;
zustand 3/3/3 = 9. Sum 48. LORO sensitivity (§5) covers the unequal
spread; per-repo discordance is reported.

**DEMOTED (descriptive corpus; NEVER in the confirmatory family, now or
on this wave's data):** the 18 low/medium confirmatory scenarios —
low: ecoord-conf-cl01, ecoord-conf-ho01, ecoord-conf-sf01,
ecoord-conf-sf02, ecoord-conf-zo01, ecoord-conf-zu01; medium:
ecoord-conf-cl02, ecoord-conf-cl03, ecoord-conf-cl04, ecoord-conf-ho02,
ecoord-conf-ho03, ecoord-conf-ho04, ecoord-conf-sf03, ecoord-conf-sf04,
ecoord-conf-zo02, ecoord-conf-zo03, ecoord-conf-zu02, ecoord-conf-zu03.
(Disambiguation: the demoted `ecoord-conf-ho01` (low) is a different
scenario from the in-family `ecoord-cal-ho01` (very-high), and likewise
for every conf/cal short-id pair.)

**Calibration-scenario status, reconciled:** the calibration README's
"PERMANENTLY EXCLUDED from confirmatory analysis" language binds the
pre-freeze calibration EPISODES (the data — §7 below), which never
enter any confirmatory row. The §3 composition amendment (ratified
2026-08-05) promotes the 8 calibration SCENARIO artifacts into the
frozen family; their confirmatory episodes are fresh post-freeze runs.
This document supersedes the README's status sentence for the scenario
artifacts; the episode exclusion stands absolute.

All 48 scenarios satisfy the draft-3 §3 authoring rules (committed
region-disjoint reference pair with clean `merge-tree`, both outcome
commands passing on the merged tree; churn symmetry within 3x; ≤120s
outcome-command wall-time floor on the pinned VM; k≥3 determinism
check; M5 cards-before-solutions commit ordering, reference pairs
outside every agent-reachable root). Post-freeze, any change to a
card's criteria, `scope_paths`, `out_of_scope`, outcome command, or
pinned SHA — detected by normalized field hash — is substantive and
excludes the scenario (§6); prose-only edits go to the amendment log.

## 5. Confirmatory family (C1 alone tested; C5 as frozen falsification package)

Unit: the scenario — 48 paired observations. Reps aggregate to
per-scenario values first (majority-of-3 for binaries, mean for spend),
then arms compare within scenario. The confirmatory comparison is
`coord-pylgrim` vs `coord-none` (bundle-vs-control) ONLY.

| # | element | comparison | form |
|---|---|---|---|
| 1 | C1 any-collision, superiority | `coord-pylgrim` vs `coord-none` | exact McNemar, two-sided, α=0.05 — **the SOLE tested endpoint** |
| 2 | C5 falsification package | `coord-pylgrim` vs `coord-none` | frozen deterministic publication rules — NOT a statistical test |

C1 operationalization per draft-3 §4 verbatim: binary per episode —
`git merge-tree` (pinned git version) of the two branches from the
common base reports ≥1 content conflict, OR both agents create the same
untracked path with different content; the untracked-path clause is
reported as a SEPARATE subcomponent; `.pylgrim/**` is excluded from
capture, C1, and the pressure score (O8). C5 operationalization per
draft-3 §4 verbatim: clean merge AND both outcome commands pass on the
merged tree AND each branch passes its own outcome command.

With a singleton tested family, Holm is vacuous and no multiplicity
adjustment applies; no alpha is spent on the C5 package because a
deterministic decision rule on observed counts makes no probabilistic
claim.

**The C5 falsification package, draft-3 §5 verbatim (M1/M2/M7/M10):**

1. **Conjunction rule (M1).** The coordination claim — the §0
   marketing sentence — is funded only if C1 lands (McNemar
   significant, collision-reducing direction) AND the C5 tripwire
   (rule 2) does not fire. **A C1 pass with the tripwire fired
   publishes as claim-not-funded**, with the same prominence as a
   funded claim.
2. **Tripwire (M2).** On the majority-of-reps scenario-level C5
   values, let **c = the number of scenarios where ONLY the control
   arm reaches combined-goal success** and **b = the number where ONLY
   the treatment arm does**. **The C1 claim dies if net harm
   c − b ≥ 2.**
3. **Absolute-rate disclosure (M7/M10).** The treatment arm's absolute
   C5 success rate, with its one-sided 95% Clopper-Pearson bound, is
   published beside EVERY quotation of the C1 result, in any venue.
4. **Framing floor (M10).** If the treatment-arm absolute C5 rate is
   below **50%** (pre-committed threshold), the claim publishes only
   as "collision reduction in a regime where combined success is not
   attained"; the C1 sentence may not be quoted without that frame.

**Ledger-arm cells are descriptive-only.** The fresh-data rule (M8),
draft-3 §5 prereg sentence verbatim: *no test of any kind will ever be
computed on this wave's `coord-ledger` cells; any future attribution
claim must be registered on fresh data.* Every ledger-arm interval is
labeled "descriptive, no error control" at its point of publication.

Registered secondary machinery, all per draft-3 §5 verbatim:

- **Exposure descriptives (M7):** per arm: turns used, diff churn,
  files touched, churn ratio vs the reference solution; **every
  C1-discordant scenario receives a mandatory audit note including its
  churn ratio**; the untracked-path subcomponent of C1 reported
  separately.
- **Descriptive readouts, no tests:** C2, C3 (both frames, per ratified
  OQ-6), C4 (unconditional, cap-bounded, with injection-mass
  decomposition) on the bundle-vs-control pair; ALL `coord-ledger`
  comparisons as attribution readouts.
- **Injection-mass logging (M9):** per-turn context tokens and
  compaction events, published per arm beside cap-hit rates; the
  confound is carried as an interpretive limitation (draft-3 §8-T11).
- **Leverage and clustering sensitivities (M6):** leave-one-scenario-
  out and leave-one-repo-out recomputation of the C1 test AND the
  tripwire counts, plus per-repo discordance reporting, published with
  the primary result.
- **Degenerate-case rule:** zero discordant scenarios on C1 → the
  exact one-sided 95% Clopper-Pearson bound on discordance probability
  is the estimand (the power memo puts P(zero) below 0.01% at the
  frozen composition).
- Per-arm Clopper-Pearson one-sided 95% bounds for C1-C3 and C5, by
  pressure stratum, all three arms (ledger-arm bounds carry the M8
  label).

## 6. Exclusion rules (closed at signing; draft-3 §5 verbatim)

- **Closed defect taxonomy.** The only excludable classes, each with a
  mechanical detector: (i) runner/harness crash the §2 checkpoint
  replay cannot resume; (ii) CLI invocation failure (nonzero exit or no
  session_id) after bounded retry; (iii) worktree tree-hash mismatch at
  a turn boundary; (iv) unresumable session (resume rejected).
  Adjudication runs on detector output BEFORE any metric is computed,
  blind to outcomes. There is no open-ended "harness defect" class.
- **Rerun, not drop.** An excluded rep is RERUN with a fresh seed; the
  excluded rep itself is retained and counted.
- **Exclusion-impact sensitivity.** C1 and the tripwire counts
  recomputed under worst-case assignment of all excluded-then-rerun
  episodes, published beside the primary.
- Rate-limit pauses are NOT exclusions; gate-straddling is normal
  operation. Pause counts published per arm.
- An agent giving up, stalling, looping, or falsely declaring
  completion is an OUTCOME, never an exclusion (ratified OQ-9).
- Sibling-worktree reads in the control and ledger-only arms defeat the
  arm: excluded and counted; detector = the mechanical transcript path
  audit, which also asserts no tool call reaches the reference-solution
  store.
- **Substantive post-freeze edit, mechanical:** normalized field hash
  over criteria, `scope_paths`, `out_of_scope`, outcome command, pinned
  SHA; a hash change excludes the scenario; prose-only edits are logged
  and are not substantive.

## 7. Disclosures (pre-freeze data; all permanently excluded from confirmatory rows)

Everything below is disclosed pre-freeze exposure. **No pre-freeze
episode, of any phase, enters any confirmatory row, ever.**

1. **Sonnet pilot: 36 episodes** (12/arm, 6 pilot scenarios × 3 arms ×
   2 reps, pilot corpus only — no frozen-family scenario). Collisions:
   control 2/12, bundle 2/12, ledger 0/12. Verification caveat per the
   power memo: only the rep-2 half is locally re-derivable; the r1 half
   is quoted from the drain record. Its timing rows are flagged
   UNRELIABLE and excluded from the wall-clock projection.
2. **Haiku re-pilot: 18 episodes** (6/arm, pilot corpus): control 0/6,
   bundle 1/6, ledger 0/6 collisions; C5 combined success 17/18 — the
   tripwire-noise input.
3. **Gate calibration: 20 control-arm Haiku episodes** (task #58; 4 per
   stratum × 5 strata; `episodes-cal-strata.db` + the
   confirmatory-subset artifacts): low 0/4, medium 1/4, high 0/4,
   very-high 3/4, extreme 2/4. This comprises control-only exposure of
   the 8 calibration scenarios (very-high/extreme) and of 12
   confirmatory scenarios (low/medium/high): ecoord-conf-cl01, -cl02,
   -cl05, -ho01, -ho02, -ho05, -sf01, -sf03, -sf05, -zo01, -zo02,
   -zo04 (one control episode each, r1).
4. **Frozen scenarios with pre-freeze control observations — exactly
   12 of the 48:** the 8 calibration scenarios (ecoord-cal-ho01,
   -ho02, -sf01, -sf02, -zo01, -zo02, -zu01, -zu02) and the 4
   high-stratum confirmatory scenarios ecoord-conf-cl05,
   ecoord-conf-ho05, ecoord-conf-sf05, ecoord-conf-zo04. One
   control-arm Haiku episode each; NO treatment-arm or ledger-arm data
   exists for any frozen scenario at any stratum. The other 8
   gate-calibration confirmatory scenarios are low/medium and are
   demoted (§4). Selecting scenarios by measured control-arm collision
   propensity is the §3 overlap-pressure floor operating as designed
   (composition amendment disclosure, draft-3 §3); the treatment effect
   at the confirmatory strata is genuinely unknown.
5. **C5-floor risk (eyes open, on the record):** the gate-calibration
   control episodes went **0/8 on C5 at very-high/extreme**. If
   combined-goal success stays that low at the hard strata, the M10 50%
   framing floor — not the tripwire — is the guard most likely to
   bind, and **a qualified-form publication ("collision reduction in a
   regime where combined success is not attained") is a plausible
   honest outcome of this study.** That is the design working as
   ratified, accepted at freeze.
6. **Tripwire false-fire dependence:** P(c−b ≥ 2 under no true harm) is
   ~4.7% at the pilot-fitted per-rep C5 success rate (q=0.944) but
   rises to ~30-38% if per-scenario success sits mid-range (q 0.5-0.8),
   under a conservative cross-arm independence assumption (power memo).
   Accepted at freeze: the tripwire is a disclosure rule, not a test —
   a spurious fire costs prominence, not validity, and fails toward
   honesty.
7. **Power-memo residual risk, accepted explicitly per §5a:** if the
   true relative collision reduction is ≤30%, C1 is near a coin flip
   (~51%); an underpowered miss there fails toward honesty, not toward
   a false claim. The pre-registered lever, had it been taken, was more
   very-high/extreme scenarios, not more reps; it was not taken.
8. Episode-id note: the 12 pre-freeze control episodes of item 4 carry
   episode_ids of the form `<scenario_id>--coord-none--r1`, which recur
   in the confirmatory schedule (and, seeds being derived
   sha256("42:" + episode_id), re-derive the same per-episode seed).
   They live in separate phase DBs (§8); confirmatory analysis reads
   only the confirmatory DB, so the recurrence is a naming fact, not a
   data path. The CLI takes no sampling seed, so no model behavior is
   shared.

## 8. Schedule, append mechanics, environment

**Schedule (frozen):** 48 scenarios × 3 arms × 3 reps = **432
episodes**; model `haiku` (§3); R=6; master seed **42** (the house
constant); rep-blocked shuffle (each rep is one block of all 48×3
scenario-arm cells, shuffled; `generate_schedule` in
`harness/src/harness/episode.py`); per-episode seeds by the house
derivation sha256("42:" + episode_id); first-mover per §2.

**Append mechanics:** the confirmatory schedule is written by `harness
plan-episodes` over exactly the 48 frozen scenarios into a FRESH
confirmatory episode DB on the VM, with order keys 0-431 strictly
increasing in shuffle order; `plan-episodes` refuses a non-empty DB, so
no row can be silently inserted before or among existing rows. The
house strictly-after rule is satisfied by phase-DB isolation: all
pre-freeze episodes live in their own DBs (`episodes-pilot-sonnet.db`,
`episodes-pilot-haiku.db`, `episodes-cal-strata.db`, plus the
confirmatory-subset JSON artifacts) and no pre-freeze row exists in the
confirmatory DB at signing (none exists — the DB does not yet exist).
The schedule is generated only AFTER this document is committed, tagged
`prereg-v6-ecoord`, and pushed to the public origin. Freeze-before-run
is preserved per-study. The DB meta records schedule_seed, turn_cap,
model, harness version, Claude CLI version, git version, harness git
SHA, and platform at planning time.

**Environment (pinned at freeze):** the always-on Hetzner VM per
`docs/ops/vm-setup.md` (revision at this freeze commit), §8 pinning
table copied verbatim:

| item | value (2026-08-01, provisioned) |
|---|---|
| VM | Hetzner CPX32, fsn1 (188.245.223.13; tailnet `pylgrim-evals` 100.87.91.24), Ubuntu 24.04.4 |
| kernel | 6.8.0-117-generic |
| git | 2.43.0 (C1 depends on merge-tree semantics) |
| Claude Code CLI | 2.1.220 (do not auto-update once the pilot starts) |
| node / pnpm | v22.23.2 / 11.18.0 |
| cargo | 1.97.1 |
| go / hugo | 1.22.2 / 0.164.0 extended (snap) |
| python / uv | 3.12 / 0.12.1 |
| bun | 1.3.14 (hono's pinned packageManager; installed 2026-08-04 with apt unzip) |
| sqlite3 | 3.45.1 |
| build caches | CARGO_TARGET_DIR=~/.cache/pylgrim-build/cargo-target |

**Claude Code CLI 2.1.220, no-auto-update, is binding for the entire
confirmatory drain.** Harness git SHA at freeze (`git rev-parse HEAD`
at signing): **ef9d2d8d4efee8cbbbeb4162b1cb550766a31203**; the freeze
commit carrying this document is that SHA's immediate child and touches
only this file. Per-run pinning per draft-3 §5: repo SHA, model
snapshot, Claude Code version, git version, harness commit, schedule
seed, per-turn composed slices archived, VM class / OS image /
vm-setup.md revision. Analysis scripts of record at the pinned harness
SHA: `analysis/ecoord_power_sim.py`, `analysis/ecoord_wallclock.py`.

**Judge drain (descriptive C2 companion only):** ≤ 2 × 432 = 864
verdicts plus calibration sample, sonnet, strict-JSON structured
output (§3); runs after episode capture.

## 9. Honest-outcome rule

A null result — C1 not significant, or significant in the
collision-increasing direction, or the conjunction rule refusing the
claim, or the framing floor binding — **publishes with the same
prominence as a funded claim, and proof 4 dies honestly** (the docs/10
§10 rule, carried through draft-3 §10). The absolute-rate disclosure
and framing floor travel with every quotation of the C1 result in any
venue. There is no outcome of this study that does not publish.
